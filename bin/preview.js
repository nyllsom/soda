import { createServer } from 'node:http';
import { watch } from 'node:fs';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { parseArgs } from 'node:util';
import { writeHelp } from './terminal.js';

export const previewHelp = `SODA · 热更新预览

  soda preview <deck.md> [motion.soda]

保存 Markdown、动画或同目录素材后自动重新编译并刷新浏览器。
修改 Markdown 时跳到修改所在页；修改 .soda 时跳到对应 motion 页。
编译失败会保留上一版页面并显示错误，修正保存后自动恢复。

选项：
  --theme <名称或JSON>   nju（默认）、ipads 或自定义主题 JSON
  --static              忽略同名 .soda 动画
  --no-open             只显示预览地址，不自动打开浏览器
  --port <端口>         默认自动选择空闲端口；0 也表示自动选择
`;

const NO_CHANGE = Symbol('no-change');

const watchedExtensions = new Set([
  '.md', '.soda', '.json', '.typ', '.py', '.js', '.mjs', '.jsx', '.ts', '.tsx', '.svg',
  '.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf', '.mp4', '.csv', '.bib',
]);

function openBrowser(url) {
  const [command, ...args] = process.platform === 'darwin' ? ['open', url]
    : process.platform === 'win32' ? ['rundll32.exe', 'url.dll,FileProtocolHandler', url]
      : ['xdg-open', url];
  const child = spawn(command, args, { stdio: 'ignore', detached: true, windowsHide: true });
  child.on('error', () => console.log('浏览器未自动打开，请访问上面的地址。'));
  child.on('exit', code => { if (code) console.log('浏览器未自动打开，请访问上面的地址。'); });
  child.unref();
}

function firstChangedLine(before, after) {
  if (before === after) return null;
  const a = before.split(/\r?\n/);
  const b = after.split(/\r?\n/);
  const shared = Math.min(a.length, b.length);
  for (let i = 0; i < shared; i += 1) {
    if (a[i] !== b[i]) return i;
  }
  return shared;
}

export function markdownSlideIndex(source, changedLine) {
  if (changedLine == null) return null;
  const lines = source.split(/\r?\n/);
  let slide = -1;
  let fence = null;
  let notes = false;
  let notesFence = null;
  for (let i = 0; i <= Math.min(changedLine, lines.length - 1); i += 1) {
    const line = lines[i];
    if (notes) {
      const marker = line.match(/^ {0,3}(`{3,}|~{3,})/);
      if (notesFence) {
        if (marker && marker[1][0] === notesFence[0] && marker[1].length >= notesFence.length && !line.slice(marker[0].length).trim()) notesFence = null;
      } else if (/^ {0,3}:::[ \t]*$/.test(line)) {
        notes = false;
      } else if (marker) {
        notesFence = marker[1];
      }
      continue;
    }
    const fenceMatch = line.match(/^\s{0,3}(`{3,}|~{3,})/);
    if (fenceMatch) {
      const marker = fenceMatch[1];
      if (fence && marker[0] === fence[0] && marker.length >= fence.length) fence = null;
      else if (fence == null) fence = marker;
      continue;
    }
    if (fence != null) continue;
    if (line.trim() === "::: notes") { notes = true; continue; }
    if (/^\s{0,3}#{1,2}(?:[ \t]+|$)/.test(line)) slide += 1;
  }
  return Math.max(0, slide);
}

export function motionSlideAt(source, changedLine) {
  if (changedLine == null) return null;
  const lines = source.split(/\r?\n/);
  let slide = null;
  for (let i = 0; i <= Math.min(changedLine, lines.length - 1); i += 1) {
    const match = lines[i].match(/^\s*motion\s+([A-Za-z_][A-Za-z0-9_]*)\b/);
    if (match) slide = match[1];
  }
  return slide;
}

function slideIndexById(html, slideId) {
  if (!slideId) return null;
  const escaped = slideId.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const byOrder = new RegExp(`<article\\b[^>]*data-slide=['"]${escaped}['"][^>]*data-index=['"](\\d+)['"]`);
  const reversed = new RegExp(`<article\\b[^>]*data-index=['"](\\d+)['"][^>]*data-slide=['"]${escaped}['"]`);
  const match = html.match(byOrder) || html.match(reversed);
  return match ? Number(match[1]) : null;
}

function previewClient() {
  return `<script>
(() => {
  const key = 'soda-preview-restore';
  const errorId = 'soda-preview-error';

  function showError(message) {
    let box = document.getElementById(errorId);
    if (!box) {
      box = document.createElement('pre');
      box.id = errorId;
      Object.assign(box.style, {
        position: 'fixed', left: '16px', right: '16px', bottom: '16px', zIndex: '2147483647',
        margin: '0', padding: '12px 14px', maxHeight: '38vh', overflow: 'auto',
        borderRadius: '8px', background: 'rgba(30, 24, 24, .96)', color: '#ffd7d7',
        font: '13px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
        boxShadow: '0 8px 30px rgba(0,0,0,.28)', whiteSpace: 'pre-wrap'
      });
      document.body.appendChild(box);
    }
    box.textContent = message;
  }

  function restore() {
    const raw = sessionStorage.getItem(key);
    if (!raw || !window.sodaTimeline) return;
    sessionStorage.removeItem(key);
    try {
      const state = JSON.parse(raw);
      if (Number.isInteger(state.slideIndex)) {
        const stop = window.sodaTimeline.stops.find(item => item.slide_index === state.slideIndex);
        if (stop) window.sodaTimeline.seek(stop.time);
      } else if (Number.isFinite(state.time)) {
        window.sodaTimeline.seek(Math.min(state.time, window.sodaTimeline.duration));
      }
    } catch {}
  }

  restore();
  const events = new EventSource('/__soda_preview_events');
  events.addEventListener('built', event => {
    const update = JSON.parse(event.data);
    const currentTime = window.sodaTimeline?.time ?? 0;
    sessionStorage.setItem(key, JSON.stringify(
      Number.isInteger(update.slideIndex) ? { slideIndex: update.slideIndex } : { time: currentTime }
    ));
    location.reload();
  });
  events.addEventListener('soda-error', event => {
    const update = JSON.parse(event.data);
    showError(update.message || 'SODA preview build failed');
  });
})();
</script>`;
}

function injectClient(html) {
  const client = previewClient();
  const index = html.lastIndexOf('</body>');
  return index < 0 ? html + client : html.slice(0, index) + client + html.slice(index);
}

function errorPage(message) {
  const escaped = String(message).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
  return `<!doctype html><html><head><meta charset="utf-8"><title>SODA preview</title></head>
<body style="margin:0;background:#171717;color:#eee;font:14px/1.5 ui-monospace,monospace">
<pre style="white-space:pre-wrap;margin:24px">${escaped}</pre>${previewClient()}</body></html>`;
}

function compileOnce(packageRoot, args, cwd) {
  return new Promise(resolve => {
    const child = spawn(process.execPath, [path.join(packageRoot, 'bin/soda.js'), ...args], {
      cwd, env: process.env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    child.stdout.setEncoding('utf8');
    child.stderr.setEncoding('utf8');
    child.stdout.on('data', chunk => { stdout += chunk; });
    child.stderr.on('data', chunk => { stderr += chunk; });
    child.on('error', error => resolve({ code: 1, stdout, stderr: error.message }));
    child.on('exit', code => resolve({ code: code ?? 1, stdout, stderr }));
  });
}

function shouldWatch(filename) {
  if (!filename) return true;
  const normalized = filename.split(path.sep);
  if (normalized.some(part => part === '.git' || part === 'node_modules' || part === '__pycache__')) return false;
  return watchedExtensions.has(path.extname(filename).toLowerCase());
}

export async function runPreview(packageRoot, argv) {
  const { values, positionals } = parseArgs({
    args: argv,
    allowPositionals: true,
    options: {
      theme: { type: 'string' },
      static: { type: 'boolean' },
      port: { type: 'string' },
      'no-open': { type: 'boolean' },
      help: { type: 'boolean', short: 'h' },
    },
  });
  if (values.help) {
    writeHelp(previewHelp);
    return;
  }
  if (positionals.length < 1 || positionals.length > 2) {
    throw new Error('preview 需要 Markdown 路径，可选第二个参数为 .soda 动画路径。');
  }
  if (values.static && positionals[1]) throw new Error('--static 不能与显式动画文件同时使用。');

  const cwd = process.cwd();
  const source = path.resolve(cwd, positionals[0]);
  if (path.extname(source).toLowerCase() !== '.md') throw new Error('preview 内容文件必须是 .md。');
  const motion = values.static ? null : path.resolve(
    cwd, positionals[1] || path.join(path.dirname(source), `${path.basename(source, path.extname(source))}.soda`)
  );
  if (positionals[1] && path.extname(motion).toLowerCase() !== '.soda') {
    throw new Error('preview 动画文件必须是 .soda。');
  }
  const port = values.port === undefined ? 0 : Number(values.port);
  if (!Number.isInteger(port) || port < 0 || port > 65535 || values.port === '') {
    throw new Error('端口应为 0–65535 的整数；0 表示自动选择。');
  }

  const tempRoot = await mkdtemp(path.join(tmpdir(), 'soda-preview-'));
  const output = path.join(tempRoot, 'index.html');
  let sourceText = await readFile(source, 'utf8');
  let motionText = '';
  try { if (motion) motionText = await readFile(motion, 'utf8'); } catch (error) {
    if (positionals[1] || error.code !== 'ENOENT') throw error;
  }

  let rendered = null;
  let lastError = null;
  let version = 0;
  let building = false;
  let queued = false;
  let pendingCause = null;
  const clients = new Set();

  const broadcast = (event, data) => {
    const payload = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
    for (const client of clients) client.write(payload);
  };

  const buildArgs = () => {
    const result = [source];
    if (positionals[1]) result.push(motion);
    if (values.static) result.push('--static');
    if (values.theme) result.push('--theme', values.theme);
    result.push('--target', 'portable', '-o', output);
    return result;
  };

  async function detectTarget(cause) {
    if (!cause) return null;
    const resolved = path.resolve(cause);
    if (resolved === source) {
      const next = await readFile(source, 'utf8');
      const line = firstChangedLine(sourceText, next);
      sourceText = next;
      if (line == null) return NO_CHANGE;
      return markdownSlideIndex(next, line);
    }
    if (motion && resolved === motion) {
      let next = '';
      try { next = await readFile(motion, 'utf8'); } catch (error) {
        if (error.code !== 'ENOENT') throw error;
      }
      const line = firstChangedLine(motionText, next);
      motionText = next;
      if (line == null) return NO_CHANGE;
      return { motionSlide: motionSlideAt(next, line) };
    }
    return null;
  }

  async function rebuild(cause = null, initial = false) {
    pendingCause = cause || pendingCause;
    if (building) {
      queued = true;
      return;
    }
    building = true;
    do {
      queued = false;
      const currentCause = pendingCause;
      pendingCause = null;
      let target = null;
      try {
        target = await detectTarget(currentCause);
        if (target === NO_CHANGE) continue;
      } catch (error) {
        lastError = error.message;
        broadcast('soda-error', { message: lastError });
        continue;
      }
      const result = await compileOnce(packageRoot, buildArgs(), cwd);
      if (result.code === 0) {
        rendered = await readFile(output, 'utf8');
        lastError = null;
        version += 1;
        let slideIndex = Number.isInteger(target) ? target : null;
        if (target && typeof target === 'object') {
          slideIndex = slideIndexById(rendered, target.motionSlide);
        }
        if (!initial) {
          broadcast('built', { version, slideIndex });
          console.log(`↻ 已更新${slideIndex == null ? '' : ` · 第 ${slideIndex + 1} 页`}`);
        }
      } else {
        lastError = (result.stderr || result.stdout || 'SODA preview build failed').trim();
        broadcast('soda-error', { message: lastError });
        console.error(lastError);
      }
      initial = false;
    } while (queued);
    building = false;
  }

  await rebuild(null, true);

  const server = createServer(async (req, res) => {
    try {
      const url = new URL(req.url, 'http://127.0.0.1');
      if (url.pathname === '/__soda_preview_events') {
        res.writeHead(200, {
          'Content-Type': 'text/event-stream; charset=utf-8',
          'Cache-Control': 'no-store',
          Connection: 'keep-alive',
        });
        res.write(': connected\n\n');
        clients.add(res);
        req.on('close', () => clients.delete(res));
        return;
      }
      if (url.pathname === '/favicon.ico') {
        res.writeHead(204); res.end(); return;
      }
      if (!['/', '/index.html'].includes(url.pathname)) {
        res.writeHead(404); res.end(); return;
      }
      const body = rendered ? injectClient(rendered) : errorPage(lastError || '等待首次编译……');
      res.writeHead(200, {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-store',
        'Content-Length': Buffer.byteLength(body),
      });
      res.end(body);
    } catch {
      res.writeHead(500); res.end();
    }
  });

  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, '127.0.0.1', resolve);
  });
  const address = `http://127.0.0.1:${server.address().port}/`;
  console.log(`SODA 热更新预览：${address}\n保存文件后自动重新渲染；按 Ctrl+C 结束。`);
  if (!values['no-open']) openBrowser(address);

  let timer = null;
  let cause = null;
  const watchers = [];
  const roots = new Set([path.dirname(source)]);
  if (motion) roots.add(path.dirname(motion));
  for (const root of roots) {
    try {
      const watcher = watch(root, { recursive: true }, (_event, filename) => {
        if (!shouldWatch(filename)) return;
        const changed = filename ? path.resolve(root, filename.toString()) : source;
        cause = changed;
        clearTimeout(timer);
        timer = setTimeout(() => rebuild(cause), 90);
      });
      watchers.push(watcher);
    } catch {
      const watcher = watch(root, (_event, filename) => {
        if (!shouldWatch(filename)) return;
        const changed = filename ? path.resolve(root, filename.toString()) : source;
        cause = changed;
        clearTimeout(timer);
        timer = setTimeout(() => rebuild(cause), 90);
      });
      watchers.push(watcher);
    }
  }

  const keepalive = setInterval(() => {
    for (const client of clients) client.write(': keepalive\n\n');
  }, 15000);

  const shutdown = async () => {
    clearInterval(keepalive);
    clearTimeout(timer);
    for (const watcher of watchers) watcher.close();
    for (const client of clients) client.end();
    server.close();
    server.closeAllConnections();
    await rm(tempRoot, { recursive: true, force: true });
  };
  process.once('SIGINT', shutdown);
  process.once('SIGTERM', shutdown);
  server.once('close', () => {
    process.off('SIGINT', shutdown);
    process.off('SIGTERM', shutdown);
  });
}
