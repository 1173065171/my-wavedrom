# fsdb2wave

Cut a bounded window (signal count × cycle count) out of an FSDB or VCD dump,
sample it on a reference clock and emit WaveDrom WaveJSON. Pure Python ≥ 3.8,
standard library only. Design: [`docs/design/fsdb2wave.md`](../../docs/design/fsdb2wave.md).

```bash
cd tools/fsdb2wave
python3 -m fsdb2wave sim.vcd -c tb.dut.clk -s 'tb.dut.u_axi.*' -n 32 --start @100 \
    --strip-prefix tb.dut --group-by-scope --pretty > window.json
npx wavedrom -i window.json > window.svg         # from the repository root
# or: pip install tools/fsdb2wave  ->  fsdb2wave ...
```

## Backends

| backend | input | needs |
|---|---|---|
| `vcd` | `.vcd` | nothing |
| `fsdb2vcd` | `.fsdb` | Verdi `fsdb2vcd` on `PATH` (or `FSDB2VCD=/path/to/fsdb2vcd`) and a license |
| `ffr` | `.fsdb` | the native module `fsdb2wave_ffr` (FsdbReader based, built on a Verdi host) |

`--backend auto` (default) picks `vcd` for `.vcd`, otherwise `ffr` when the
module is importable, otherwise `fsdb2vcd`.

- `fsdb2vcd` converts the whole file unless you narrow it with
  `--fsdb2vcd-args '...'` (scope / time-range options of your Verdi version).
  The VCD reader stops at the end of the window, but conversion cost is paid up front.
- `fsdb2wave_ffr` is not part of this repository yet. It must provide
  `open(path)` returning an object with `header.tick_fs`, `header.vars`
  (`VarInfo(path, code, width, kind)`), `changes(codes)` yielding time-ordered
  `(time, code, value)` and `close()`, with values normalized as in `fsdb2wave/vcd.py`.

## Output

- Reference clock first (`p`/`n`), then the selected signals in selection order.
- Values are sampled half a cycle after each edge (`--sample mid`, matches how
  WaveDrom draws a cycle) or just before the next edge (`--sample pre`).
- 1-bit: `0 1 x z`, `.` while unchanged. Free-running clocks aligned to the window
  become `p`/`n` with `period: k`; gated clocks become per-cycle `p` with `l`/`h` levels.
- Buses: `=` (or `2`…`9` with `--color`) plus `data` in `--radix`; all-x / all-z
  become `x` / `z`; a hex digit whose bits include x shows as `x`, all-z as `z` (e.g. `1x0`).
- `head.tick` is the start cycle, `config.hscale` fits the longest label,
  `meta` (ignored by WaveDrom) records source, clock, window and `warnings`
  (`multi-transition`, `clock-irregular`, `window-truncated`, ...).

## Exit codes

stderr carries one JSON line `{"code", "message", "candidates"?}`.

| code | meaning |
|---|---|
| 0 | success (may carry warnings) |
| 1 | bad arguments, unreadable input, not enough clock edges |
| 2 | limits exceeded (`--max-signals` default 32 / hard 128, `--max-cycles` default 128 / hard 1024) without `--truncate` |
| 3 | signal or clock path not found (`candidates` lists close matches) |
| 4 | backend unavailable (no `fsdb2vcd`, no `fsdb2wave_ffr`, license failure) |

## From TypeScript / Node

```ts
import { fsdb2wave } from './tools/fsdb2wave/node';

const res = await fsdb2wave(
  { file: 'sim.fsdb', clock: 'tb.dut.clk', signals: ['tb.dut.valid', 'tb.dut.addr'], cycles: 32, start: '@100' },
  { cwd: 'tools/fsdb2wave', timeout: 60_000 });
if (res.ok) waveView.source = res.wave;       // <wave-view> from wavedrom/wave-view
else if (res.code === 3) retryWith(res.candidates);
```

## Tests

```bash
python3 -m unittest discover -s tools/fsdb2wave/tests -v
python3 tools/fsdb2wave/tests/make_fixtures.py     # regenerate the VCD fixtures
```
