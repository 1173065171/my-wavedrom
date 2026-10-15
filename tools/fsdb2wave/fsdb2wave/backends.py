"""Waveform backends.

Every backend exposes the same small interface as VcdSource:

    source.header.tick_fs          femtoseconds per time tick
    source.header.vars             list of VarInfo(path, code, width, kind)
    source.changes(codes)          iterator of (time, code, value), time ordered
    source.close()

Backends:
  vcd       plain VCD file (no license needed; used by the tests)
  fsdb2vcd  FSDB converted with Verdi's fsdb2vcd utility, then read as VCD
  ffr       native reader built on Verdi's FsdbReader, provided as the optional
            Python module `fsdb2wave_ffr`; it must implement
                fsdb2wave_ffr.open(path) -> object with the interface above
            (value strings normalized exactly as in vcd.py)
"""

from __future__ import annotations

import importlib
import os
import shlex
import shutil
import subprocess
import tempfile

from .errors import Fsdb2WaveError, BACKEND, INPUT
from .vcd import VcdSource


def _ffr_module():
    try:
        return importlib.import_module('fsdb2wave_ffr')
    except ImportError:
        return None


class _TempVcd(VcdSource):
    def __init__(self, path: str, tmpdir: str):
        self._tmpdir = tmpdir
        super().__init__(path)

    def close(self) -> None:
        super().close()
        shutil.rmtree(self._tmpdir, ignore_errors=True)


def _fsdb2vcd(path: str, extra_args: str) -> VcdSource:
    exe = os.environ.get('FSDB2VCD', 'fsdb2vcd')
    if shutil.which(exe) is None:
        raise Fsdb2WaveError(BACKEND, 'fsdb2vcd not found (install Verdi or set FSDB2VCD); '
                                      'alternatively build the fsdb2wave_ffr module')
    tmpdir = tempfile.mkdtemp(prefix='fsdb2wave-')
    out = os.path.join(tmpdir, 'dump.vcd')
    cmd = [exe, path, '-o', out] + shlex.split(extra_args or '')
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    except OSError as err:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise Fsdb2WaveError(BACKEND, 'cannot run fsdb2vcd: %s' % err)
    if proc.returncode != 0 or not os.path.exists(out):
        shutil.rmtree(tmpdir, ignore_errors=True)
        detail = (proc.stderr or proc.stdout or '').strip().splitlines()[-1:] or ['']
        code = BACKEND if 'licen' in detail[0].lower() else INPUT
        raise Fsdb2WaveError(code, 'fsdb2vcd failed (exit %d): %s' % (proc.returncode, detail[0]))
    return _TempVcd(out, tmpdir)


def open_source(path: str, backend: str = 'auto', fsdb2vcd_args: str = ''):
    """Return (source, backend_name)."""
    if not os.path.exists(path):
        raise Fsdb2WaveError(INPUT, 'file not found: %s' % path)
    if backend == 'auto':
        if path.lower().endswith('.vcd'):
            backend = 'vcd'
        elif _ffr_module() is not None:
            backend = 'ffr'
        else:
            backend = 'fsdb2vcd'
    if backend == 'vcd':
        return VcdSource(path), 'vcd'
    if backend == 'fsdb2vcd':
        return _fsdb2vcd(path, fsdb2vcd_args), 'fsdb2vcd'
    if backend == 'ffr':
        mod = _ffr_module()
        if mod is None:
            raise Fsdb2WaveError(BACKEND, 'ffr backend unavailable: module fsdb2wave_ffr is not installed')
        return mod.open(path), 'ffr'
    raise Fsdb2WaveError(INPUT, 'unknown backend: %s' % backend)
