# SODA

用 Markdown 写演示内容，用可选的 `.soda` 文件安排讲解节奏，再通过 Python 导出 HTML。

像气泡为水增添轻微的动感，SODA 为静态内容加入适度的动态：内容始终是主体，动画帮助讲解逐步展开。

第一版保留编译器、浏览器播放器和主题系统。支持学术排版、代码聚焦、公式、图表、媒体与可回放动画；默认导出可单独分享的 HTML。

- **从这里开始**：[安装与示例](examples/README.md)。先运行四页入门，再看十四页完整展示。
- **需要查阅时**：[Python API](docs/api.md) · [语法](docs/language.md) · [添加主题](docs/themes.md)。
- **参与开发**：[结构与验证](docs/development.md)。

当前为 `0.1.0` 原型，要求 Python 3.12+。普通内容导出无第三方 Python 运行依赖；公式需要 Typst，单文件 Zanim 场景需要 esbuild。当前产物是 HTML，不是 PPTX；不包含编辑器扩展，也尚未发布到包索引。

代码沿用 MIT 许可，来源与素材说明见 [NOTICE](NOTICE.md)。
