"""Streaming VCD reader.

The header is parsed eagerly (it is small); value changes are streamed and
filtered by identifier code, so only the selected signals cost anything and
reading stops as soon as the caller closes the generator.

Values are normalized to strings:
  scalars   '0' '1' 'x' 'z'
  vectors   bit string, MSB first, e.g. '1010', 'x1z0' (not yet padded)
  reals     'r' + number, e.g. 'r1.5'
  strings   's' + text
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterator

from .errors import Fsdb2WaveError, INPUT
from .timeutil import parse_timescale

_RANGE_RE = re.compile(r'\[\s*-?\d+\s*:\s*-?\d+\s*\]$')


@dataclass
class VarInfo:
    path: str          # hierarchical path, dot separated, without [msb:lsb]
    code: str          # identifier code shared by aliases
    width: int
    kind: str          # 'logic' | 'real' | 'event' | 'string'


@dataclass
class Header:
    tick_fs: int = 10 ** 6     # default 1ns when $timescale is missing
    vars: list[VarInfo] = field(default_factory=list)


def normalize_path(path: str) -> str:
    """Drop a trailing [msb:lsb] range; single-bit selects such as bus[3] stay."""
    return _RANGE_RE.sub('', path.strip()).strip()


def _kind(var_type: str) -> str:
    if var_type in ('real', 'realtime', 'shortreal'):
        return 'real'
    if var_type == 'event':
        return 'event'
    if var_type == 'string':
        return 'string'
    return 'logic'


def _tokens(stream) -> Iterator[str]:
    for line in stream:
        for tok in line.split():
            yield tok


class VcdSource:
    """Backend over a VCD file (also used for FSDB converted by fsdb2vcd)."""

    def __init__(self, path: str):
        self.path = path
        try:
            self._stream = open(path, 'r', encoding='utf-8', errors='replace')
        except OSError as err:
            raise Fsdb2WaveError(INPUT, 'cannot open %s: %s' % (path, err.strerror))
        self._tokens = _tokens(self._stream)
        self.header = self._parse_header()

    def close(self) -> None:
        self._stream.close()

    def _block(self) -> list[str]:
        res = []
        for tok in self._tokens:
            if tok == '$end':
                return res
            res.append(tok)
        raise Fsdb2WaveError(INPUT, '%s: unexpected end of file in header' % self.path)

    def _parse_header(self) -> Header:
        header = Header()
        scopes: list[str] = []
        for tok in self._tokens:
            if tok == '$enddefinitions':
                self._block()
                return header
            if tok == '$timescale':
                header.tick_fs = parse_timescale(''.join(self._block()))
            elif tok == '$scope':
                body = self._block()
                scopes.append(body[1] if len(body) > 1 else body[0])
            elif tok == '$upscope':
                self._block()
                if scopes:
                    scopes.pop()
            elif tok == '$var':
                body = self._block()
                if len(body) < 4:
                    raise Fsdb2WaveError(INPUT, '%s: malformed $var %s' % (self.path, ' '.join(body)))
                var_type, width, code = body[0], body[1], body[2]
                name = body[3]
                if len(body) > 4 and not _RANGE_RE.match(body[4]):
                    name += body[4]          # e.g. 'bus' '[3]' -> 'bus[3]'
                try:
                    width_n = int(width)
                except ValueError:
                    width_n = 1
                path = normalize_path('.'.join(scopes + [name]))
                header.vars.append(VarInfo(path, code, width_n, _kind(var_type)))
            elif tok.startswith('$'):
                self._block()                # $date $version $comment ...
        raise Fsdb2WaveError(INPUT, '%s: no $enddefinitions, not a VCD file?' % self.path)

    def changes(self, codes: set[str]) -> Iterator[tuple[int, str, str]]:
        """Yield (time, code, value) for the selected codes, in file order."""
        time = 0
        toks = self._tokens
        for tok in toks:
            c = tok[0]
            if c == '#':
                try:
                    time = int(tok[1:])
                except ValueError:
                    raise Fsdb2WaveError(INPUT, '%s: bad timestamp %r' % (self.path, tok))
            elif c in '01xzXZ':
                code = tok[1:]
                if code in codes:
                    yield time, code, c.lower()
            elif c in 'bBrRsS':
                code = next(toks, None)
                if code is None:
                    return
                if code in codes:
                    if c in 'bB':
                        yield time, code, tok[1:].lower()
                    else:
                        yield time, code, c.lower() + tok[1:]
            elif c == '$':
                if tok == '$comment':
                    for t in toks:
                        if t == '$end':
                            break
                # $dumpvars / $dumpall / $dumpon / $dumpoff / $end: markers only
