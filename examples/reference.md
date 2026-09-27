# 功能速查

本文用于查具体写法。第一次使用请从 [运行示例](README.md) 开始，无需先读完这里。

| 想做什么 | 跳到这里 | 完整展示中的位置 |
| :--- | :--- | :--- |
| 分两栏、三栏或网格 | [布局](#分栏与网格) | 第 3–4 页 |
| 逐步出现、移动或转场 | [动画](#动画与转场) | 第 10–14 页 |
| 解释代码和数学公式 | [代码与公式](#代码与公式) | 第 5 页 |
| 加图片、图表、文献或场景 | [内容引用](#图片图表与外部文件) | 第 6–9 页 |
| 调整 Python 导出参数 | [Python API](#python-api) | 第 14 页 |
| 加标识，让素材随主题换色 | [自定义主题](#自定义主题) | NJU 与 IPADS 对比 |

表中的页码对应 [完整展示](showcase/README.md) 的 HTML 页数。下方片段说明单项功能；完整搭配见示例的 [deck.md](showcase/deck.md) 与 [deck.soda](showcase/deck.soda)。

## 分栏与网格

把下面内容放进 Markdown，即得到一个左宽右窄的页面：

```markdown
## 方法 {#method left|right 2:1}

### 说明 {#explanation}
先解释问题。

### 结果 {#result .card}
再给出结论。
```

`left|right 2:1` 将两个 `###` 区域按 2:1 分配宽度。`.card` 给“结果”加上带内边距的背景块。`#method`、`#explanation`、`#result` 是名称，动画用它们找到页面或区域。

| 布局标注 | 效果 |
| :--- | :--- |
| `left\|right`、`right\|left` | 等宽两栏，或反转左右顺序 |
| `columns 2:1:1` | 三栏，第一栏占一半宽度 |
| `top\|bottom 1:2`、`bottom\|top` | 上下分区，或反转上下顺序 |
| `rows 1:2:1` | 三行，按指定比例分配 |
| `grid:2x2` | 两列两行，需要四个直接子区域 |
| `stack` | 顺序排列子区域 |
| `overlay` | 子区域叠在同一个框中，适合叠图 |

布局也能写在 `###` 上，再用 `####` 划分子区域。每个比例对应一个直接子区域；网格需要正好填满声明的格子数。`### {#slot}` 可以声明不含标题文字的区域。

**排版建议**：先保留默认间距，让文字自然换行；不要为了填满页面拉伸表格。固定画布为 1600 × 900，浏览器整体等比缩放。默认左右留白 96px，普通两栏间距 64px，卡片内边距 32px。

确有需要时，`gap=1.5` 可将布局间距设为 48px（单位为 32px）。`.dense` / `.tight` 会减小字号和间距，适合信息较多的页面。普通单栏正文最长 1000px；表格按内容决定宽度，`{.wide}` 才明确要求通栏。

## 动画与转场

为上面的“方法”页添加同名 `.soda` 文件：

```soda
motion method {
    step "说明" {
        explanation.fade_in(duration = 400ms);
    }
    step "结论" {
        result.fade_in(duration = 400ms);
    }
}
```

每个 `step` 是一次讲解停顿。要一起出现，使用 `parallel`：

```soda
motion method {
    step "一起展开" {
        parallel(duration = 400ms) {
            explanation.fade_in();
            result.fade_in(at = 100ms);
        }
    }
}
```

这两段是替代写法，一页只写一个 `motion`。第二段中，“说明”立即开始，“结果”晚 100ms 开始，整体持续 500ms。

| 你要的效果 | 写在对应页面的 `motion` 中 |
| :--- | :--- |
| 进入、离场 | `result.fade_in();` / `result.fade_out();` |
| 半透明 | `result.opacity(to = 0.5);` |
| 向右移动 48px | `result.move(by = vec2(48, 0));` |
| 放大或旋转 | `result.scale(by = 1.05);` / `result.rotate(by = 0.08);` |
| 逐步呈现对象 | `result.create();`；公式会整体同步出现 |
| 移到另一个区域的框中 | `result.fit_to(target = slot);`，需先在 Markdown 中声明 `slot` |

这些方法均可加 `duration`、`at` 和 `easing`。时长用 `ms` 或 `s`，默认 1s；缓动用 `SMOOTHSTEP`（默认）或 `LINEAR`；旋转以弧度计。`wait 200ms;` 增加停顿，`const QUICK: Duration = 400ms;` 可复用时长。

动作默认依次执行。并行块不能嵌套或包含 `wait`；同一对象不能同时执行冲突的动作，例如并行移动和缩放。页 ID 全局唯一，对象名称页内唯一。`slide`、`title` 分别指当前整页和页标题；区域标题名为 `<区域ID>_title`。

页间动作放在单独的 `flow` 中，例如已有相邻的 `cover`、`method` 两页时：

```soda
flow {
    cover -> method using fade(duration = 400ms);
}
```

| 转场 | 适合什么场景 |
| :--- | :--- |
| `cut()` | 直接切页 |
| `fade(duration = 400ms)` | 温和过渡 |
| `push(LEFT, duration = 400ms)` | 按方向推入；也支持 RIGHT、UP、DOWN |
| `shared("hero", "hero_mark", duration = 800ms)` | 在相邻页之间延续同名区域、图片或公式等对象 |
| `embed_zoom(duration = 800ms)` | 将 `@slide detail` 的预览放大进入紧邻的 detail 页 |

没有动画文件时默认直接切页；有动画文件但未指定转场时默认推入。转场只能连接 Markdown 顺序中相邻的两页。

`shared` 要求两端对象兼容，图片、公式等内容一致；它不能把一段文字变成另一段文字。共享区域只共享框，区域里的对象需单独列出。`fit_to` 的目标默认隐藏，只提供尺寸，`show_target=true` 可保持目标可见。完整搭配参见展示的第 11–14 页。

## 代码与公式

在代码块的语言名后加 `{#policy}`，或直接引用源码文件：

```markdown
@code assets/policy.py {#policy lines=2:5 max_lines=4}
```

对应页面的 `motion` 中，`policy.focus(range = [2, 3]);` 持续聚焦两行，`policy.highlight(line = 4);` 短暂强调一行。行号从 1 开始，范围包含两端；引用文件时，动画行号对应截取后显示的代码。代码块也支持 `line_numbers=false` 隐藏行号。

公式使用 **Typst 数学语法**。导出前准备 Typst，安装方式见 [完整展示](showcase/README.md#修改并重新生成)。

```markdown
行内公式 $p = m v$ 与正文混排。

$$
L = 1/N sum_(i=1)^N (y_i - hat(y)_i)^2
$$ {#loss font_size=36 color=foreground align=left}
```

`align=left` 便于接着正文阅读，`align=center` 突出独立结论；`color=primary` 使用主题主色。普通汇报中保持同一种策略，完整展示第 5 页则刻意对比两种选择。

`loss.create();` 让文字、分数线和根号同步出现；`loss.highlight();` 强调整个公式。分步骤推导请拆成多个公式对象，公式不支持按代码行 `focus`。

## 图片图表与外部文件

下面是可放进 Markdown 的写法；`assets/` 下的文件需由自己的项目提供。路径相对 Markdown 所在目录，HTTPS 地址则作为远程引用保留。

```markdown
![结果](assets/result.png) {#figure fit=contain caption="验证结果"}
@video assets/demo.mp4 {poster=assets/poster.png controls=true muted=true}
@typst assets/pipeline.typ {page=1}
@pdf assets/note.pdf {page=1}
@web https://example.com {label="打开网页"}
@embed assets/policy.py {type=code lines=2:5}
@slide detail {#preview}
```

`@embed` 根据扩展名识别类型，也可以明确指定 `type`。`@slide detail` 引用的是同一份演示中 ID 为 `detail` 的页面，适合用作后续页面的预览。

CSV 图表和技术图无需额外 JavaScript：

```markdown
@chart assets/results.csv {#curve type=line x=step y=ours,baseline}

@diagram {#pipeline direction=LR}
input["输入"] -> encoder["编码"] -> output["输出"]
@enddiagram
```

图表支持 `line`、`bar`、`scatter`，系列可独立动画，例如 `curve_ours.fade_in();`。技术图支持横向 `LR` 和纵向 `TB`；节点用声明的名字，边用 `pipeline_edge_1` 等自动名称。

文献需要在 Markdown 开头声明 `bibliography: assets/references.bib`，正文用 `[@文献键]` 或 `@cite 文献键` 引用，`@references` 列出参考文献。普通 Markdown 表格下方单独写 `{#results}`，则行和单元格分别可用 `results_r1`、`results_r1_c2` 等名称控制。

**参数驱动的图形**用 `@zanim scene.js {#koch iteration=0}` 引入。场景导出 `mount(container, context)`，返回可实现 `render(time, props)` 和 `destroy()` 的对象；写法参照 [scene.js](showcase/scene.js)。在动画文件中可用：

```soda
motion scene {
    koch.animate(name = "iteration", from = 0, to = 3, duration = 1800ms);
    koch.set(name = "iteration", value = 1);
}
```

这对应展示中 ID 为 `scene` 的页面。单文件导出本地场景需要 esbuild；依赖设置见 [完整展示](showcase/README.md#修改并重新生成)。

## Python API

需要将编译器嵌入自己的 Python 程序时，在源码仓库运行 `python -m pip install .`。通过 npm 使用 CLI 不需要这一步。

```python
from soda import compile_deck, export_html

deck = compile_deck("deck.md")
export_html(deck, "demo.html")
```

以下参数用于改变默认行为。Python API 的显式动画路径相对 Markdown 目录；CLI 的显式动画参数则相对运行命令的目录。

| 调用 | 输入与结果 | 可选项 |
| :--- | :--- | :--- |
| `compile_deck(source)` | 读取 `.md` 路径，返回 `Deck` | 自动读取同名 `.soda`；`static=True` 忽略动画；`motion="other.soda"` 改用另一份动画 |
| `compile_text(markdown)` | 读取 Markdown 字符串，返回 `Deck` | `motion` 为动画字符串，`base_dir` 指定资源与主题根目录；不自动读取动画文件 |
| `export_html(deck, output)` | 导出 HTML，返回输出 `Path` | `theme` 覆盖本次主题；`portable=False` 改为 HTML 加相邻的 `assets/` 目录 |

例如内容由 Python 生成时：

```python
from soda import compile_text, export_html

deck = compile_text(
    "## 结果 {#result}\n准确率提高。 {#finding}\n",
    motion="motion result { finding.fade_in(duration = 400ms); }",
)
export_html(deck, "result.html")
```

显式动画路径和主题 JSON 路径相对 Markdown 目录；`compile_text` 中相对 `base_dir`，省略时用当前目录。`static=True` 不能与显式 `motion` 一起使用。输出路径相对运行目录，导出会自动创建父目录并覆盖同名文件。

`Deck` 是编译结果，直接交给 `export_html` 即可。编译时不调用 Typst 或 esbuild；导出时才读取素材、调用需要的工具。若在程序中处理错误，语法和对象检查异常为 `SodaError`，资源、主题或时间冲突可能抛出 `ValueError`，文件读取可能抛出 `OSError`。

命令行使用 `soda deck.md [motion.soda] [-o demo.html]`，检查使用 `soda check deck.md [motion.soda]`。也保留 `soda html …` 写法。导出支持 `--static`、`--theme ipads`、`--target web`；选择 web 模式部署时需同时上传 HTML 和 `assets/`。安装 Python 包后可通过 `python -m soda` 调用编译命令，范例服务由 npm 的 `soda example` 提供。

## 自定义主题

入门只需 [新建主题 JSON](README.md) 中的四个字段。要增加标识，可将主题写成下面这样，并把 `logo.png` 放在该 JSON 旁边：

```json
{
  "extends": "nju",
  "name": "实验室",
  "primary": "#245a73",
  "brand_logo": "logo.png",
  "brand_label": "实验室标识",
  "logo_width": "220px",
  "logo_height": "64px"
}
```

`extends` 只能选内置的 `nju` 或 `ipads`，默认是前者。标识路径相对主题 JSON，而非 Markdown。继承主题后，不覆盖标识就继续使用该主题的标识；将 `brand_logo` 或封面附属标识 `affiliation_logo` 设为 `null` 可以移除。

完整字段可对照 [nju.json](../src/soda/themes/nju.json) 与 [ipads.json](../src/soda/themes/ipads.json)。`"$primary"` 表示引用主色，例如代码高亮使用该引用，覆盖主色后就会同步变化。

自己制作的素材需要使用主题变量，才能一起换色：

| 素材 | 写法 | 可参考的文件 |
| :--- | :--- | :--- |
| SVG | `stroke="var(--soda-primary)"` | [curve.svg](showcase/assets/curve.svg) |
| Typst | `rgb(sys.inputs.at("soda-primary", default: "#315b85"))` | [pipeline.typ](showcase/assets/pipeline.typ) |
| JavaScript 场景 | 从 `getComputedStyle(container)` 读取 `--soda-primary` | [scene.js](showcase/scene.js) |

常用变量还有 `surface`（块背景）、`foreground`（正文）、`muted`（次要文字）和 `accent`（第二强调色）。写死的色值、照片和视频不会被自动改色。
