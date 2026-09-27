# 修改 SODA

制作演示稿从 [examples](examples/README.md) 开始。本文说明如何修改和分发 SODA 本身。

## 代码在哪里

| 想改什么 | 代码位置 |
| :--- | :--- |
| npm 命令、Python 查找与启动 | `bin/soda.js` |
| 范例浏览和源码复制 | `bin/examples.js`、`examples/index.html` |
| Python API、编译参数 | `src/soda/api.py`、`cli.py` |
| Markdown 内容和布局语法 | `src/soda/compiler/content.py` |
| 动画语法、对象检查和时间轴 | `src/soda/compiler/` |
| HTML、资源内嵌、公式编译 | `src/soda/html/`、`src/soda/adapters/typst.py` |
| 留白、字号、浏览器动画 | `src/soda/html/academic.css`、`runtime.js` |
| 内置主题与标识 | `src/soda/themes/` |

npm 包携带 Python 源码，启动器调用本机 Python，直接加载随包编译器，不安装 Python 依赖、不使用安装脚本构建范例。esbuild 是 npm 依赖；`soda example` 的预览和复制功能直接由 Node.js 提供。

Markdown 决定内容和布局，`.soda` 引用已有对象安排动作。编译器将动作转换为绝对时间区间，播放器按当前时间求画面，因此可以回退和任意跳转。`src/soda/vendor/` 是随包携带的 Zanim Web 运行时及许可。

## 本地开发

需要 Node.js 20+、Python 3.12+；完整测试和范例构建还需 Typst。可使用 `SODA_TYPST` 指定 Typst 路径。

```bash
npm ci
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
npm test
python -m ruff check .
python -m pytest -q
```

Python 测试可从仓库的 `node_modules/.bin` 找到 esbuild；若使用别处的二进制，可设置 `SODA_ESBUILD`。尚未安装可选工具时，基础检查使用 `npm test` 和 `python -m pytest tests/test_api.py tests/test_cli.py -q`。

开发 CLI 时直接运行 `node bin/soda.js …`；开发 Python 接口时使用 `python -m soda …`。Python 包不再注册同名 `soda` 命令，避免与 npm 的入口冲突。

## 更新范例与分发

```bash
npm run examples:build
node bin/soda.js example
npm pack
python -m build
```

`examples/preview/` 的四份 HTML 与源码一并提交。这让 Git 安装后的 `soda example` 立即可用，安装者无需 Typst 或 Python 来构建范例。修改示例、主题或播放器后，重新生成预览，在浏览器中检查 D 面板和重要动画中间帧。

`npm pack` 生成 `.tgz`，Python 构建在 `dist/` 生成 wheel。分发前，在仓库外用临时 npm 安装目录检查 CLI、范例预览、源码复制和实际导出；打包内容必须包含两个主题、标识及 Zanim WASM，不能包含虚拟环境和构建工具二进制。

版本号在 `package.json`、`pyproject.toml`、`src/soda/_version.py` 中保持一致。推送到 GitHub 后，可用 `npm install -g git+https://github.com/nyllsom/soda.git` 安装；公开仓库无需 SSH 密钥。本项目当前通过 Git 分发，不需要向 npm registry 发布。
