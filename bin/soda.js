#!/usr/bin/env node

import { readFileSync, realpathSync } from 'node:fs';
import { createRequire } from 'node:module';
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { runExample } from './examples.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const { version } = JSON.parse(readFileSync(path.join(root, 'package.json'), 'utf8'));
const args = process.argv.slice(2);

const help = `SODA ${version} · Markdown 演示编译器

  soda <deck.md> [motion.soda] [-o output.html]
  soda check <deck.md> [motion.soda]
  soda example [quickstart|showcase] [--theme nju|ipads]
  soda example [quickstart|showcase] --copy <目录>

编译：
  省略动画文件时自动读取同名 .soda；省略输出时生成同目录同名 .html。
  -o, --output <文件>    输出路径
  --theme <名称或JSON>   nju（默认）、ipads 或项目主题 JSON
  --static              忽略同名动画
  --target portable|web 单文件 HTML（默认）或 HTML + assets/

范例：
  soda example          打开范例目录；无需 Python 或 Typst
  --no-open             只显示本地预览地址
  --port <端口>         默认自动选择空闲端口；Ctrl+C 结束预览
  --copy <目录>         复制可编辑源码；默认 quickstart，不覆盖已有目录

  -h, --help            查看帮助
  -v, --version         查看版本

编译稿件需要 Python 3.12+；公式需要 Typst。SODA_PYTHON 可指定 Python 路径。
使用说明：https://github.com/nyllsom/soda/tree/main/examples
`;

function pythonCommand() {
  const configured = process.env.SODA_PYTHON;
  const candidates = configured ? [[configured]] : (
    process.platform === 'win32'
      ? [['py', '-3'], ['python3'], ['python']]
      : [['python3'], ['python']]
  );
  for (const command of candidates) {
    const probe = spawnSync(command[0], [...command.slice(1), '-I', '-c',
      'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)'],
    { stdio: 'ignore', timeout: 5000, windowsHide: true });
    if (probe.status === 0) return command;
  }
  throw new Error(configured
    ? `SODA_PYTHON 指定的程序不可用或低于 Python 3.12：${configured}`
    : '编译需要 Python 3.12+。请安装后重试，或用 SODA_PYTHON 指定可执行文件。查看范例可直接运行 soda example。');
}

function compile() {
  const command = pythonCommand();
  const env = { ...process.env };
  if (!env.SODA_ESBUILD) {
    const require = createRequire(import.meta.url);
    const esbuildPackage = path.dirname(require.resolve('esbuild/package.json'));
    // Point Python at the native binary, including Windows installs where bin/esbuild is JS.
    const platform = `${process.platform}-${process.arch}`;
    const subpath = process.platform === 'win32' ? 'esbuild.exe' : 'bin/esbuild';
    const packageName = process.platform === 'android' ? `@esbuild/android-${process.arch}` : `@esbuild/${platform}`;
    try {
      env.SODA_ESBUILD = require.resolve(`${packageName}/${subpath}`);
    } catch {
      const fallback = path.join(esbuildPackage, 'bin', 'esbuild');
      if (process.platform !== 'win32') env.SODA_ESBUILD = realpathSync(fallback);
    }
  }
  const bootstrap = 'import sys; sys.path.insert(0, sys.argv.pop(1)); from soda.cli import main; raise SystemExit(main())';
  const child = spawn(command[0], [...command.slice(1), '-I', '-c', bootstrap, path.join(root, 'src'), ...args],
    { stdio: 'inherit', env, windowsHide: true });
  child.on('error', error => { console.error(`soda: ${error.message}`); process.exitCode = 1; });
  const interrupt = signal => child.kill(signal);
  const onInterrupt = () => interrupt('SIGINT');
  const onTerminate = () => interrupt('SIGTERM');
  process.on('SIGINT', onInterrupt);
  process.on('SIGTERM', onTerminate);
  child.on('exit', (code, signal) => {
    process.off('SIGINT', onInterrupt);
    process.off('SIGTERM', onTerminate);
    process.exitCode = code ?? (signal === 'SIGINT' ? 130 : 1);
  });
}

try {
  if (!args.length || ['--help', '-h', 'help'].includes(args[0])) process.stdout.write(help);
  else if (['--version', '-v'].includes(args[0])) console.log(`SODA ${version}`);
  else if (args[0] === 'example') await runExample(root, args.slice(1));
  else compile();
} catch (error) {
  console.error(`soda: ${error.message}`);
  process.exitCode = 1;
}
