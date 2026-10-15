"""Command line interface. Errors go to stderr as one JSON line:
{"code": 3, "message": "...", "candidates": [...]}  with the same exit code."""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__
from .backends import open_source
from .convert import Options, convert, HARD_MAX_CYCLES, HARD_MAX_SIGNALS
from .errors import Fsdb2WaveError, INPUT
from .timeutil import parse_time


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Fsdb2WaveError(INPUT, message)


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(prog='fsdb2wave', description='Convert a bounded window of FSDB / VCD waveforms into WaveDrom WaveJSON.')
    p.add_argument('input', help='.fsdb or .vcd file')
    p.add_argument('-s', '--signal', action='append', default=[], metavar='PATH',
                   help='hierarchical path, repeatable; * and ? wildcards')
    p.add_argument('--signals-file', metavar='FILE', help='one path per line, # comments')
    p.add_argument('-c', '--clock', required=True, metavar='PATH', help='reference clock')
    p.add_argument('--edge', choices=['pos', 'neg'], default='pos')
    p.add_argument('--start', metavar='TIME|@CYCLE',
                   help="window start: a time such as 1200ns, or @N for the N-th edge (0-based); default first edge")
    p.add_argument('-n', '--cycles', type=int, required=True)
    p.add_argument('--sample', choices=['mid', 'pre'], default='mid',
                   help='mid: half a cycle after the edge (default); pre: just before the next edge')
    p.add_argument('--radix', choices=['hex', 'bin', 'dec', 'sdec'], default='hex')
    p.add_argument('--color', choices=['none', 'value', 'signal'], default='none')
    p.add_argument('--group-by-scope', action='store_true')
    p.add_argument('--strip-prefix', default='', metavar='PREFIX')
    p.add_argument('--alias', metavar='FILE', help='JSON object: path -> display name')
    p.add_argument('--max-signals', type=int, default=32, help='default 32, at most %d' % HARD_MAX_SIGNALS)
    p.add_argument('--max-cycles', type=int, default=128, help='default 128, at most %d' % HARD_MAX_CYCLES)
    p.add_argument('--truncate', action='store_true', help='cut down to the limits instead of failing')
    p.add_argument('--mark-glitch', action='store_true', help="draw cycles with 2+ transitions as 'x'")
    p.add_argument('--hscale', type=int, choices=[1, 2, 3], help='default: derived from the longest data label')
    p.add_argument('--backend', choices=['auto', 'ffr', 'fsdb2vcd', 'vcd'], default='auto')
    p.add_argument('--fsdb2vcd-args', default='', metavar='ARGS',
                   help='extra arguments for fsdb2vcd, e.g. to limit scope / time range')
    p.add_argument('-o', '--output', metavar='FILE', help='default stdout')
    p.add_argument('--pretty', action='store_true')
    p.add_argument('--version', action='version', version='fsdb2wave ' + __version__)
    return p


def _read_lines(path: str) -> list[str]:
    try:
        with open(path, encoding='utf-8') as f:
            return [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith('#')]
    except OSError as err:
        raise Fsdb2WaveError(INPUT, 'cannot read %s: %s' % (path, err.strerror))


def _read_alias(path: str) -> dict:
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError) as err:
        raise Fsdb2WaveError(INPUT, 'cannot read alias file %s: %s' % (path, err))
    if not isinstance(data, dict):
        raise Fsdb2WaveError(INPUT, 'alias file must hold a JSON object')
    return {str(k): str(v) for k, v in data.items()}


def run(argv: list[str]) -> dict:
    args = build_parser().parse_args(argv)
    signals = list(args.signal) + (_read_lines(args.signals_file) if args.signals_file else [])
    if not signals:
        raise Fsdb2WaveError(INPUT, 'no signals selected (use -s or --signals-file)')
    source, backend = open_source(args.input, args.backend, args.fsdb2vcd_args)
    try:
        opts = Options(
            signals=signals, clock=args.clock, cycles=args.cycles, edge=args.edge,
            sample=args.sample, radix=args.radix, color=args.color,
            group_by_scope=args.group_by_scope, strip_prefix=args.strip_prefix,
            alias=_read_alias(args.alias) if args.alias else {},
            max_signals=args.max_signals, max_cycles=args.max_cycles,
            truncate=args.truncate, mark_glitch=args.mark_glitch, hscale=args.hscale,
            source_name=os.path.basename(args.input), backend=backend)
        if args.start:
            start = args.start.strip()
            if start.startswith('@'):
                try:
                    opts.start_cycle = int(start[1:])
                except ValueError:
                    raise Fsdb2WaveError(INPUT, 'bad --start %r, expected @N' % start)
            else:
                opts.start_time = parse_time(start, source.header.tick_fs)
        result = convert(source, opts)
    finally:
        source.close()

    text = json.dumps(result, indent=2 if args.pretty else None, ensure_ascii=False)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(text + '\n')
    else:
        sys.stdout.write(text + '\n')
    return result


def main(argv: list[str] | None = None) -> int:
    try:
        run(sys.argv[1:] if argv is None else argv)
    except Fsdb2WaveError as err:
        sys.stderr.write(json.dumps(err.to_dict(), ensure_ascii=False) + '\n')
        return err.code
    return 0
