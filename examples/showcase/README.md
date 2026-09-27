# 十四页完整展示

用于对照源码查看全部已实现的对象、动作与转场。以 `deck.md` 为内容入口，同名 `deck.soda` 安排动画，`scene.js` 实现一个参数驱动的 Zanim 场景。

先按 [上一级说明](../README.md) 安装 SODA，再准备可选构建工具：

- **Typst**：让 `typst` 在 PATH 中可用，或设置 `SODA_TYPST` 为可执行文件路径。用于公式和 `.typ` 插图。
- **esbuild**：安装 Node.js 后，在仓库根目录执行 `npm install --no-save --package-lock=false esbuild`。也可以将 `esbuild` 放入 PATH，或设置 `SODA_ESBUILD`。用于将本地 JavaScript 场景打进单个 HTML。

本次验证使用 Python 3.12.3、Typst 0.15.1、esbuild 0.28.2。

```bash
python examples/showcase/build.py
```

脚本从同一份内容生成 `dist/showcase.html` 和 `dist/showcase-ipads.html`。前者使用中性学术主题，后者展示 IPADS 配色与标识；两者共享时间轴。

| 页码 | 观察重点 |
| :--- | :--- |
| 1–4 | 封面、Markdown、紧凑表格、两栏与三栏、递归布局 |
| 5 | 公式、代码聚焦与短暂强调；公式分数线和文字同步出现 |
| 6–8 | CSV 图表、技术图、文献、图片、视频、Typst、PDF 与网页 |
| 9–10 | 参数场景、移动、缩放、旋转、透明度与离场 |
| 11–14 | 区域适配、跨页共享对象、页面预览与放大进入、导出流程 |

公式页刻意对比“居中、主题色”和“居左、正文色”，旁边分别说明用途。这是能力对比；自己的汇报应保持一致的对齐与强调策略。图表、SVG 和场景使用语义颜色，切换主题即可统一换色。

**观看方式**：空格或右箭头前进，左箭头回退；拖动进度条观察动画中间状态。D 打开布局诊断。源文件中的页面编号从封面后的 01 开始。

本地素材已包含在单文件 HTML 中；网页示例仍需联网，并受目标站点的 iframe 策略限制。浏览器若不支持内嵌 PDF，可用页面提供的打开链接。字体由接收方系统提供，跨系统可能略有差异。

若部署到静态网站，`soda html examples/showcase/deck.md --target web -o dist/web/index.html` 会生成 HTML 与 `assets/` 目录，无需 esbuild；部署时需保留两者。Typst 仍是本例的构建依赖。
