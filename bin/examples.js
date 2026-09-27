import { createServer } from 'node:http';
import { cp, mkdir, readFile, readdir, realpath, stat } from 'node:fs/promises';
import { createReadStream } from 'node:fs';
import { spawn } from 'node:child_process';
import path from 'node:path';
import { parseArgs } from 'node:util';
import { writeHelp } from './terminal.js';

const examples = new Set(['quickstart', 'showcase']);
export const exampleHelp = `SODA · 范例帮助

  soda example                              打开范例目录
  soda example showcase --theme ipads        直接查看某个范例和主题
  soda example quickstart --copy my-talk     复制可编辑源码

范例：quickstart（四页入门）、showcase（十四页完整展示）。
预览与复制无需 Python；复制时省略名称默认 quickstart，不覆盖已有目录。
进入复制的目录后运行 soda deck.md；编译细节见 soda help compile。

预览选项：
  --theme nju|ipads   选择预生成的主题；需同时指定范例名
  --no-open          只显示预览地址，不自动打开浏览器
  --port <端口>      默认自动选择空闲端口；Ctrl+C 关闭本地服务
--copy 不与预览选项同时使用。自定义主题见 soda help theme。
`;
const types = {
  '.html': 'text/html; charset=utf-8', '.md': 'text/plain; charset=utf-8',
  '.soda': 'text/plain; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.py': 'text/plain; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.pdf': 'application/pdf',
  '.mp4': 'video/mp4', '.csv': 'text/plain; charset=utf-8', '.bib': 'text/plain; charset=utf-8',
  '.typ': 'text/plain; charset=utf-8',
};

function contained(root, candidate) {
  const relative = path.relative(root, candidate);
  return relative !== '..' && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative);
}

export function exampleServer(root) {
  return createServer(async (req, res) => {
    if (!['GET', 'HEAD'].includes(req.method)) {
      res.writeHead(405, { Allow: 'GET, HEAD' }); res.end(); return;
    }
    try {
      const url = new URL(req.url, 'http://127.0.0.1');
      const decoded = decodeURIComponent(url.pathname);
      const candidate = path.resolve(root, `.${decoded === '/' ? '/index.html' : decoded}`);
      if (!contained(root, candidate)) { res.writeHead(403); res.end(); return; }
      const file = await realpath(candidate);
      if (!contained(root, file)) { res.writeHead(403); res.end(); return; }
      const info = await stat(file);
      if (!info.isFile()) { res.writeHead(404); res.end(); return; }
      res.writeHead(200, {
        'Content-Type': types[path.extname(file)] || 'application/octet-stream',
        'Content-Length': info.size,
        'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff',
      });
      if (req.method === 'HEAD') res.end();
      else createReadStream(file).on('error', () => res.destroy()).pipe(res);
    } catch (error) {
      res.writeHead(error instanceof URIError ? 400 : 404); res.end();
    }
  });
}

function openBrowser(url) {
  const [command, ...args] = process.platform === 'darwin' ? ['open', url]
    : process.platform === 'win32' ? ['rundll32.exe', 'url.dll,FileProtocolHandler', url]
      : ['xdg-open', url];
  const child = spawn(command, args, { stdio: 'ignore', detached: true, windowsHide: true });
  child.on('error', () => console.log('浏览器未自动打开，请访问上面的地址。'));
  child.on('exit', code => { if (code) console.log('浏览器未自动打开，请访问上面的地址。'); });
  child.unref();
}

export async function runExample(packageRoot, argv) {
  const { values, positionals } = parseArgs({ args: argv, allowPositionals: true, options: {
    theme: { type: 'string' }, port: { type: 'string' }, copy: { type: 'string' },
    'no-open': { type: 'boolean' }, help: { type: 'boolean', short: 'h' },
  } });
  if (values.help) {
    writeHelp(exampleHelp);
    return;
  }
  const name = positionals[0];
  if (positionals.length > 1 || (name && !examples.has(name))) throw new Error('示例名请选择 quickstart 或 showcase。');
  if (values.theme && !['nju', 'ipads'].includes(values.theme)) throw new Error('示例主题请选择 nju 或 ipads。');
  if (values.copy && (values.theme || values.port || values['no-open'])) throw new Error('--copy 不与预览选项同时使用；复制后可修改 deck.md 的主题。');
  const root = await realpath(path.join(packageRoot, 'examples'));
  if (values.copy) {
    const destination = path.resolve(values.copy);
    const source = path.join(root, name || 'quickstart');
    if (contained(source, destination)) throw new Error('复制目录不能放在范例自身内部。');
    await mkdir(path.dirname(destination), { recursive: true });
    try { await mkdir(destination); }
    catch (error) {
      if (error.code === 'EEXIST') throw new Error(`目标已存在，未覆盖：${destination}`);
      throw error;
    }
    for (const entry of await readdir(source)) {
      await cp(path.join(source, entry), path.join(destination, entry), {
        recursive: true, force: false, errorOnExist: true,
        filter: item => !item.split(path.sep).includes('__pycache__') && !/\.py[co]$/.test(item),
      });
    }
    console.log(`已复制 ${name || 'quickstart'} 到 ${destination}\n进入该目录后运行：soda deck.md；编译帮助：soda help compile\n自定义主题：soda help theme 查看写法，soda theme init 生成配置。`);
    return;
  }
  if (values.theme && !name) throw new Error('指定主题时请同时选择示例，例如 soda example showcase --theme ipads。');
  const port = values.port === undefined ? 0 : Number(values.port);
  if (!Number.isInteger(port) || port < 0 || port > 65535 || values.port === '') throw new Error('端口应为 0–65535 的整数；0 表示自动选择。');
  const entry = name ? `preview/${name}-${values.theme || 'nju'}.html` : 'index.html';
  await readFile(path.join(root, entry));
  const server = exampleServer(root);
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, '127.0.0.1', resolve);
  });
  const address = `http://127.0.0.1:${server.address().port}/${name ? entry : ''}`;
  console.log(`SODA 范例：${address}\n按 Ctrl+C 结束预览。`);
  const shutdown = () => { server.close(); server.closeAllConnections(); };
  process.once('SIGINT', shutdown);
  process.once('SIGTERM', shutdown);
  server.once('close', () => {
    process.off('SIGINT', shutdown);
    process.off('SIGTERM', shutdown);
  });
  if (!values['no-open']) openBrowser(address);
}
