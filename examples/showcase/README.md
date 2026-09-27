# 十四页完整展示

展示已实现的内容、动画和转场。无需构建，直接查看：

```bash
soda example showcase
soda example showcase --theme ipads
```

## 修改并重新生成

```bash
soda example showcase --copy my-showcase
cd my-showcase
soda deck.md -o showcase.html
soda deck.md --theme ipads -o showcase-ipads.html
```

编译需要 Python 3.12+。**Typst** 用于公式和 `.typ` 插图，让 `typst` 在 PATH 中可用，或设置 `SODA_TYPST` 为可执行文件路径。esbuild 已包含在 npm 依赖中，无需单独安装；如需覆盖，可设置 `SODA_ESBUILD`。

自定义配色与标识：`soda theme` 查看写法，`soda theme init --from ipads` 生成配置，修改后用 `soda deck.md --theme theme.json` 应用。`soda theme --reference` 提供离线字段说明。

本次验证使用 Node.js 22.22.2、Python 3.12.3、Typst 0.15.1、esbuild 0.28.2。

## 对照效果和源码

[deck.md](deck.md) 决定内容，[deck.soda](deck.soda) 决定动作，[scene.js](scene.js) 实现参数驱动的图形。按空格或 → 前进，← 回退；拖动进度条观察中间状态，D 检查布局。

| HTML 页码 | 观察重点 |
| :--- | :--- |
| 1–4 | 封面、Markdown、紧凑表格、两栏与三栏、递归布局 |
| 5 | 公式、代码聚焦与短暂强调；分数线和文字同步出现 |
| 6–8 | CSV 图表、技术图、文献、图片、视频、Typst、PDF 与网页 |
| 9–10 | 参数场景、移动、缩放、旋转、透明度与离场 |
| 11–14 | 区域适配、跨页共享对象、页面预览与放大进入、CLI 导出 |

源文件中的编号从封面后的 01 开始。公式页刻意对比“居中、主题色”和“居左、正文色”，分别说明用途；自己的汇报宜保持一致的对齐与强调策略。具体参数见 [功能速查](https://github.com/nyllsom/soda/blob/main/examples/reference.md)。

## 分享和部署

默认只分享 HTML。本地素材已内嵌；网页示例仍需联网，并受目标站点的嵌入策略限制。浏览器若不支持内嵌 PDF，可使用页面中的打开链接。

网站部署用 `soda deck.md --target web -o dist/index.html`，同时上传 HTML 和 `assets/`。这一模式无需 esbuild，重新编译本例仍需要 Typst。

在源码仓库中执行 `npm run examples:build`，可更新两份范例的四个主题预览。Python API 的等效构建见 [build.py](build.py)。
