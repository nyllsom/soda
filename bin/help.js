export function overviewHelp(version) {
  return `SODA ${version} · Markdown 演示编译器

从范例开始：
  soda example                              浏览范例
  soda example quickstart --copy my-talk     复制入门源码
  cd my-talk
  soda deck.md                              编译得到 deck.html

内容写在 .md，动画写在可选的同名 .soda；生成的 HTML 可直接分享。
编译用法：soda <deck.md> [motion.soda] [-o output.html]

按需查看帮助：
  soda help                 整体用法（也可用 soda --help）
  soda help compile         编译、动画、输出位置与依赖
  soda help theme           自定义主题：生成、修改、应用
  soda help example         预览和复制范例
  soda help check           检查稿件
  soda --version            查看版本

帮助、范例浏览和主题配置生成无需 Python。
编译需要 Python 3.12+；公式与 Typst 插图另需 Typst。
更多写法：https://github.com/nyllsom/soda/tree/main/examples
`;
}

export const compileHelp = `SODA · 编译帮助

  soda <deck.md> [motion.soda] [-o output.html]
  soda compile <deck.md> [motion.soda] [-o output.html]

最短流程：
  soda deck.md                              生成同目录的 deck.html
  soda deck.md motion.soda -o dist/talk.html 指定动画和输出
  soda deck.md --theme ipads                 切换内置主题
  soda deck.md --theme theme.json            使用自定义主题

动画与输出：
  省略动画文件时自动读取同名 .soda；找不到时生成静态演示。
  -o, --output <文件>    指定输出，自动创建父目录；已有输出会被覆盖
  --static              忽略同名动画，不能与显式动画文件同时使用
  --theme <名称或JSON>   nju（默认）、ipads 或自定义主题 JSON
  --target portable     默认单文件 HTML，本地素材内嵌，可以直接分享
  --target web          HTML 与相邻的 assets/ 目录，部署时一起上传

路径从哪里算：
  命令行中的 Markdown、动画、输出路径：相对当前工作目录。
  Markdown 中的资源、主题 JSON 路径：相对 Markdown 所在目录。
  主题中的标识图片路径：相对主题 JSON 所在目录。
  路径含空格时加引号，例如 soda "我的 演示.md" -o "导出/演示.html"。

编译前准备：
  Python 3.12+；可用 SODA_PYTHON 指定 Python 可执行文件。
  公式和 .typ 插图需要 Typst；可用 SODA_TYPST 指定其路径。
  场景打包工具 esbuild 已由 npm 安装。

编译后用浏览器打开 HTML；远程网页与媒体仍需联网。
只检查内容和时间轴：soda check deck.md
自定义主题的完整流程：soda help theme
soda html … 与 soda compile … 等效；加 --help 可再次查看本页。
`;

export const checkHelp = `SODA · 稿件检查

  soda check <deck.md> [motion.soda] [--static]

检查语法、对象引用和时间轴，不生成 HTML。
省略动画文件时自动读取同名 .soda；--static 忽略同名动画。
--static 不能与显式动画文件同时使用。
Markdown 和动画路径相对当前工作目录；资源路径相对 Markdown。
检查需要 Python 3.12+。最终排版请编译后在浏览器按 D 检查。
导出与依赖：soda help compile
`;

export function installationHint(version, command = 'soda') {
  return `SODA ${version} 已安装。
  使用总览：${command} help
  编译帮助：${command} help compile
  自定义主题：${command} help theme
  查看范例：${command} example
`;
}
