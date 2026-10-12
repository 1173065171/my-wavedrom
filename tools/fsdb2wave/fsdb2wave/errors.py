"""Errors carrying the CLI exit code (see docs/design/fsdb2wave.md)."""

from __future__ import annotations

INPUT = 1          # bad arguments, unreadable / malformed input
CONSTRAINT = 2     # signal or cycle limits exceeded
NOT_FOUND = 3      # signal or clock path does not exist
BACKEND = 4        # backend unavailable (no Verdi libraries / fsdb2vcd)


class Fsdb2WaveError(Exception):
    def __init__(self, code: int, message: str, candidates: list[str] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.candidates = candidates or []

    def to_dict(self) -> dict:
        res = {'code': self.code, 'message': self.message}
        if self.candidates:
            res['candidates'] = self.candidates
        return res
