# 语法速查

先看 [四页入门](../examples/quickstart/README.md)，需要具体能力时再查本页。内容与初始布局写在 Markdown 中，动画写在 `.soda` 中。

## 页面、区域与对象

```markdown
---
deck: 研究进展
author: 作者
theme: academic
lang: zh
---

# 研究进展 {#cover}
封面副标题。

## 方法 {#method left|right 2:1}

### 说明 {#explanation}
一段简短说明。 {#summary}

### 结果 {#result .card}
一个需要强调的结论。
```

`#` 建立封面，`##` 建立内容页，`###` 至 `######` 建立可递归嵌套的区域。正文、标题、列表、代码、公式等都是对象。仅当动画或引用需要稳定名称时添加 `{#id}`。区域 ID 对应整个区域，其标题 ID 为 `<id>_title`。

页面 ID 在整份演示中唯一；对象 ID 在一页内唯一。`motion method` 中的 `slide` 表示整页，`title` 表示页标题。空标题 `### {#slot}` 可以建立没有文字的目标区域。

元数据还支持 `bibliography: assets/references.bib`。仅当使用引用时声明它；元数据中的主题规则见 [主题](themes.md)。

## 布局

将布局写在页面或区域标题末尾，它作用于紧邻的下一级区域：

| 标注 | 含义 |
| :--- | :--- |
| `left\|right 2:1` | 左右两栏，按比例分配 |
| `right\|left` | 反转两栏顺序 |
| `top\|bottom 1:2`、`bottom\|top` | 上下布局及其逆序 |
| `columns 2:1:1`、`rows 1:2:1` | 任意数量的栏或行 |
| `grid:2x2` | 两列两行，需四个直接子区域 |
| `stack` | 按顺序排列区域 |
| `overlay` | 子区域共用一个框，适合叠图 |

比例数量必须与直接子区域数量相同；区域也可以有自己的布局。例如 `### 运行时 {top|bottom 1:2}` 下再用两个 `####` 区分上下部分。

`gap=1.5` 覆盖间距，单位为 32 个逻辑像素；未指定时使用主题间距。`layout_id=columns` 可以命名生成的布局对象。`.card` 添加背景和内边距；`.dense`、`.tight` 适合信息较多的展示页，仍保留安全页边距。

固定画布为 **1600 × 900**，浏览器按窗口等比缩放。默认左右留白 96px，上方 64px，下方 56px；两栏间距 64px，行与网格间距 48px。页标题 48px，正文 28px。单栏普通正文最长 1000px；多栏内容按区域宽度自然换行，不按固定字数硬拆行。

区块标题与下方块的外侧左边界对齐。卡片保留 32px 内边距，组内间距 24px。表格按内容决定宽度，文字用左对齐、数值按需要右对齐；只有确需通栏时才使用 `{.wide}`。

## 文字、代码与公式

支持段落、粗体、斜体、删除线、行内代码、链接、有序与无序列表、引用和分隔线。普通 Markdown 表格下方单独写 `{#results}` 可以命名表格，行和单元格分别生成 `results_r1`、`results_r1_c2` 等 ID。

````markdown
```python {#trainer line_numbers=true max_lines=8}
def train(model, batch):
    loss = model(batch)
    return loss
```

@code assets/policy.py {#policy lines=2:5 max_lines=4}

行内公式 $p = m v$ 与正文混排。

$$
L = 1/N sum_(i=1)^N (y_i - hat(y)_i)^2
$$ {#loss font_size=36 color=foreground align=left}
````

公式使用 **Typst 数学语法**，导出时编译为 SVG，不使用 LaTeX 或浏览器端 MathJax。`align=center` 突出独立结论，`align=left` 便于连续阅读；普通汇报宜统一策略。`color=primary` 使用主题主色。

`create()` 让整个公式同步出现，包含分数线、根号和文字。分步骤推导应拆成多个数学对象。`focus(line=...)` / `focus(range=[a,b])` 只用于代码，保持行选区；`highlight()` 是临时强调，可用于代码或整个公式。行号从 1 开始，区间包含两端。公式不能按代码行聚焦。

## 资源、图表与文献

```markdown
![结果](assets/result.png) {#figure fit=contain label=a caption="验证结果"}
@video assets/demo.mp4 {poster=assets/poster.png controls=true muted=true}
@typst assets/pipeline.typ {#pipeline page=1}
@pdf assets/note.pdf {page=1 label="论文"}
@web https://example.com {label="打开网页"}
@embed assets/policy.py {type=code lines=2:5}
@slide detail {#preview}
```

资源路径相对 Markdown 所在目录。支持 HTTPS 远程资源；单文件导出只内嵌本地资源，远程地址保持不变。`@embed` 可按扩展名识别资源，也可用 `type=image|video|zanim|typst|pdf|web|code` 明确类型。代码和 Typst 在构建时读取；PDF 与网页由浏览器显示。

`@slide` 引用另一页真实内容，用于预览和 `embed_zoom`，不是截图。

```markdown
@chart assets/results.csv {#curve type=line x=step y=ours,baseline xlabel="step" ylabel="score"}

@diagram {#pipeline direction=LR}
input["输入"] -> encoder["编码"] -> output["输出"]
@enddiagram

已有工作 [@he2016resnet] 提供了参考。
@cite vaswani2017attention
@references
```

CSV 图表支持 `line`、`bar`、`scatter`；每条系列都有 ID，如 `curve_ours`。技术图支持 `LR` / `TB`；节点直接使用声明的名称，边使用 `<图ID>_edge_N`。文献来自元数据声明的 BibTeX 文件，编译时检查路径和引用键。

## 动画与讲解步骤

```soda
const QUICK: Duration = 400ms;

motion method {
    step "说明" {
        parallel(duration = QUICK) {
            explanation.fade_in();
            result.fade_in(at = 100ms);
        }
    }
    step "结论" {
        result.scale(by = 1.05, duration = QUICK);
        wait 200ms;
    }
}
```

动作默认依次执行，`step` 设置讲解停顿。`parallel` 中的动作使用同一起点，`duration` 给子动作提供默认时长，`at` 设置相对该起点的延迟；整体持续到最晚的子动作结束。并行块不能嵌套，也不能在其中使用 `wait`。

时长使用 `ms` 或 `s`，默认 1s；缓动支持 `SMOOTHSTEP`（默认）与 `LINEAR`。同一对象的同一通道不能出现时间重叠，例如并行动画中同时 `move` 和 `scale` 会在编译时报错。需要共同变化时应按已有能力组织步骤。

| 方法 | 用途与关键参数 |
| :--- | :--- |
| `fade_in()`、`fade_out()` | 进入与离场 |
| `opacity(to=0.5)` | 修改透明度 |
| `move(by=vec2(48,-24))` | 按画布像素移动，向右、向下为正 |
| `scale(by=1.05)`、`rotate(by=0.08)` | 相对缩放、旋转；角度单位为弧度 |
| `create()` | 创建过程；公式作为一个整体出现 |
| `fit_to(target=slot)` | 适配另一个对象的框 |
| `focus(line=3)`、`focus(range=[2,4])` | 代码持续聚焦 |
| `highlight()` | 代码或公式临时强调 |
| `set(name="iteration",value=1)` | 设置 Zanim 场景参数 |
| `animate(name="iteration",from=0,to=3)` | 插值改变 Zanim 场景参数 |

动作只能作用于已声明的对象。`fit_to` 在临时框中重新布局文字，不将文字当图片拉伸；目标默认仅提供几何尺寸并隐藏，可用 `show_target=true` 保留目标可见性。

## 页间转场

```soda
flow {
    cover -> method using fade(duration = 400ms);
    method -> result using push(LEFT, duration = 400ms);
}
```

转场只能连接 Markdown 顺序中的相邻页面。支持 `cut`、`fade`、`push`、`shared` 和 `embed_zoom`。`push` 方向可用 `LEFT`、`RIGHT`、`UP`、`DOWN`。没有动画文件时默认直接切页；有动画文件但未声明转场时默认 `push`。

`shared("hero", "hero_mark", duration=800ms)` 在相邻页之间延续同名对象。两端须存在兼容的区域框或内容一致的图片、视频、公式、页面预览；不支持文字或代码的形变。共享区域只共享表面和框，子对象仍需单独列出。过渡中每个身份只由一个临时对象呈现。

`embed_zoom(duration=800ms)` 将当前页中 `@slide detail` 的预览放大，进入紧邻的 `detail` 页。两种复杂转场的完整对应关系见 [showcase](../examples/showcase/deck.soda)。

## Zanim 场景

```markdown
@zanim scene.js {#koch iteration=0}
```

场景模块导出 `mount(container, context)` 或默认函数，返回对象可实现 `render(time, props)` 与 `destroy()`。SODA 管理演讲时间，模块负责图形几何。模块可从随包携带的 `@zanim/web` 导入运行时；自己的 npm 依赖仍需自行提供。

```soda
motion scene {
    koch.animate(name = "iteration", from = 0, to = 3, duration = 1800ms);
    koch.set(name = "iteration", value = 1);
}
```

本地场景的单文件导出用 esbuild 打包 JavaScript，并内嵌 Zanim WASM。`--target web` 则将模块和运行时放入相邻 `assets/`，通过 HTTP 服务访问。

## 检查与回放

编译器将动作转换为绝对时间区间；播放器从时间直接求状态，支持回退、跳转和重复进入转场。浏览器底部进度条可定位任意时间，D 打开布局诊断。

开发时可用 `window.sodaTimeline.seek(seconds)`、`window.sodaObjects.get(slideId, objectId)` 和 `window.sodaDiagnostics.layout()` 检查状态。完成的示例应没有基础布局越界，并检查重要动画的中间帧；源码检查不能发现所有浏览器排版问题。
