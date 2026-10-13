---
deck: Remotion · 从图标到图表
lang: zh
theme: nju
---

# Remotion 动画教学 {#intro}

React 写画面，SODA 安排讲解节奏。

按空格逐步播放，按左箭头回退；拖动底部进度条验证任意帧。

## 01 · 图标入场：帧驱动 {#icon}

@remotion icon.tsx {#check}

`useCurrentFrame()` 获取本页时间对应的帧，`spring()` 控制缩放，`interpolate()` 控制勾线。

## 02 · 图表变化：参数驱动 {#chart}

@embed chart.tsx {#bars progress=0}

`.animate()` 连续改变 progress；`.set()` 修改标题。回退时恢复初始状态。
