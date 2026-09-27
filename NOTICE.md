# 来源与许可

SODA 从 `https://github.com/zjwqsd/zanim-slide-lang` 中的 Zanim Slide Language 编译器原型及其后续改进整理而来，重新组织为独立的 Python 包。迁移保留了内容模型、类型检查、时间轴、HTML 播放器和学术排版实现，并增加公开 Python API 与项目级主题文件。

原项目的 MIT 版权声明保留在根目录 `LICENSE` 中。

`src/soda/vendor/zanim_web/` 是随包分发的 Zanim Web 运行时，源自 `https://github.com/zjwqsd/zanim`，保留其原有包名、版本信息与 MIT 许可。它用于 `@zanim` 场景，不是 SODA 语言本身。该目录是运行所需文件的子集，不是完整的上游开发仓库。

`examples/showcase/assets/` 中的图、代码、视频与文档沿用原功能示例；CSV 数值为演示数据，文献用于展示引用排版。
