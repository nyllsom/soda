#!/usr/bin/env node

import { readFileSync, realpathSync } from 'node:fs';
import { createRequire } from 'node:module';
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { exampleHelp, runExample } from './examples.js';
import { runTheme, themeHelp } from './theme.js';
import { checkHelp, compileHelp, overviewHelp } from './help.js';
import { writeHelp } from './terminal.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const { version } = JSON.parse(readFileSync(path.join(root, 'package.json'), 'utf8'));
const args = process.argv.slice(2);

function showHelp(topics = []) {
  const pages = new Map([
    ['compile', compileHelp], ['html', compileHelp], ['theme', themeHelp],
    ['example', exampleHelp], ['check', checkHelp],
  ]);
  if (topics.length > 1 || (topics.length && !pages.has(topics[0]))) {
    throw new Error('帮助主题请选择 compile、theme、example 或 check；运行 soda help 查看总览。');
  }
  writeHelp(topics.length ? pages.get(topics[0]) : overviewHelp(version));
}

function wantsHelp(argv) {
  const end = argv.indexOf('--');
  return argv.slice(0, end < 0 ? argv.length : end).some(arg => ['--help', '-h'].includes(arg));
}

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
  if (!args.length) showHelp();
  else if (['--help', '-h', 'help'].includes(args[0])) showHelp(args.slice(1));
  else if (['--version', '-v'].includes(args[0])) console.log(`SODA ${version}`);
  else if (args[0] === 'example') await runExample(root, args.slice(1));
  else if (args[0] === 'theme') await runTheme(root, args.slice(1));
  else if (wantsHelp(args) || (args.length === 1 && ['compile', 'html', 'check'].includes(args[0]))) {
    showHelp([args[0] === 'check' ? 'check' : 'compile']);
  }
  else compile();
} catch (error) {
  console.error(`soda: ${error.message}`);
  process.exitCode = 1;
}
