import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { parseArgs } from 'node:util';

export const themeHelp = `SODA · 自定义主题帮助

  soda deck.md --theme ipads          切换内置主题：nju（默认）或 ipads
  soda theme init                    在当前目录生成 theme.json
  soda theme init themes/lab.json --from ipads
  soda theme --reference             离线查看全部字段和素材换色说明

在 Markdown 所在目录生成配置，修改需要的字段，再编译：
  soda theme init
  soda deck.md --theme theme.json

例如，编辑 theme.json：

  {
    "extends": "nju",
    "name": "我的主题",
    "primary": "#245a73",
    "accent": "#a65432"
  }

  extends       继承 nju 或 ipads；未填写的字段沿用它的设置
  name          主题名称
  primary       标题、强调、图表第一组数据的主色
  accent        图表第二组数据等的辅助强调色
  background    页面底色；foreground 为正文色；surface 为卡片底色
  brand_logo    自己的标识图片路径；brand_label 为图片的文字说明

主题 JSON 路径相对 Markdown；图片路径相对主题 JSON。
未改标识会保留原主题标识；brand_logo: null 可移除它。
继承 IPADS 时，affiliation_logo: null 可移除封面的 SJTU 标识。
颜色用 CSS 色值，尺寸写成 "160px"；JSON 不支持注释或末尾逗号。
只写要修改的字段。"$primary" 可引用主色；写死颜色的图片不会自动换色。
也可在 Markdown 开头的 --- 配置区写 theme: theme.json，省去每次传参。

查看说明、生成配置无需 Python；生成时不会覆盖已有文件。
soda help theme 与 soda theme --help 都可查看本页；编译细节见 soda help compile。
`;

export async function runTheme(packageRoot, argv) {
  const { values, positionals } = parseArgs({ args: argv, allowPositionals: true, options: {
    from: { type: 'string' }, reference: { type: 'boolean' },
    help: { type: 'boolean', short: 'h' },
  } });
  if (values.help) { process.stdout.write(themeHelp); return; }
  if (values.reference) {
    if (positionals.length || values.from) throw new Error('--reference 不与 init 或 --from 同时使用。');
    const reference = await readFile(path.join(packageRoot, 'examples/reference.md'), 'utf8');
    const section = reference.split('\n## 自定义主题\n')[1];
    if (!section) throw new Error('安装包中的主题说明不完整，请重新安装 SODA。');
    console.log(`SODA · 自定义主题\n${section.split('\n## ')[0]}`);
    return;
  }
  if (!positionals.length && !values.from) { process.stdout.write(themeHelp); return; }
  if (positionals[0] !== 'init' || positionals.length > 2) throw new Error('用 soda theme 查看写法，或用 soda theme init [theme.json] 生成配置。');
  const parent = values.from || 'nju';
  if (!['nju', 'ipads'].includes(parent)) throw new Error('--from 请选择 nju 或 ipads。');
  const target = path.resolve(positionals[1] || 'theme.json');
  if (path.extname(target).toLowerCase() !== '.json') throw new Error('主题文件请使用 .json 扩展名。');
  const base = JSON.parse(await readFile(path.join(packageRoot, 'src/soda/themes', `${parent}.json`), 'utf8'));
  const theme = { extends: parent, name: '我的主题', primary: base.primary, accent: base.accent };
  await mkdir(path.dirname(target), { recursive: true });
  try { await writeFile(target, JSON.stringify(theme, null, 2) + '\n', { flag: 'wx' }); }
  catch (error) {
    if (error.code === 'EEXIST') throw new Error(`目标已存在，未覆盖：${target}`);
    throw error;
  }
  console.log(`已创建 ${target}（继承 ${parent}，包括原主题标识）。\n修改 primary / accent 后，用 --theme 指定这个文件；路径相对 Markdown 所在目录。\n将它放在 deck.md 旁并命名为 theme.json，即可运行：soda deck.md --theme theme.json\n字段与标识说明：soda help theme；完整参考：soda theme --reference`);
}
