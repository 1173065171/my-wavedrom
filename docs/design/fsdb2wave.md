# 设计稿：fsdb2wave —— FSDB 转 WaveJSON

目标：从仿真产生的 FSDB 文件中，按受约束的范围（信号数、cycle 数）截取一段波形，转换成 WaveDrom 可渲染的 WaveJSON，供 CLI 使用和 TS agent 调用。

## 1. 边界与前提

- FSDB 是 Synopsys Verdi 的私有格式，只能通过 Verdi 自带的 FsdbReader（FFR，C++）或 `fsdb2vcd` 工具读取。运行环境必须是装有 Verdi 且有 License 的 Linux 主机，不能在浏览器或 WASM 中运行。
- WaveDrom 以 cycle 为单位描述波形，FSDB 以事件（时间戳 + 值）记录。转换本质是**按参考时钟采样**，cycle 之内的毛刺和精确时刻会丢失，这些信息写入 `meta.warnings` 告知调用方。
- 输出只承诺 WaveJSON 的 `signal` 子集，不生成 `edge`/`node` 标注（标注由 agent 或用户后续添加）。

## 2. 架构

```
           ┌─────────────── backend（可替换）───────────────┐
FSDB ──►   │ ffr：C++ 直接读（pybind11 暴露给 Python）     │ ──► SignalTrace[]
           │ vcd：fsdb2vcd 导出子集 → VCD 解析             │     {path, width, type,
VCD  ──►   │ vcd：直接解析（无 Verdi 环境，用于测试/开源仿真）│      changes:[(t, value)]}
           └───────────────────────────────────────────────┘
                                   │
                    Window（时间窗、时钟沿列表）
                                   │
                    Sampler（每 cycle 取一个值 + 统计跳变次数）
                                   │
                    Mapper（值 → wave 字符 / data）
                                   │
                    Emitter（WaveJSON + meta，JSON 输出到 stdout 或文件）
```

- 核心（Window/Sampler/Mapper/Emitter）用 Python 实现，与 backend 解耦。
- `ffr` backend 是唯一依赖 Verdi 的部分；`vcd` backend 不依赖 License，CI 用 VCD 测试夹具覆盖全部核心逻辑。
- FFR 读取流程大致为：打开文件 → 读 scope/var 树解析信号句柄 → 只把选中信号加入加载列表 → 为每个信号创建值变化遍历句柄 → 定位到窗口起点逐个读取值变化。具体 API 以所装 Verdi 版本附带的 FsdbReader 示例为准。
- `vcd` backend 读 FSDB 时先调用 `fsdb2vcd` 只导出选中信号和时间窗口，避免生成整份 VCD。

## 3. CLI 设计

```
fsdb2wave <input.fsdb|input.vcd>
  -s, --signal <path>        信号层次路径，可重复；支持通配 tb.dut.u_axi.*
      --signals-file <file>  每行一个路径，# 开头为注释
  -c, --clock <path>         参考时钟（必填）
      --edge pos|neg         采样沿，默认 pos
      --start <time|@cycle>  起点：1200ns，或 @15（第 15 个有效沿），默认第一个沿
  -n, --cycles <N>           截取 cycle 数（必填）
      --sample mid|pre       采样点：mid=沿后半周期（默认，与显示一致）；pre=下个沿前一刻（寄存器视角）
      --radix hex|bin|dec|sdec  总线显示进制，默认 hex
      --color none|value|signal 数据格着色：none 全用 '='（默认）；value 按值哈希到 2..9；signal 按信号固定一色
      --group-by-scope       按层次分组输出嵌套数组
      --strip-prefix <p>     名称去掉公共前缀
      --alias <file>         路径 → 显示名 映射（JSON）
      --max-signals <N>      默认 32，硬上限 128
      --max-cycles <N>       默认 128，硬上限 1024
      --truncate             超限时截断并告警，而非报错
      --backend auto|ffr|vcd 默认 auto：.fsdb 优先 ffr，不可用时退回 vcd
  -o, --output <file>        默认 stdout
      --pretty               缩进输出
```

退出码：

| 码 | 含义 |
|---|---|
| 0 | 成功（可能带 warnings） |
| 1 | 参数错误、文件读取 / 解析失败、窗口内时钟沿不足 2 个 |
| 2 | 违反约束（信号数、cycle 数超限，且未指定 `--truncate`） |
| 3 | 信号或时钟路径不存在（错误信息列出最相近的候选路径） |
| 4 | backend 不可用（未找到 Verdi 库 / `fsdb2vcd`，或无 License） |

错误输出统一为 stderr 上的一行 JSON：`{"code":3,"message":"...","candidates":[...]}`，方便 agent 解析后自动修正参数重试。

## 4. 约束检查（在读取前完成）

1. 解析信号列表、展开通配，计数 > `max-signals` → 退出码 2（或 `--truncate` 保留前 N 个）。
2. `--cycles` > `max-cycles` → 同上。
3. 只为选中信号创建读取句柄，时间窗口 = `[起点沿, 起点沿 + (N+1) 个周期)`，多读一个周期用于判断最后一格的取值。
4. 单个总线宽度 > 128 bit 时告警，`data` 以截断形式显示（如 `'h1f…3a`）。

“先限定再读取”保证大 FSDB（数 GB）上的耗时只与选中范围相关。

## 5. 时钟与周期

- 从参考时钟的值变化中提取有效沿时刻 `e[0..N]`，周期 `T` 取中位数；沿间隔偏离中位数超过 10% 时记 warning（时钟门控、频率切换）。
- 参考时钟本身输出 `wave: "p" + "."*(N-1)`（`--edge neg` 时为 `n`）。
- 其他被识别为时钟的信号（通过 `-s` 选中、且周期为参考周期整数倍 k）输出 `p` 并设置 `period: k`；非整数倍时按普通信号采样并告警。

## 6. 采样与映射规则

对每个信号、每个 cycle i，在采样点 `t_i` 取值（`mid`：`e[i] + T/2`；`pre`：`e[i+1] - ε`），并统计区间 `[e[i], e[i+1])` 内的跳变次数。

**单 bit 信号**

| 采样值 | 与上一格相同 | 字符 |
|---|---|---|
| 0 / 1 | 否 | `0` / `1` |
| x / z | 否 | `x` / `z` |
| 任意 | 是 | `.` |

**多 bit 总线**

| 采样值 | 字符 | data |
|---|---|---|
| 与上一格相同 | `.` | — |
| 全 x / 全 z | `x` / `z` | — |
| 确定值 | `=`（或按 `--color` 取 `2`…`9`） | 按 radix 格式化，如 `"3A"` |
| 部分 x/z | `=` | 按位保留，如 `"h3x"`（hex 某 nibble 含 x 则该位显示 x） |

**其他类型**：real → `=` + `%.4g` 格式化；enum（SV）→ `=` + 枚举名；event / string 类型跳过并告警。

**cycle 内多次跳变**：仍取采样点的值；跳变次数 ≥ 2 的格子记入 `meta.warnings`（`{signal, cycle, transitions}`）。可选 `--mark-glitch`：把该格输出为 `x` 以显式提示。

## 7. 输出格式

```json5
{
  signal: [
    { name: "clk",      wave: "p......." },
    { name: "valid",    wave: "0.1..0.." },
    { name: "addr",     wave: "x.===.x.", data: ["1000", "1004", "1008"] },
    [ "u_fifo",
      { name: "full",   wave: "0....1.." }
    ]
  ],
  head: { text: "tb.dut  1200ns – 2000ns", tick: 15 },
  config: { hscale: 1 },
  meta: {
    source: "sim.fsdb",
    backend: "ffr",
    clock: { path: "tb.dut.clk", edge: "pos", period: "10ns" },
    window: { start: "1200ns", end: "2000ns", startCycle: 15, cycles: 8 },
    sample: "mid",
    radix: "hex",
    warnings: [
      { kind: "multi-transition", signal: "tb.dut.valid", cycle: 3, transitions: 2 }
    ]
  }
}
```

- `head.tick` 设为起始 cycle 号，渲染出的刻度与仿真 cycle 对齐。
- `meta` 是扩展字段，WaveDrom 渲染时忽略（`lib/render-any.js` 只识别 `signal`/`assign`/`reg`），agent 可以读取它来解释波形或决定下一步截取范围。
- `hscale` 根据最长 `data` 文本自动取 1–3，避免数据格中文字溢出。

## 8. 与 TS agent 项目的集成

agent 侧注册一个工具，内部以子进程调用 CLI（或部署在 Verdi 主机上的 HTTP 包装）：

```ts
interface Fsdb2WaveArgs {
  file: string;
  signals: string[];
  clock: string;
  start?: string;      // "1200ns" | "@15"
  cycles: number;
  radix?: 'hex' | 'bin' | 'dec' | 'sdec';
}
type Fsdb2WaveResult =
  | { ok: true;  wave: WaveJSON; warnings: Warning[] }
  | { ok: false; code: 1 | 2 | 3 | 4; message: string; candidates?: string[] };
```

返回的 `wave` 直接交给前端的 `<wave-view>` 组件渲染（见 `theming.md`）。错误码 2/3 让 agent 能自动缩小范围或修正信号路径后重试。

## 9. 测试计划

- 用 iverilog / Verilator 生成若干 VCD 夹具：单 bit、总线、x/z、门控时钟、分频时钟、cycle 内毛刺。
- 对每个夹具做 WaveJSON 快照测试，并把输出交给 `lib/index.js` 的 `renderAny` 渲染，确保产物可渲染。
- 在有 Verdi 的机器上，用同一设计生成 FSDB，验证 `ffr` 与 `vcd` 两个 backend 的输出逐字节一致。
- 约束测试：超限报错 / `--truncate` 截断、路径不存在时的候选提示、backend 缺失时退出码 4。

## 10. 实施记录（第一轮）

代码在 `tools/fsdb2wave/`（Python ≥ 3.8，仅标准库），用法见该目录 README。

- **已实现**：VCD backend（流式读取，按标识码过滤，读到窗口最后一个沿即停止）、`fsdb2vcd` backend（调用外部工具转出 VCD 后读取）、第 3 节全部 CLI 参数、退出码与 stderr JSON、第 4–7 节的约束、采样、映射和输出格式。另提供 Node 封装 `tools/fsdb2wave/node`（带 `.d.ts`），供 TS agent 以子进程方式调用。
- **未实现**：`ffr` backend 只定义了接口（可选模块 `fsdb2wave_ffr`，见 `backends.py`），C++/pybind11 实现需要在装有 Verdi 的机器上按所装版本的 FsdbReader API 编写和验证。
- **同一时间戳整体处理**：读取时按时间戳成组处理变化，时钟沿与同一时刻的数据变化不论在文件里谁先谁后，都落在窗口起点的同一侧（测试用倒序夹具验证）。
- **门控时钟**：在某个 cycle 内恰好是“沿上升 + 周期中段下降”的 1 bit 信号，输出该 cycle 为 `p`（反相为 `n`）；同一信号的其余电平改用 `l`/`h`，与 `p` 衔接时不会出现 `0`/`1` 的过渡斜线。自由运行且与窗口对齐的分频时钟仍输出 `p`/`n` + `period: k`。
- **部分 x 的总线**：hex 每 4 bit 一位，含 x 的位显示 `x`、全 z 显示 `z`，不加 `h` 前缀；前导 0 省略。超过 16 个字符的标签中间省略并记 `bus-truncated`。
- **`--start @N`**：N 是从 0 开始的有效沿序号，与 `head.tick` 一致。
- **性能**：纯 Python 读取 VCD 约 7MB/s。窗口靠前时只读文件头部（9MB 文件、窗口在开头时 0.07s，在末尾时 1.25s）；GB 级 FSDB 需要 `ffr` backend 才能做到只读选中范围。
- **测试**：`tests/make_fixtures.py` 生成确定性的 VCD 夹具，覆盖握手、总线、部分 x、高阻、real、event、别名、分频/门控时钟和毛刺；18 个 unittest，其中一项把输出交给 `lib/index.js` 的 `renderAny` 确认可渲染。CI 新增 Python 3.8 / 3.12 任务。
