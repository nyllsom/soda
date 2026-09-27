import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const cli = path.join(root, 'bin/soda.js');
const run = (args, options = {}) => spawnSync(process.execPath, [cli, ...args], { encoding: 'utf8', ...options });

test('help and version do not require Python', () => {
  const env = { ...process.env, SODA_PYTHON: '/missing/python' };
  const help = run(['--help'], { env });
  assert.equal(help.status, 0);
  assert.match(help.stdout, /soda <deck.md>/);
  assert.match(help.stdout, /soda example/);
  assert.match(help.stdout, /soda theme/);
  const version = run(['--version'], { env });
  const metadata = JSON.parse(readFileSync(path.join(root, 'package.json')));
  assert.equal(version.stdout.trim(), `SODA ${metadata.version}`);
  const pyproject = readFileSync(path.join(root, 'pyproject.toml'), 'utf8');
  assert.match(pyproject, new RegExp(`version = "${metadata.version.replaceAll('.', '\\.') }"`));
  const pythonVersion = readFileSync(path.join(root, 'src/soda/_version.py'), 'utf8');
  assert.ok(pythonVersion.includes(`__version__ = "${metadata.version}"`));
});

test('missing configured Python fails with an actionable message', () => {
  const result = run(['talk.md'], { env: { ...process.env, SODA_PYTHON: '/missing/python' } });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /SODA_PYTHON.*Python 3.12/);
  assert.doesNotMatch(result.stderr, /Traceback/);
});

test('installed-style launcher handles paths with spaces and explicit animation', t => {
  const cwd = mkdtempSync(path.join(tmpdir(), 'soda cli '));
  t.after(() => rmSync(cwd, { recursive: true, force: true }));
  const source = path.join(cwd, '中文 稿件.md');
  const motion = path.join(cwd, '动画.soda');
  writeFileSync(source, '## 结果 {#result}\n结论。 {#finding}\n');
  writeFileSync(motion, 'motion result { finding.fade_in(duration = 250ms); }');
  const result = run([source, motion, '-o', '输出/演示.html', '--theme', 'ipads'], { cwd });
  assert.equal(result.status, 0, result.stderr);
  const html = readFileSync(path.join(cwd, '输出/演示.html'), 'utf8');
  assert.match(html, /theme-ipads/);
  assert.match(html, /"end": 0.25/);
  assert.equal(run([source], { cwd }).status, 0);
  assert.ok(existsSync(path.join(cwd, '中文 稿件.html')));
  writeFileSync(motion, 'motion result { missing.fade_in(); }');
  const bad = run([source, motion], { cwd });
  assert.equal(bad.status, 1);
  assert.match(bad.stderr, /动画.soda:1:/);
});

test('example copy works without Python and never overwrites a directory', t => {
  const cwd = mkdtempSync(path.join(tmpdir(), 'soda example '));
  t.after(() => rmSync(cwd, { recursive: true, force: true }));
  const env = { ...process.env, SODA_PYTHON: '/missing/python' };
  const copied = run(['example', '--copy', '我的演示'], { cwd, env });
  assert.equal(copied.status, 0, copied.stderr);
  assert.match(copied.stdout, /soda theme init/);
  const source = path.join(cwd, '我的演示/deck.md');
  assert.match(readFileSync(source, 'utf8'), /内容先行/);
  writeFileSync(source, 'keep this');
  const repeated = run(['example', '--copy', '我的演示'], { cwd, env });
  assert.equal(repeated.status, 1);
  assert.match(repeated.stderr, /目标已存在/);
  assert.equal(readFileSync(source, 'utf8'), 'keep this');
  mkdirSync(path.join(cwd, 'empty'));
  assert.equal(run(['example', '--copy', 'empty'], { cwd, env }).status, 1);
});

test('example validates names, themes and conflicting options', () => {
  for (const args of [['bad'], ['showcase', '--theme', 'academic'], ['--port', '-1'], ['--theme', 'ipads'], ['--copy', 'foo', '--no-open']]) {
    const result = run(['example', ...args]);
    assert.equal(result.status, 1, result.stdout + result.stderr);
  }
});
