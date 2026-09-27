---
deck: SODA · 四页入门
theme: nju
lang: zh
---

# 内容先行，动态适度 {#intro}

SODA · 从一份 Markdown 到可分享的演示。

用四页了解内容、布局、讲解节奏与导出。

## 01 · 源码与排版一一对应 {#layout left|right 1:1}

### 左侧 · 写下结构

```markdown {line_numbers=false}
## 一个清楚的结论 {left|right 1:1}

### 观察
先说明发生了什么。

### 解释
再说明为什么。
```

本页也使用两个等宽区域。标题和正文共享左边界，栏间留白区分内容。

### 右侧 · 理解规则

- `#` 是封面，`##` 开始新的一页
- `###` 建立页内区域
- `left|right 1:1` 让两个区域并排

> 先写清楚内容，再选择布局。

## 02 · 每一步只引入一个重点 {#steps left|right 1:1}

### 左侧 · 安排讲解

```soda {#source line_numbers=true}
motion steps {
  step "观察" {
    observation.fade_in(duration = 400ms);
  }
  step "解释" {
    explanation.fade_in(duration = 400ms);
  }
}
```

右侧对象在 Markdown 中命名为 `observation` 和 `explanation`。示例文件还同步聚焦对应代码行。

### 右侧 · 按两次下一步

#### 观察 {#observation .card}

一次展示一个重点，听众更容易跟上。

#### 解释 {#explanation .card}

动画提供讲解顺序，结论仍由文字表达。

## 03 · 编译一次，直接分享 {#export left|right 1.15:1}

### 在终端中导出

```bash {line_numbers=false}
soda deck.md
soda deck.md motion.soda -o demo.html
soda deck.md --theme ipads -o demo.html
```

同名 `deck.soda` 自动加载；没有动画文件时，仍然是一份完整的静态演示。

### 交给读者的是一个文件

默认生成同目录的 `deck.html`；也可用 `-o` 指定路径。将 HTML 发给对方，用浏览器打开即可。

- **空格 / →**：下一步；**←**：回退
- **D**：检查内容是否越界
- 底部进度条：自由回看任意时刻

> 先完成四页入门，再探索完整展示。
