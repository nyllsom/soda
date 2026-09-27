# 四页入门

这个示例只需要 Python，不含公式、外部素材或 JavaScript 场景。

在仓库根目录完成安装后运行：

```bash
python examples/quickstart/build.py
```

打开 `dist/quickstart.html`，同时阅读以下三个文件：

- `deck.md`：标题划分页和区域；`left|right 1:1` 将两个区域并排。
- `deck.soda`：用对象 ID 指定动画，用 `step` 指定讲解停顿；代码聚焦和右侧内容同步出现。
- `build.py`：调用公开 Python API。资源路径随 Markdown 所在目录解析，不依赖启动位置。

四页分别介绍分工、源码与布局、源码与动画、导出与分享。前两页静态呈现，第三页用两次点击展开两条结论；动画用于引导注意力。

也可以直接调用命令行：

```bash
soda check examples/quickstart/deck.md
soda html examples/quickstart/deck.md -o dist/quickstart.html
soda html examples/quickstart/deck.md --static -o dist/quickstart-static.html
soda html examples/quickstart/deck.md --theme ipads -o dist/quickstart-ipads.html
```

先改正文，再尝试调整第三页的 `duration`。如需更多对象或转场，查看 [完整展示](../showcase/README.md)。
