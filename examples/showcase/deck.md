---
deck: SODA · 十四页功能速览
author: SODA
theme: academic
lang: zh
bibliography: assets/references.bib
---

# 把研究讲清楚 {#cover}

Markdown 写内容，SODA 安排讲解节奏。 {#subtitle}

十四页，了解从静态排版到可回放动画的完整工作流。

## 01 · 从普通 Markdown 开始 {#markdown .dense}

保留熟悉的 **粗体**、*斜体*、~~修订~~、`行内代码` 与[链接](https://example.com)。

- 标题建立层级，列表表达并列关系
- 对象只有需要动画时才添加 `#id`

> 先写一份能够静态阅读的演示稿。

---

| 对象 | 内容来源 | 典型行为 |
| :--- | :--- | :--- |
| 文字 | Markdown | 淡入与强调 |
| 公式 | Typst | 整体出现 |
| 代码 | 文件或代码块 | 逐行聚焦 |
{#capabilities}

## 02 · 三栏共享同一条基准线 {#columns columns 1:1:1 .dense}

### 内容 · Markdown

标题、段落和资源路径描述页面的初始状态。

```markdown {line_numbers=false}
## 方法 {left|right 2:1}
### 说明
一段简短说明。
### 结果
![图](result.png)
```

### 时间 · SODA

`step` 对应一次讲解停顿，动作默认依次执行。

```soda {line_numbers=false}
motion method {
  step "结果" {
    result.fade_in();
  }
}
```

### 工具 · 编译器 {stack}

#### 检查

对象、参数、资源与时间冲突都有诊断。

#### 导出

静态或动画 HTML；同名 `.soda` 自动关联。

## 03 · 布局可以递归组合 {#layouts grid:2x2 .dense .tight}

### 上下 · rows {top|bottom 1:1}

#### 上区
`top|bottom 1:1`

#### 下区
比例也可改为 `1:2`。

### 叠放 · overlay {overlay}

####
![示意坐标](assets/axes.svg) {fit=contain caption=""}

####
![叠加的曲线](assets/curve.svg) {#overlay_curve fit=contain caption=""}

### 并列 · columns

`left|right 2:1` 表达主次。

`right|left`、`bottom|top` 反转视觉顺序。

### 网格 · grid

本页使用 `grid:2x2`；上一页第三栏使用 `stack`。

> 每个区域和区域标题都是独立对象。

## 04 · 公式与代码同步讲解 {#math_code left|right 1:1 .dense}

### 聚焦实际源代码

@code assets/policy.py {#policy lines=1:5 max_lines=5}

```soda {line_numbers=false}
parallel(duration = 500ms) {
  equation.create();
  policy.focus(range = [2, 4]);
}
```

`focus` 保持选区；`highlight` 短暂强调。公式中的分数线与文字同步出现。

### 完整的数学对象

行内公式 $p = m v$ 与正文混排。

**居中 · 主题色**：突出独立结论。

$$
s = min(W_"viewport" / 1600, H_"viewport" / 900)
$$ {#equation font_size=30 color=primary align=center}

**居左 · 正文色**：便于与段落连续阅读。

$$
L = 1/N sum_(i=1)^N (y_i - hat(y)_i)^2
$$ {#loss font_size=30 color=foreground align=left}

> 本页对比排版选项；普通汇报宜统一。

## 05 · 数据和结构保持可编辑 {#academic left|right 1.35:1 .dense}

### 从 CSV 生成图表

@chart assets/results.csv {#curve type=line x=step y=ours,baseline title="验证集表现 · 演示数据" xlabel="step" ylabel="score"}

系列可分别控制；`type` 支持 `line`、`bar` 和 `scatter`。

### 从文本生成技术图

@diagram {#pipeline direction=TB}
input["输入"] -> encoder["编码"] -> output["输出"]
@enddiagram

节点和边都有身份。文献支持行内引用 [@he2016resnet]。

## 06 · 媒体引用就是内容 {#media grid:2x2 .dense .tight}

### 图片与子图题注

![示例图片](assets/example-image.png) {#picture fit=contain label=a caption="独立的图片对象"}

### 原生视频

@video assets/demo.mp4 {controls=true muted=true poster=assets/poster.png fit=contain}

### Typst 矢量图

@typst assets/pipeline.typ {caption="构建时编译为 SVG"}

### 引用源码与自动识别

@embed assets/policy.py {type=code lines=2:4 max_lines=3}

`@embed` 自动识别常见文件类型；`@code` 可指定行范围。

## 07 · 论文与网页进入演示 {#documents left|right 1:1 .dense}

### PDF · 定位到指定页

@pdf assets/note.pdf {page=1 caption="随 demo 提供的本地 PDF"}

```markdown {line_numbers=false}
@pdf assets/note.pdf {page=1}
```

### Web · 交互与外链

@web https://example.com {label="打开示例网页"}

网页需要联网，受目标站点嵌入策略限制；右下角保留独立打开链接。

## 08 · 参数驱动动态图形 {#scene left|right 1:1 .dense}

### 声明场景，编排参数

```markdown {line_numbers=false}
@zanim scene.js {#koch iteration=0}
```

```soda {#scene_code line_numbers=true}
koch.animate(
  name = "iteration",
  from = 0, to = 3,
  duration = 1800ms
);
koch.set(name = "iteration", value = 1);
```

复杂图形在场景模块里实现；SODA 负责演讲时间线。

### 实际的 Zanim Web 场景

@zanim scene.js {#koch iteration=0}

局部动画、公式、图形与代码共享演讲步骤。

## 09 · 同一对象，多种动作 {#object_motion left|right 1:1 .dense}

### 按讲解顺序安排动作

```soda {#motion_code line_numbers=true}
marker.fade_in(duration = 360ms);
marker.move(by = vec2(48, 0));
marker.scale(by = 1.08);
marker.rotate(by = 0.08);
marker.opacity(to = 0.45);
marker.fade_out();
```

`parallel` 同时执行；`at` 错开起点；`wait` 添加停顿。

### 观察右侧图形

![被动画控制的示意图](assets/curve.svg) {#marker fit=contain}

一个对象的变换依次执行；区域、标题和整页也能作为动作目标。 {#motion_note}

## 10 · 把对象放到目标区域 {#fit left|right 1:1.4 .dense}

### 从这个卡片出发

```soda {line_numbers=false}
card.fit_to(
  target = slot,
  duration = 800ms
);
```

#### 结论 {#card .card}

清晰的层级来自位置与留白。

### {#slot .card}

## 11 · 跨页延续同一个对象 {#shared_source left|right 1:1 .dense}

### 稳定的视觉身份 {#hero .card}

$$
E = m c^2
$$ {#hero_mark font_size=46 color=primary}

### 转场声明

```soda {line_numbers=false}
flow {
  shared_source -> overview
    using shared(
      "hero", "hero_mark",
      duration = 800ms
    );
}
```

按下一步，观察公式进入下一页的位置。

## 12 · 从页面预览进入详情 {#overview left|right 1.35:1 .dense}

### 整张幻灯片也是对象

@slide tools {#preview}

`@slide tools` 引用真实页面；下一步使用 `embed_zoom` 进入详情。

### {#hero .card}

$$
E = m c^2
$$ {#hero_mark font_size=46 color=primary}

## 13 · 检查、导出、开始讲解 {#tools left|right 1.2:1 .dense}

### 最短工作流

```python {#commands line_numbers=false}
from soda import compile_deck, export_html

deck = compile_deck("deck.md")
export_html(deck, "demo.html")
```

编译时检查对象、资源与时间冲突；浏览器中检查排版。分享只需发送导出的 HTML。

### 讲解与回看

- **空格 / →**：下一步；**←**：回退
- **D**：布局诊断；底部进度条：任意定位
- 转场：`cut`、`fade`、`push`、`shared`、`embed_zoom`

@cite vaswani2017attention

@references
