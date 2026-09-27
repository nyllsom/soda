# Python API

公开入口只有一个结果类型和三个函数：

```python
from soda import Deck, compile_deck, compile_text, export_html

deck = compile_deck("talk/deck.md")
export_html(deck, "dist/talk.html")
```

`compile_deck(source, *, motion=None, static=False)` 读取一个 `.md` 文件，默认加载同目录、同名的 `.soda`。`motion="other.soda"` 可显式指定动画文件；相对路径以 Markdown 所在目录为准。`static=True` 忽略同名动画，不能与显式 `motion` 同时使用。

`compile_text(markdown, *, motion=None, base_dir=None)` 接收字符串，适合程序生成内容。这里的 `motion` 是动画源码字符串；`base_dir` 是资源和主题的根目录，默认当前目录。它不会自动读取同名动画文件。

```python
deck = compile_text(
    "## 结果 {#result}\n准确率提高。 {#finding}\n",
    motion="motion result { finding.fade_in(duration = 400ms); }",
)
export_html(deck, "result.html", theme="ipads")
```

两种编译入口都会检查语法、对象、布局声明、资源引用与时间冲突，返回 `Deck`。其中 `program` 是内容与动作模型，`timeline` 是绝对时间轴，`theme` 是已解析主题，`base_dir` 是绝对资源目录。这些内部模型供检查使用，目前不承诺跨版本结构稳定；导出使用编译结果，不应直接修改内部对象。

`export_html(deck, output, *, theme=None, portable=True)` 返回输出文件的 `Path`。默认内嵌本地资源；`portable=False` 会生成相邻的 `assets/`。`theme` 可为内置主题名、项目主题 JSON 路径或已解析的 `Theme`，只影响本次导出。输出路径相对调用时的工作目录，父目录自动创建，已有输出文件会被覆盖。

编译不调用外部渲染工具。导出时，公式和 Typst 插图需要 Typst；含本地 Zanim 场景的单文件导出需要 esbuild。资源内容在导出时读取，编译后应保留原资源文件。

源代码诊断抛出 `SodaError`，含 `diagnostic.path`、`span` 和 `message`；路径读取可能抛出 `OSError`，无效主题或渲染参数可能抛出 `ValueError`。浏览器的实际排版仍需用 D 面板检查。

命令行复用同一 API：

```bash
soda check talk/deck.md
soda html talk/deck.md -o dist/talk.html
soda html talk/deck.md --theme ipads --static -o dist/static.html
```

`python -m soda` 与 `soda` 等价。它们用于本地编译与导出，不含编辑器服务、PPTX 导出或在线托管。
