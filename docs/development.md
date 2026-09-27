# 结构与验证

```text
src/soda/
  api.py          Python 公开入口
  cli.py          命令行薄封装
  compiler/       内容、语法、类型检查与时间轴
  html/           HTML 导出、资源处理与浏览器播放器
  adapters/       可选 Typst 编译适配
  themes/         内置主题 JSON 与标识
  vendor/         随包携带的 Zanim Web 运行时
examples/         入门和完整展示
tests/            编译器、渲染与 API 回归检查
docs/             按需查阅的说明
```

数据依次经过 Markdown 对象树、经过类型检查的动作、绝对时间轴和 HTML 导出。内容和布局由 Markdown 决定，`.soda` 只描述已有对象的变化。播放器从绝对时间计算画面，使跳转和回退得到一致状态。

第一版保留完整原型的对象与动画能力，不引入编辑器服务、插件系统或多种输出后端。语言内部 AST/HIR/IR 继续分层，以便排查语法、类型与播放问题；公开 Python API 保持小而稳定。

```bash
python -m pip install -e '.[dev]'
python -m ruff check .
python -m pytest -q
python -m build
```

完整测试使用真实 Typst 和 esbuild，准备方式见 [showcase](../examples/showcase/README.md)。没有这些可选工具时可运行 `python -m pytest tests/test_api.py -q` 验证基础使用；完整套件不会将缺失工具误报为已通过。

改动导出器或播放器后，运行两套示例并打开生成的 HTML：D 面板应为 `0 issues`，还应检查公式出现、代码聚焦、`fit_to`、`shared`、`embed_zoom` 的中间时刻和回退行为。Python 测试不能替代浏览器排版验证。

分发前构建 wheel，在仓库外的新虚拟环境中安装，再运行示例。包中必须包含 CSS、JavaScript、主题 JSON、标识和 Zanim WASM；基础导出不能依赖源码目录、Node.js 或 Typst。构建产物位于忽略的 `dist/`，示例源文件进入版本管理。
