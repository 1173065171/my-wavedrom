"""Time units: everything is converted to integer femtoseconds."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from .errors import Fsdb2WaveError, INPUT

UNITS = [('s', 10 ** 15), ('ms', 10 ** 12), ('us', 10 ** 9), ('ns', 10 ** 6), ('ps', 10 ** 3), ('fs', 1)]
UNIT_FS = dict(UNITS)

_TIME_RE = re.compile(r'^\s*([0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)\s*([a-z]*)\s*$')


def parse_timescale(text: str) -> int:
    """'1ns', '1 ns', '10ps' -> femtoseconds per tick."""
    m = _TIME_RE.match(text.replace('µ', 'u').lower())
    if not m or m.group(2) not in UNIT_FS:
        raise Fsdb2WaveError(INPUT, 'cannot parse timescale: %r' % text)
    return int(Decimal(m.group(1)) * UNIT_FS[m.group(2)])


def parse_time(text: str, tick_fs: int) -> int:
    """'1200ns', '1.5us' or a bare tick count -> ticks."""
    m = _TIME_RE.match(text.lower())
    if not m:
        raise Fsdb2WaveError(INPUT, 'cannot parse time: %r' % text)
    try:
        value = Decimal(m.group(1))
    except InvalidOperation:
        raise Fsdb2WaveError(INPUT, 'cannot parse time: %r' % text)
    unit = m.group(2)
    if unit == '':
        return int(value)
    if unit not in UNIT_FS:
        raise Fsdb2WaveError(INPUT, 'unknown time unit in %r (use fs ps ns us ms s)' % text)
    return int((value * UNIT_FS[unit] / tick_fs).to_integral_value())


def fmt_time(ticks: float, tick_fs: int) -> str:
    """Ticks -> shortest exact string such as '1200ns' or '1.5us'."""
    fs = Decimal(str(ticks)) * tick_fs
    if fs == 0:
        return '0' + _unit_name(tick_fs)
    for name, scale in UNITS:
        value = fs / scale
        if abs(value) >= 1 and value == value.quantize(Decimal('0.001')):
            text = format(value.normalize(), 'f')
            return text + name
    return format(fs.normalize(), 'f') + 'fs'


def _unit_name(tick_fs: int) -> str:
    for name, scale in UNITS:
        if tick_fs >= scale:
            return name
    return 'fs'
