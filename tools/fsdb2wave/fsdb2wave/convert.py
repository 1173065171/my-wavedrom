"""Sample a window per reference-clock cycle and emit WaveJSON."""

from __future__ import annotations

import bisect
import math
import re
import statistics
import zlib
from dataclasses import dataclass, field
from difflib import get_close_matches

from .errors import Fsdb2WaveError, INPUT, CONSTRAINT, NOT_FOUND
from .timeutil import fmt_time
from .vcd import VarInfo, normalize_path
from .window import collect

HARD_MAX_SIGNALS = 128
HARD_MAX_CYCLES = 1024
MAX_BUS_CHARS = 16          # longer data labels are elided in the middle
MAX_GLITCH_WARNINGS = 100


@dataclass
class Options:
    signals: list[str]
    clock: str
    cycles: int
    edge: str = 'pos'
    start_time: int | None = None       # ticks
    start_cycle: int | None = None
    sample: str = 'mid'                 # 'mid' | 'pre'
    radix: str = 'hex'                  # 'hex' | 'bin' | 'dec' | 'sdec'
    color: str = 'none'                 # 'none' | 'value' | 'signal'
    group_by_scope: bool = False
    strip_prefix: str = ''
    alias: dict[str, str] = field(default_factory=dict)
    max_signals: int = 32
    max_cycles: int = 128
    truncate: bool = False
    mark_glitch: bool = False
    hscale: int | None = None
    source_name: str = ''
    backend: str = ''


# ---------------------------------------------------------------- selection

def _pattern(text: str):
    text = normalize_path(text)
    if '*' not in text and '?' not in text:
        return None, text
    regex = ''.join('.*' if c == '*' else '.' if c == '?' else re.escape(c) for c in text)
    return re.compile('^' + regex + '$'), text


def select(vars_: list[VarInfo], patterns: list[str]) -> list[VarInfo]:
    by_path: dict[str, VarInfo] = {}
    for v in vars_:
        by_path.setdefault(v.path, v)
    res: list[VarInfo] = []
    seen = set()
    for pat in patterns:
        regex, text = _pattern(pat)
        if regex is None:
            hits = [by_path[text]] if text in by_path else []
        else:
            hits = [v for p, v in by_path.items() if regex.match(p)]
        if not hits:
            raise Fsdb2WaveError(NOT_FOUND, 'signal not found: %s' % pat,
                                 get_close_matches(text, list(by_path), n=5, cutoff=0.5))
        for v in hits:
            if v.path not in seen:
                seen.add(v.path)
                res.append(v)
    return res


# ------------------------------------------------------------------ values

def pad_bits(bits: str, width: int) -> str:
    if len(bits) >= width:
        return bits[-width:]
    fill = bits[0] if bits and bits[0] in 'xz' else '0'
    return fill * (width - len(bits)) + bits


def _elide(text: str, warn, path: str) -> str:
    if len(text) <= MAX_BUS_CHARS:
        return text
    warn({'kind': 'bus-truncated', 'signal': path, 'length': len(text)})
    keep = (MAX_BUS_CHARS - 1) // 2
    return text[:keep] + '…' + text[-keep:]


def format_bits(bits: str, radix: str) -> str:
    if radix == 'bin':
        return bits
    if radix in ('dec', 'sdec'):
        if any(b in 'xz' for b in bits):
            return 'x'
        n = int(bits, 2)
        if radix == 'sdec' and bits[0] == '1':
            n -= 1 << len(bits)
        return str(n)
    digits = []
    bits = '0' * ((-len(bits)) % 4) + bits
    for i in range(0, len(bits), 4):
        nib = bits[i:i + 4]
        if all(b in '01' for b in nib):
            digits.append('%X' % int(nib, 2))
        elif all(b == 'z' for b in nib):
            digits.append('z')
        else:
            digits.append('x')
    text = ''.join(digits).lstrip('0')
    return text or '0'


def classify(value: str, var: VarInfo):
    """-> (kind, text): kind in '0' '1' 'x' 'z' 'v' (data); text for 'v'."""
    if var.kind == 'real' or value.startswith('r'):
        try:
            return 'v', '%.4g' % float(value[1:])
        except ValueError:
            return 'x', ''
    if var.kind == 'string' or value.startswith('s'):
        return 'v', value[1:]
    if var.width == 1:
        v = value[-1:] or 'x'
        return (v if v in '01xz' else 'x'), ''
    bits = pad_bits(value, var.width)
    if all(b == 'x' for b in bits):
        return 'x', ''
    if all(b == 'z' for b in bits):
        return 'z', ''
    return 'v', bits


# ---------------------------------------------------------------- sampling

class Trace:
    def __init__(self, init: str | None, changes: list[tuple[int, str]]):
        self.init = init if init is not None else 'x'
        self.times = [t for t, _ in changes]
        self.values = [v for _, v in changes]

    def at(self, t: float, strict: bool = False) -> str:
        """Value at time t (strict: just before t)."""
        idx = (bisect.bisect_left if strict else bisect.bisect_right)(self.times, t) - 1
        return self.values[idx] if idx >= 0 else self.init

    def transitions(self, t0: int, t1: int) -> list[tuple[int, str]]:
        """Actual value changes in [t0, t1)."""
        lo = bisect.bisect_left(self.times, t0)
        hi = bisect.bisect_left(self.times, t1)
        prev = self.at(t0, strict=True)
        res = []
        for t, v in zip(self.times[lo:hi], self.values[lo:hi]):
            if v != prev:
                res.append((t, v))
            prev = v
        return res

    def edges(self, t0: int, t1: int, target: str) -> list[int]:
        lo = bisect.bisect_left(self.times, t0)
        hi = bisect.bisect_left(self.times, t1)
        prev = self.at(t0, strict=True)
        res = []
        for t, v in zip(self.times[lo:hi], self.values[lo:hi]):
            if v == target and prev != target:
                res.append(t)
            prev = v
        return res


def _near(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol


def clock_pulse(changes: list[tuple[int, str]], t0: int, t1: int):
    """One full clock pulse starting at the reference edge -> 'p' / 'n'.
    Lets gated or occasionally running clocks render as clock cycles."""
    if len(changes) != 2:
        return None
    (ta, va), (tb, vb) = changes
    span = t1 - t0
    if not _near(ta, t0, 0.01 * span) or not (t0 + 0.1 * span <= tb <= t0 + 0.9 * span):
        return None
    if (va, vb) == ('1', '0'):
        return 'p'
    if (va, vb) == ('0', '1'):
        return 'n'
    return None


def detect_clock(trace: Trace, edges: list[int], period: float, cycles: int):
    """A 1-bit signal that is a free-running clock aligned to the window start
    -> ('p' | 'n', k) with k = its period in reference cycles; else None."""
    e0, end = edges[0], edges[-1]
    tol = 0.01 * period
    for char, target, other in (('p', '1', '0'), ('n', '0', '1')):
        lead = trace.edges(e0, end, target)
        if len(lead) < 2 or not _near(lead[0], e0, tol):
            continue
        k = round((lead[1] - lead[0]) / period)
        if k < 1 or any(not _near(b - a, k * period, k * tol) for a, b in zip(lead, lead[1:])):
            continue
        trail = trace.edges(e0, end, other)
        if not trail or not _near(trail[0] - lead[0], k * period / 2, k * tol):
            continue
        if len(lead) != math.ceil(cycles / k):
            continue
        return char, k
    return None


# ------------------------------------------------------------------ output

def display_name(path: str, opts: Options) -> str:
    if path in opts.alias:
        return opts.alias[path]
    prefix = opts.strip_prefix
    if prefix:
        if not prefix.endswith('.'):
            prefix += '.'
        if path.startswith(prefix):
            return path[len(prefix):]
    return path


def _color(opts: Options, text: str, index: int) -> str:
    if opts.color == 'value':
        return str(2 + zlib.crc32(text.encode('utf-8')) % 8)
    if opts.color == 'signal':
        return str(2 + index % 8)
    return '='


def _check_limits(opts: Options, n_signals: int, warnings: list) -> tuple[int, int]:
    for name, value, hard in (('max-signals', opts.max_signals, HARD_MAX_SIGNALS),
                              ('max-cycles', opts.max_cycles, HARD_MAX_CYCLES)):
        if value < 1 or value > hard:
            raise Fsdb2WaveError(CONSTRAINT, '--%s must be between 1 and %d' % (name, hard))
    if opts.cycles < 1:
        raise Fsdb2WaveError(INPUT, '--cycles must be at least 1')
    cycles, keep = opts.cycles, n_signals
    if opts.cycles > opts.max_cycles:
        if not opts.truncate:
            raise Fsdb2WaveError(CONSTRAINT, '%d cycles requested, limit is %d (use --truncate or narrow the window)'
                                 % (opts.cycles, opts.max_cycles))
        cycles = opts.max_cycles
        warnings.append({'kind': 'cycles-truncated', 'requested': opts.cycles, 'kept': cycles})
    if n_signals > opts.max_signals:
        if not opts.truncate:
            raise Fsdb2WaveError(CONSTRAINT, '%d signals selected, limit is %d (use --truncate or select fewer)'
                                 % (n_signals, opts.max_signals))
        keep = opts.max_signals
        warnings.append({'kind': 'signals-truncated', 'selected': n_signals, 'kept': keep})
    return cycles, keep


def convert(source, opts: Options) -> dict:
    header = source.header
    tick_fs = header.tick_fs
    warnings: list[dict] = []

    clock = select(header.vars, [opts.clock])
    if len(clock) != 1:
        raise Fsdb2WaveError(INPUT, 'clock must name exactly one signal, got %d' % len(clock))
    clock = clock[0]
    if clock.width != 1 or clock.kind != 'logic':
        raise Fsdb2WaveError(INPUT, 'clock %s is not a 1-bit signal' % clock.path)

    selected = [v for v in select(header.vars, opts.signals) if v.path != clock.path]
    usable = []
    for v in selected:
        if v.kind == 'event':
            warnings.append({'kind': 'signal-skipped', 'signal': v.path, 'reason': 'event'})
        else:
            usable.append(v)
    cycles, keep = _check_limits(opts, len(usable), warnings)
    usable = usable[:keep]

    codes = [clock.code] + [v.code for v in usable]
    win = collect(source, clock.code, codes, opts.edge, opts.start_time, opts.start_cycle, cycles)
    edges = win.edges
    if len(edges) < 2:
        where = ('@%d' % opts.start_cycle) if opts.start_cycle is not None else \
            fmt_time(opts.start_time or 0, tick_fs)
        raise Fsdb2WaveError(INPUT, 'fewer than 2 %s edges of %s from %s' % (opts.edge, clock.path, where))

    intervals = [b - a for a, b in zip(edges, edges[1:])]
    period = statistics.median(intervals)
    if len(edges) < cycles + 1:
        edges = edges + [edges[-1] + period]          # end of dump: close the last cycle
        warnings.append({'kind': 'last-edge-estimated', 'time': fmt_time(edges[-1], tick_fs)})
        if len(edges) < cycles + 1:
            warnings.append({'kind': 'window-truncated', 'requested': cycles, 'kept': len(edges) - 1})
            cycles = len(edges) - 1
    for i, d in enumerate(intervals[:cycles]):
        if abs(d - period) > 0.1 * period:
            warnings.append({'kind': 'clock-irregular', 'cycle': win.start_index + i,
                             'interval': fmt_time(d, tick_fs), 'period': fmt_time(period, tick_fs)})

    glitches = [0]

    def warn(item):
        if item['kind'] == 'multi-transition':
            glitches[0] += 1
            if glitches[0] > MAX_GLITCH_WARNINGS:
                return
        if item not in warnings:
            warnings.append(item)

    rows = [(clock, {'name': display_name(clock.path, opts),
                     'wave': ('p' if opts.edge == 'pos' else 'n') + '.' * (cycles - 1)})]
    widest = 1.0
    for index, var in enumerate(usable):
        trace = Trace(win.init.get(var.code), win.changes.get(var.code, []))
        entry = {'name': display_name(var.path, opts)}
        if var.width == 1 and var.kind == 'logic':
            clk = detect_clock(trace, edges[:cycles + 1], period, cycles)
            if clk is not None:
                char, k = clk
                entry['wave'] = char + '.' * (math.ceil(cycles / k) - 1)
                if k > 1:
                    entry['period'] = k
                rows.append((var, entry))
                continue

        wave, data, spans = [], [], []
        prev_key = None
        for i in range(cycles):
            t0, t1 = edges[i], edges[i + 1]
            changes = trace.transitions(t0, t1)
            pulse = clock_pulse(changes, t0, t1) if var.width == 1 and var.kind == 'logic' else None
            if pulse is not None:
                key = ('clk', pulse)
                wave.append('.' if prev_key == key else pulse)
                prev_key = key
                continue
            if len(changes) >= 2:
                warn({'kind': 'multi-transition', 'signal': var.path, 'cycle': win.start_index + i,
                      'transitions': len(changes)})
                if opts.mark_glitch:
                    wave.append('x')
                    prev_key = None
                    continue
            value = trace.at(t0 + (t1 - t0) / 2) if opts.sample == 'mid' else trace.at(t1, strict=True)
            kind, bits = classify(value, var)
            key = (kind, bits)
            if prev_key == key:
                wave.append('.')
                if kind == 'v':
                    spans[-1] += 1
                continue
            prev_key = key
            if kind != 'v':
                wave.append(kind)
                continue
            if var.kind == 'logic':
                text = _elide(format_bits(bits, opts.radix), warn, var.path)
            else:
                text = bits
            wave.append(_color(opts, text, index))
            data.append(text)
            spans.append(1)
        entry['wave'] = ''.join(wave)
        if any(c in 'pn' for c in wave):
            # clock-style levels join pulses without the 0/1 transition slope
            entry['wave'] = entry['wave'].replace('0', 'l').replace('1', 'h')
        if data:
            entry['data'] = data
            widest = max([widest] + [(len(t) * 7.5 + 8) / (40.0 * s) for t, s in zip(data, spans)])
        rows.append((var, entry))

    if glitches[0] > MAX_GLITCH_WARNINGS:
        warnings.append({'kind': 'multi-transition-omitted', 'count': glitches[0] - MAX_GLITCH_WARNINGS})

    signal = _group(rows, opts) if opts.group_by_scope else [e for _, e in rows]
    e0, e_end = edges[0], edges[cycles]
    prefix = opts.strip_prefix.rstrip('.')
    hscale = opts.hscale or max(1, min(3, math.ceil(widest - 1e-9)))
    return {
        'signal': signal,
        'head': {
            'text': ((prefix + '  ') if prefix else '') + fmt_time(e0, tick_fs) + ' – ' + fmt_time(e_end, tick_fs),
            'tick': win.start_index
        },
        'config': {'hscale': hscale},
        'meta': {
            'source': opts.source_name,
            'backend': opts.backend,
            'clock': {'path': clock.path, 'edge': opts.edge, 'period': fmt_time(period, tick_fs)},
            'window': {'start': fmt_time(e0, tick_fs), 'end': fmt_time(e_end, tick_fs),
                       'startCycle': win.start_index, 'cycles': cycles},
            'sample': opts.sample,
            'radix': opts.radix,
            'warnings': warnings
        }
    }


def _group(rows, opts: Options) -> list:
    """Nest rows under their parent scope: ['scope', {...}, ...]."""
    res: list = [rows[0][1]]                 # reference clock stays on top
    groups: dict[str, list] = {}
    for var, entry in rows[1:]:
        name = display_name(var.path, opts)
        if var.path in opts.alias or '.' not in name:
            res.append(entry)
            continue
        scope, leaf = name.rsplit('.', 1)
        entry = dict(entry, name=leaf)
        if scope not in groups:
            groups[scope] = [scope]
            res.append(groups[scope])
        groups[scope].append(entry)
    return res
