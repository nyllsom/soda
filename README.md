# SODA

SODA 是一个把 Markdown 转成 HTML 演示文稿的工具，生成的文件可以用浏览器打开、直接分享。

它在 Markdown 基础上增加了少量语法：**`.md` 写内容、排版和布局，`.soda` 写动画效果。没有 `.soda`，就生成静态演示文稿。**

像汽水里的气泡，SODA 为静态内容添一点动感。

安装并查看用法：

```bash
npm install -g git+https://github.com/nyllsom/soda.git && soda help
```

运行 `soda deck.md` 编译稿件，`soda example` 浏览范例。

- **学习使用**：[从范例开始](examples/README.md) · [语法与功能速查](examples/reference.md)
- **命令行帮助**：`soda help compile` 查看编译用法，`soda help theme` 查看主题配置
- **参与开发**：[开发说明](CONTRIBUTING.md)

安装需要 Node.js 20+ 和 Git；编译稿件还需 Python 3.12+，公式与 Typst 插图另需 Typst。浏览内置范例无需 Python 或 Typst。

采用 [MIT 许可](LICENSE)。
