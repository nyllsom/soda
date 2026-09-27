# 四页入门

先按 [使用说明](https://github.com/nyllsom/soda/blob/main/examples/README.md) 安装，再打开预生成的示例：

```bash
soda example quickstart
```

复制源码并生成自己的第一份演示：

```bash
soda example quickstart --copy my-talk
cd my-talk
soda deck.md
```

打开 `deck.html`，对照 [deck.md](deck.md) 与 [deck.soda](deck.soda) 阅读。在仓库中也可运行 `soda examples/quickstart/deck.md -o dist/quickstart.html`。

| 页面 | 看什么 | 可以试着改什么 |
| :--- | :--- | :--- |
| 1 · 封面 | `#` 建立封面，后面是副标题 | 换成自己的演示标题 |
| 2 · 排版 | `left\|right 1:1` 让两个 `###` 区域并排 | 将比例改为 `2:1`，观察宽度 |
| 3 · 动画 | 两次点击展开两条结论，左侧代码同步聚焦 | 在 `.soda` 中将 `400ms` 改为 `800ms` |
| 4 · 导出 | `soda deck.md` 生成 HTML，`-o` 指定输出 | 加上 `--static` 导出静态版本 |

第三页中，Markdown 的 `{#observation .card}` 给“观察”卡片取名，动画中的 `observation.fade_in()` 让整张卡片出现。前两页保持静态，第三页才用动画引导讲解。

这个例子的编译只需 Python 3.12+，无需 Typst。默认 NJU，换主题用 `soda deck.md --theme ipads`。

想改颜色或标识，运行 `soda theme` 查看中文写法，`soda theme init` 生成 `theme.json`。改完后用 `soda deck.md --theme theme.json` 应用；字段表可离线运行 `soda theme --reference` 查看。

如需 Python API，[build.py](build.py) 展示对应调用；公式、媒体和更多转场见 [完整展示](https://github.com/nyllsom/soda/blob/main/examples/showcase/README.md)。
