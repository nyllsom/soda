# 从示例开始

在仓库根目录运行，要求 Python 3.12+：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python examples/quickstart/build.py
```

Windows PowerShell 使用 `.venv\Scripts\Activate.ps1` 激活环境。

打开生成的 `dist/quickstart.html`。按 **空格 / →** 前进一步，**←** 回退，**D** 检查布局，也可以拖动底部进度条。接收方无需安装 Python。

| 示例 | 用途 | 构建条件 |
| :--- | :--- | :--- |
| [quickstart](quickstart/README.md) | 四页，学会内容、布局、动画和导出 | 只需 Python |
| [showcase](showcase/README.md) | 十四页，对照源码查看完整能力 | Python、Typst；单文件场景还需 esbuild |

建议复制 `quickstart/` 作为自己的第一份演示。内容写在 `deck.md`；动画写在同名 `deck.soda`，可以删除动画文件或使用 `static=True` 导出静态版本。

默认导出会内嵌本地资源，只发送一个 HTML 即可。远程网页、远程媒体仍需联网；字体使用接收方系统字体，PDF 的内嵌显示取决于浏览器。正文与动画 API、主题规则分别见 [API](../docs/api.md)、[语法](../docs/language.md)、[主题](../docs/themes.md)。
