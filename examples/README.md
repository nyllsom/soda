# 从范例开始

先安装并运行 `soda example` 看效果，再复制一个例子修改。内容写在 `.md`，动画写在可选的 `.soda`，输出是可以单独分享的 HTML。

## 1. 安装

准备 Node.js 20+ 和 Git，然后通过 HTTPS 从公开仓库安装：

```bash
npm install -g git+https://github.com/nyllsom/soda.git && soda help
```

公开仓库无需 GitHub 账号或 SSH 密钥。npm 使用 `git+https://…` 这种 [Git 地址格式](https://docs.npmjs.com/cli/v11/commands/npm-install/#description)。上面的命令在安装成功后自动显示使用总览，列出编译、主题和范例的入口。升级也执行这条命令。

若只想安装到当前项目，运行 `npm install git+https://github.com/nyllsom/soda.git && npx soda help`，随后用 `npx soda …` 执行下面的命令。已经安装但没有看到说明时，运行 `soda` 或 `soda help` 即可。

```bash
soda help                 # 整体用法与最短工作流
soda help compile         # 编译参数、路径、输出与依赖
soda help theme           # 生成、修改并应用自定义主题
```

也可用 `soda --help`、`soda compile --help`、`soda theme --help`。所有帮助都可离线查看，无需 Python。

终端中的帮助会自动着色，重定向或管道输出默认为纯文本。用 `NO_COLOR=1 soda help` 关闭颜色，`FORCE_COLOR=1 soda help` 强制开启；显式设置的 `FORCE_COLOR` 优先。

**编译自己的稿件**还需要 Python 3.12+，不必额外 `pip install`。CLI 自动查找 Python，也可以用 `SODA_PYTHON` 指定可执行文件路径。公式和 `.typ` 插图另需 Typst；场景打包工具 esbuild 已由 npm 安装。

## 2. 看范例

```bash
soda example
soda example showcase --theme ipads
```

第一条命令启动本地范例目录并打开浏览器；第二条直接进入 IPADS 完整展示。服务只监听本机，按 **Ctrl+C** 关闭。若不想自动打开浏览器，加 `--no-open`；用 `--port 8080` 可指定端口，默认自动选择空闲端口。

| 范例 | 用来学什么 |
| :--- | :--- |
| [quickstart](quickstart/README.md) | 四页：内容、两栏布局、逐步讲解、CLI 导出 |
| [showcase](showcase/README.md) | 十四页：公式、图表、媒体、参数场景和全部动画 |

两者都有 NJU 和 IPADS 预览。浏览预生成的范例不需要 Python 或 Typst。

## 3. 复制并修改

```bash
soda example quickstart --copy my-talk
cd my-talk
soda deck.md
```

打开生成的 `deck.html`。复制不会覆盖已有目录，避免写掉自己的文件。

| 文件 | 你在这里做什么 |
| :--- | :--- |
| `deck.md` | 写正文、选布局、引用资源 |
| `deck.soda` | 指定哪些对象何时出现、如何强调；不需要动画时可删除 |
| `build.py` | 可选的 Python API 示例；使用 CLI 时无需运行它 |

先改 `deck.md` 的正文，再运行 `soda deck.md`。`#` 是封面，`##` 开始新的一页，`###` 是页内区域。空格或 → 前进，← 回退，拖动底部进度条回看；D 检查内容是否越界。

## 4. 指定动画、输出和主题

完整编译说明可随时运行 `soda help compile` 查看；`soda compile deck.md` 与 `soda deck.md` 等效。

```bash
soda deck.md
soda deck.md animation.soda
soda deck.md animation.soda -o dist/talk.html
soda deck.md --theme ipads -o dist/talk-ipads.html
soda deck.md --static -o dist/static.html
soda check deck.md animation.soda
```

- 不指定动画文件时，自动读取同名 `.soda`；没有该文件就生成静态演示。
- 不指定 `-o` 时，在 Markdown 旁生成同名 `.html`。指定输出会自动创建父目录，并覆盖已有输出。
- `--static` 忽略同名动画，不能与显式动画文件一起使用。
- 命令行给出的 Markdown、动画和输出路径都相对当前工作目录。内容中的资源路径、主题 JSON 路径相对 Markdown 所在目录。

默认主题是 `nju`。不知道主题 JSON 怎么写时，直接在终端查看中文说明，再在稿件目录生成一份：

```bash
soda help theme
soda theme init
soda deck.md --theme theme.json
```

修改生成文件的 `primary` 和 `accent` 即可调整两种强调色；其他字段继承原主题。查看说明和生成配置都不需要 Python，也不必打开仓库。要从 IPADS 开始，用 `soda theme init --from ipads`；已有文件不会被覆盖。

最小配置如下，也可以自行存为 `themes/lab.json`：

```json
{
  "extends": "nju",
  "name": "实验室",
  "primary": "#245a73",
  "accent": "#a65432"
}
```

然后运行 `soda deck.md --theme themes/lab.json`。JSON 不会自动启用，需通过 `--theme` 指定，或在 Markdown 开头的配置区写入 `theme: themes/lab.json`。原主题标识会被继承；修改标识和更多字段，运行 `soda theme --reference` 离线查看，或阅读 [自定义主题](reference.md#自定义主题)。

## 5. 分享和继续查阅

默认只发送生成的 HTML 即可，接收方无需安装 SODA。远程网页和远程媒体仍需联网，字体和 PDF 内嵌显示取决于浏览器环境。

部署到静态网站时可用 `soda deck.md --target web -o dist/index.html`，这会生成 HTML 与相邻的 `assets/` 目录，部署时一起上传。

需要更多写法，查看 [功能速查](reference.md)。想直接在 Python 中调用编译器，查看其中的 [Python API](reference.md#python-api)；修改 SODA 本身则看 [开发说明](../CONTRIBUTING.md)。
