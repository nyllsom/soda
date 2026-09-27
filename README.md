# SODA

用 Markdown 写演示内容，用可选的 `.soda` 文件安排讲解节奏，运行 `soda deck.md` 生成可分享的 HTML。

像气泡为水增添轻微的动感，SODA 为静态内容加入适度的动态：内容始终是主体，动画帮助讲解逐步展开。

通过 npm 从 Git 安装，提供 `soda` 命令和 `soda example` 范例入口。支持学术排版、公式、代码聚焦、图表、媒体与可回放动画；内置 `nju`（默认）和 `ipads` 两套主题。

- **安装与使用**：[从范例开始](examples/README.md)——安装、浏览范例、复制源码、编译和换主题。
- **查具体写法**：[功能速查](examples/reference.md)。
- **修改编译器**：[开发说明](CONTRIBUTING.md)。

当前为 `0.1.0` 原型。npm 入口需要 Node.js 20+；编译自己的稿件还需要 Python 3.12+，公式和 Typst 插图需要 Typst。范例已随包预生成，浏览无需 Python 或 Typst。Python API 继续保留。

采用 [MIT 许可](LICENSE)。
