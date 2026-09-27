# 添加主题

默认 `academic` 是中性学术风格，`ipads` 加入机构配色和标识。布局共用同一套留白与对齐规则；换肤不改变内容或时间轴。

在 Markdown 开头指定主题，或只覆盖某次导出：

```yaml
---
theme: ipads
---
```

```python
export_html(deck, "demo.html", theme="ipads")
```

自己的主题放在演示项目中，不必修改已安装的包。例如 `talk/themes/lab.json`：

```json
{
  "extends": "academic",
  "name": "实验室",
  "primary": "#245a73",
  "accent": "#a65432"
}
```

在 `talk/deck.md` 的 front matter 中写 `theme: themes/lab.json`，或在 Python 中传入 `theme="themes/lab.json"`。JSON 路径相对 Markdown 目录；`compile_text` 则相对 `base_dir`。

`extends` 可以是 `academic` 或 `ipads`，省略时使用前者。只需写要覆盖的字段。完整字段见 [academic.json](../src/soda/themes/academic.json) 与 [ipads.json](../src/soda/themes/ipads.json)。字段名使用下划线，`"$primary"` 这样的值引用另一个字段，覆盖主色后引用仍会同步更新。

标识可以使用 `brand_logo`、`brand_label`、`logo_width`、`logo_height`；文件路径相对主题 JSON。`affiliation_logo` 是封面附属机构标识。继承 `ipads` 时不覆盖标识，会继续使用内置标识；设为 `null` 可移除。继承 `academic` 后添加标识时，请显式设置宽高，例如 `"logo_width": "220px"`、`"logo_height": "64px"`。

自定义素材也要使用语义颜色，才能随主题变化：

- SVG：`stroke="var(--soda-primary)"`、`fill="var(--soda-surface)"`，导出时替换。
- Typst：`rgb(sys.inputs.at("soda-primary", default: "#315b85"))`，编译时注入。
- JavaScript 场景：从容器的 `getComputedStyle(container)` 读取 `--soda-primary` 等变量。

示例见 [曲线 SVG](../examples/showcase/assets/curve.svg)、[Typst 插图](../examples/showcase/assets/pipeline.typ) 和 [场景模块](../examples/showcase/scene.js)。图表、技术图、公式和代码高亮已接入同一套颜色。外部素材中写死的色值、照片和视频不会被自动改色。

建议保留默认页边距、字号层级和内容宽度，先只改少量颜色与机构标识。浅底深字，强调色只突出需要关注的对象；不要为填满页面而拉伸表格。
