"""Generate the VCD fixtures used by the tests (deterministic, no simulator needed).

    python3 tests/make_fixtures.py      # rewrites tests/fixtures/*.vcd
"""

from __future__ import annotations

import os

HERE = os.path.dirname(os.path.abspath(__file__))

VARS = [
    # scope path, var type, width, code, name, range
    ('tb.dut', 'wire', 1, '!', 'clk', None),
    ('tb.dut', 'reg', 1, '"', 'rst_n', None),
    ('tb.dut', 'reg', 1, '#', 'valid', None),
    ('tb.dut', 'reg', 1, '$', 'ready', None),
    ('tb.dut', 'reg', 32, '%', 'addr', '[31:0]'),
    ('tb.dut', 'reg', 8, '&', 'data', '[7:0]'),
    ('tb.dut', 'wire', 8, "'", 'bus_z', '[7:0]'),
    ('tb.dut', 'reg', 1, '(', 'clk_div2', None),
    ('tb.dut', 'reg', 1, ')', 'glitchy', None),
    ('tb.dut', 'wire', 1, '*', 'gclk', None),
    ('tb.dut', 'real', 64, '+', 'temp', None),
    ('tb.dut', 'event', 1, ',', 'ev', None),
    ('tb.dut', 'wire', 1, '!', 'clk_alias', None),        # alias of clk
    ('tb.dut.u_fifo', 'reg', 1, '-', 'full', None),
    ('tb.dut.u_fifo', 'reg', 4, '.', 'count', '[3:0]'),
]

PERIOD = 10000      # ticks of 1ps -> 10ns


def _scalar(v, code):
    return '%s%s' % (v, code)


def _vector(bits, code):
    return 'b%s %s' % (bits, code)


def build_events(cycles=40):
    """Return {time: [value-change strings]} for a small handshake design."""
    ev: dict[int, list[str]] = {}

    def at(t, s):
        ev.setdefault(t, []).append(s)

    half = PERIOD // 2
    # initial values
    at(0, _scalar('0', '!'))
    at(0, _scalar('0', '"'))
    at(0, _scalar('0', '#'))
    at(0, _scalar('x', '$'))
    at(0, _vector('x', '%'))
    at(0, _vector('x', '&'))
    at(0, _vector('z', "'"))
    at(0, _scalar('0', '('))
    at(0, _scalar('0', ')'))
    at(0, _scalar('0', '*'))
    at(0, 'r20.5 +')
    at(0, _scalar('0', '-'))
    at(0, _vector('0', '.'))

    for k in range(cycles):
        rise = 5000 + k * PERIOD           # rising edges at 5ns, 15ns, ...
        at(rise, _scalar('1', '!'))
        at(rise + half, _scalar('0', '!'))
        # divided clock toggles on every rising edge
        at(rise, _scalar('1' if k % 2 == 0 else '0', '('))
        # gated clock: runs only in cycles 4..7
        if 4 <= k <= 7:
            at(rise, _scalar('1', '*'))
            at(rise + half, _scalar('0', '*'))
        # registered signals change on the rising edge (zero delay)
        if k == 2:
            at(rise, _scalar('1', '"'))
            at(rise, _scalar('0', '$'))
        if k == 3:
            at(rise, _scalar('1', '#'))
            at(rise, _vector('1000', '%'))
            at(rise, _vector('10100101', '&'))
        if k == 4:
            at(rise, _scalar('1', '$'))
        if k == 5:
            at(rise, _vector('1100', '%'))
            at(rise, _vector('1x0x0000', '&'))      # partially unknown
            at(rise, _vector('11110000', "'"))
        if k == 6:
            at(rise, _scalar('0', '#'))
            at(rise, _vector('x', '%'))
            at(rise, _vector('z', "'"))
            at(rise, 'r21.25 +')
            at(rise, _scalar('1', ','))
        if k == 7:
            at(rise + 2000, _scalar('1', ')'))      # glitch inside one cycle
            at(rise + 3000, _scalar('0', ')'))
        if k == 8:
            at(rise, _scalar('1', '-'))
        if 2 <= k <= 9:
            at(rise, _vector(format(k - 2, 'b'), '.'))
    return ev


def write_vcd(path, cycles=40, shuffle_same_time=False):
    ev = build_events(cycles)
    lines = ['$date today $end', '$version make_fixtures $end', '$timescale 1ps $end']
    current: list[str] = []
    for scope, typ, width, code, name, rng in VARS:
        parts = scope.split('.')
        common = 0
        while common < min(len(parts), len(current)) and parts[common] == current[common]:
            common += 1
        for _ in range(len(current) - common):
            lines.append('$upscope $end')
        for p in parts[common:]:
            lines.append('$scope module %s $end' % p)
        current = parts
        lines.append('$var %s %d %s %s%s $end' % (typ, width, code, name, (' ' + rng) if rng else ''))
    for _ in current:
        lines.append('$upscope $end')
    lines.append('$enddefinitions $end')
    lines.append('$comment generated $end')
    for t in sorted(ev):
        lines.append('#%d' % t)
        changes = ev[t]
        if t == 0:
            lines.append('$dumpvars')
        if shuffle_same_time:
            changes = list(reversed(changes))     # clock edge after the data changes
        lines.extend(changes)
        if t == 0:
            lines.append('$end')
    with open(path, 'w') as f:
        f.write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    out = os.path.join(HERE, 'fixtures')
    os.makedirs(out, exist_ok=True)
    write_vcd(os.path.join(out, 'handshake.vcd'))
    write_vcd(os.path.join(out, 'handshake_reordered.vcd'), shuffle_same_time=True)
    print('written to', out)
