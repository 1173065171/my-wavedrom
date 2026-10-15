# 设计稿：皮肤改造为 CSS 变量主题

目标：WaveDrom 以内联 SVG 嵌入 TS 主项目（悬浮面板 / Web Component）时，配色、字体、线宽跟随主项目的设计 token，切换亮/暗主题不需要换皮肤、不需要重新渲染。

## 1. 现状问题（基于 3.6.2 代码）

| # | 问题 | 位置 | 嵌入后的后果 |
|---|---|---|---|
| P1 | 皮肤 `<style>` 是全局、无作用域的，含 `text{font-family:Helvetica;...}`、`.info`、`.error` 等通用选择器 | `skins/*.js`（由 `unpacked/skins/*.svg` 生成） | 内联到页面后污染主项目所有 SVG 文本和同名 class |
| P2 | 第一张图携带完整 `<defs>`（224 个 id，约 43KB），后续图 `notFirstSignal` 为真时只有空壳，靠 `xlink:href="#xxx"` 引用第一张图的 defs | `lib/insert-svg-template.js:16-18`、`lib/render-wave-lane.js:14`、`lib/render-gaps.js:29` | 动态面板里删除第一张图，其余图全部失去图元；同页两种皮肤 id 冲突 |
| P3 | 颜色硬编码在渲染代码里：背景 `fill:white`，箭头 `#0041c4`、`#00F`、`#F00` | `lib/insert-svg-template.js:30`、`lib/arc-shape.js:43-107`、`lib/arcs.js` | 暗色主题下出现白底、蓝色箭头 |
| P4 | `sN` class 是 Inkscape 导出时的流水号，不同皮肤编号语义不同（default 的 `.s3` 是点线，dark 的 `.s3` 是 0.5px 细线） | `skins/*.js` | 无法写一份通用覆盖样式；每加一套配色就要复制整份 43KB 皮肤 |
| P5 | 字体 Helvetica、字号 11pt 写死；文字宽度靠 `char-width.json` 估算 | 皮肤 `<style>`、`lib/text-width.js` | 换主项目字体后标签宽度估算偏差 |

## 2. 方案总览

> 实现时改为运行时转换（`lib/theme.js`），不再改 `svg2js.js`，见第 10 节。

```
unpacked/skins/default.svg
        │  bin/svg2js.js（扩展：class 语义化 + 颜色替换为 var()）
        ▼
skins/themeable.js      ← 唯一几何皮肤，颜色全部走 CSS 变量
        │
        ├─ defs 精灵：页面只注入一次 <svg id="wd-sprite" hidden>，id 统一加前缀 wd-
        ├─ 样式表：wavedrom.css，所有选择器限定在 .wd-root 下
        └─ 每张图：<svg class="wd-root"> 只含 <use href="#wd-xxx"> 和标签
```

主项目只需要定义一组 `--wd-*` 变量（或映射到自己的 token）。

## 3. 语义化 class（替换 sN）

| 新 class | 含义 | 对应 default 皮肤 |
|---|---|---|
| `wd-line` | 波形主线 | `.s1` |
| `wd-line-thin` | 细线（gap、斜线） | `.s2` |
| `wd-line-dotted` | 网格 / 点线 | `.s3` |
| `wd-line-solid` | 实线辅助 | `.s4` |
| `wd-bg` | 背景填充 | `.s5`、背景 rect |
| `wd-fg-fill` | 实心前景（箭头头部等） | `.s6` |
| `wd-data-2` … `wd-data-9` | `=`/`2`…`9` 数据格填充 | `.s7`…`.s14`（依次对应 `gen-wave-brick.js` 的 `-2`…`-9` 后缀） |
| `wd-x-hatch` | `x` 未知态阴影 | 现由 `s1` 斜线 + 背景组合 |
| `wd-arc` / `wd-arc-label` | 边（edge）箭头与标签 | `.s15`/`.s16` 与 `arc-shape.js` 内联样式 |
| `wd-text` / `wd-muted` / `wd-info` / `wd-warning` / `wd-error` / `wd-success` | 文本与状态色 | 原 `text`、`.muted` 等 |

映射表在 `svg2js.js` 中以一份 JSON 维护，按皮肤分别声明（解决 P4）。

## 4. CSS 变量（主题 token）

```css
.wd-root {
  /* 基础 */
  --wd-fg:            #000;
  --wd-bg:            transparent;   /* 默认透明，直接透出主项目面板底色 */
  --wd-grid:          #ccc;
  --wd-line-width:    1;
  --wd-font-family:   Helvetica, Arial, sans-serif;
  --wd-font-size:     11pt;
  /* 数据格（对应 wave 字符 = 2..9） */
  --wd-data-2: #fff;    --wd-data-3: #ffffb4; --wd-data-4: #ffe0b9; --wd-data-5: #b9e0ff;
  --wd-data-6: #ccfdfe; --wd-data-7: #cdfdc5; --wd-data-8: #f0c1fb; --wd-data-9: #f5c2c0;
  --wd-data-text: var(--wd-fg);
  /* 边与状态 */
  --wd-arc:     #0041c4;
  --wd-muted:   #aaa;
  --wd-info:    #0041c4;
  --wd-warning: #f6b900;
  --wd-error:   #f60000;
  --wd-success: #00ab00;
}

.wd-root .wd-line      { fill: none; stroke: var(--wd-fg); stroke-width: var(--wd-line-width); stroke-linecap: round; }
.wd-root .wd-data-2    { fill: var(--wd-data-2); stroke: none; }
.wd-root text          { fill: var(--wd-fg); font-family: var(--wd-font-family); font-size: var(--wd-font-size); }
.wd-root .wd-arc       { fill: none; stroke: var(--wd-arc); marker-end: url(#wd-arrowhead); }
/* ……其余 class 同理，均限定在 .wd-root 下（解决 P1） */
```

主项目接入示例：

```css
.wd-root {
  --wd-fg:          var(--color-text-primary);
  --wd-bg:          var(--color-surface-raised);
  --wd-grid:        var(--color-border-subtle);
  --wd-font-family: var(--font-mono);
  --wd-arc:         var(--color-accent);
  --wd-data-2:      color-mix(in oklab, var(--color-accent) 18%, transparent);
}
[data-theme="dark"] .wd-root { /* 只改变量，不重新渲染 */ }
```

暗色主题由变量切换完成，`dark` 皮肤不再需要单独维护。

## 5. defs 共享方式（解决 P2）

浏览器中 `<use>` 克隆出的元素会继承 `<use>` 所在位置的 CSS 自定义属性，所以全页只需一份 defs，各图仍能有各自的主题。

- 渲染器新增 `defsMode` 选项：
  - `'sprite'`（Web 默认）：组件首次挂载时向 `document.body` 注入一次隐藏的 `<svg id="wd-sprite">`，引用计数归零时移除。每张图都不含 defs，删除任意一张都不影响其他图。
  - `'inline'`（CLI / 导出默认）：每张 SVG 自带完整 defs，id 加实例前缀 `wd{n}-`，产物自包含。
- 删除 `notFirstSignal` 这一路径，它的作用由 `defsMode` 取代。
- 所有 `#id` 引用（`render-wave-lane.js`、`render-gaps.js`、`arc-shape.js` 的 marker）统一走 `ref(id)` 辅助函数加前缀。

**Shadow DOM 取舍**：`<use href="#...">` 只能引用同一 tree scope 内的 id。如果主项目要求组件用 Shadow DOM 隔离，就只能每个 shadow root 各注入一份 defs（约 43KB/实例，仅几张图时可接受）；否则推荐 Light DOM + `.wd-root` 前缀，依靠第 4 节的选择器作用域隔离。

## 6. 渲染代码中的硬编码颜色（解决 P3）

- `insert-svg-template.js:30` 的背景 rect：`style:'stroke:none;fill:white'` 改为 `class:'wd-bg'`。
- `arc-shape.js` / `arcs.js`：内联 `style` 改为 `class`（`wd-arc`、`wd-arc-tee`、`wd-arc-err`），marker 引用改为带前缀的 id。
- `render-marks.js:75`、`render-groups.js:31` 的 `muted`/`info` 改为 `wd-muted`/`wd-info`。

## 7. 导出（另存为 SVG / PNG）

CSS 变量离开页面后无法解析，导出时需要“固化”：
1. 克隆目标 SVG，把 sprite 中用到的 defs 复制进来（等同于 `inline` 模式）。
2. 对每个带 `wd-*` class 的元素读取 `getComputedStyle`，把 `fill`/`stroke`/`font-*` 写成内联属性。
3. 删除 `class` 和 `var()`，得到自包含的 SVG，再交给现有 `append-save-as-dialog.js` 的 PNG 流程。

CLI 新增 `--theme <file.json>`，接收一份变量表，渲染时直接写入 `<style>` 的 `:root`，产物同样自包含。

## 8. 字体与文字宽度（P5）

- `text-width.js` 新增可注入的测量函数：浏览器端默认用 `canvas.measureText` 按 `--wd-font-family` 的计算值测量，CLI 端继续用 `char-width.json`。
- 等宽字体（如主项目用 `--font-mono`）时可直接用 `字符数 × 单字宽` 的快速路径。

## 9. 实施步骤

1. 扩展 `bin/svg2js.js`：读取 class 映射 JSON，输出语义 class，颜色替换为 `var(--wd-*, 默认值)`，生成 `skins/themeable.js` 与 `skins/wavedrom.css`。
2. 渲染层：引入 `ref()` 前缀函数、`defsMode`，移除 `notFirstSignal`，清理第 6 节的硬编码颜色。
3. Web Component `<wave-view>`：负责 sprite 注入/引用计数、`source` 属性变更时防抖重渲染（约 50ms）。
4. 导出固化逻辑 + CLI `--theme`。
5. 测试：对 `test/*.json5` 做 SVG 快照；用 Playwright 在亮/暗两套变量下截图对比；验证删除第一张图后其余图仍正常。

旧皮肤（`default`、`narrow` 等）保留不动，`themeable` 作为新增皮肤，现有调用方不受影响。

## 10. 实施记录（第一轮）

与上文设计的差异和取舍：

- **运行时转换代替构建期生成。** `lib/theme.js` 的 `makeThemeable(skin)` 直接把任意现有皮肤（6 套都已验证）转换为语义 class + `var(--wd-*)`，结果按皮肤缓存。分类依据是样式声明加所在 def 组的 id（如 `vvv-3` → `wd-data-3`，`gap` → `wd-bg`，`arrow*` → `wd-arc*`），不依赖 `sN` 的编号。
- **变量默认值写在 `var()` 的回退值里**，不在 `.wd-root` 上声明。主项目在 `:root` 或任意祖先上设置变量即可生效，无需比拼选择器优先级。`--wd-data-2`（`=` 数据格）默认跟随 `--wd-bg`。
- **渲染代码的内联 `style` 改为 class + 表现属性**（如 `class="wd-arc" stroke="#0041c4"`）。表现属性优先级低于 CSS，旧皮肤下由属性生效，主题皮肤下由 `.wd-root .wd-arc` 覆盖。旧皮肤的渲染结果经 Chromium 截图逐像素比对与改动前一致。
- **`notFirstSignal` 保留**，供 `processAll` 旧路径使用；新路径用 `renderAny(..., options)` 的 `idPrefix` / `defs: 'sprite'`。传入 `options` 时每张图都独立读取皮肤几何参数。
- **不再修改共享的皮肤对象**：`insert-svg-template.js` 复制根节点，`<style>`/`<defs>` 只读复用。

已知限制：

- sprite 模式下箭头 marker 的颜色变量从 sprite 所在位置（`body`）继承，而不是从引用它的图继承。单张图上局部覆盖 `--wd-arc` 时箭头头部不跟随，统一在 `:root` 设置不受影响。
- 导出时 `color-mix()` 之类的值会原样写入。浏览器能打开，但部分非浏览器 SVG 渲染器不支持。
- 未完成：文字宽度按实际字体测量（P5）；`reg` / `assign` 图尚未主题化。

新增 / 修改的入口：

| 文件 | 内容 |
|---|---|
| `lib/theme.js` | `makeThemeable`、`themeCss(vars, {resolve})`、`renderSprite`、`prefixDefs`、`defaults` |
| `lib/wave-view.js` + `.d.ts` | `<wave-view>` 元素、`exportSvg`；包导出 `wavedrom/wave-view` |
| `lib/wave-view-global.js` | 浏览器 bundle 入口（`npm run view` → `build/wave-view.js`） |
| `bin/cli.js` | `--skin`、`--themeable`、`--theme <json5>` |
| `test/theme.js`、`test/test-theme.html` | 单元测试；亮/暗切换演示页 |
