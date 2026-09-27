import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const cli = path.join(root, 'bin/soda.js');
const run = (args, options = {}) => spawnSync(process.execPath, [cli, ...args], { encoding: 'utf8', ...options });
const noPython = { ...process.env, SODA_PYTHON: '/missing/python' };

test('theme instructions and field reference work outside the repo without Python', t => {
  const cwd = mkdtempSync(path.join(tmpdir(), 'soda-theme-help-'));
  t.after(() => rmSync(cwd, { recursive: true, force: true }));
  for (const args of [[], ['--help'], ['--reference']]) {
    const result = run(['theme', ...args], { cwd, env: noPython });
    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout, /primary/);
    assert.match(result.stdout, /brand_logo/);
    assert.match(result.stdout, /soda theme init/);
    assert.match(result.stdout, /Markdown/);
  }
  const reference = run(['theme', '--reference'], { cwd, env: noPython });
  assert.match(reference.stdout, /code_highlight/);
  assert.match(reference.stdout, /SVG/);
});

test('generated themes can be edited and used from a separate working directory', t => {
  const cwd = mkdtempSync(path.join(tmpdir(), 'soda-theme-edit-'));
  t.after(() => rmSync(cwd, { recursive: true, force: true }));
  mkdirSync(path.join(cwd, '稿件'));
  for (const parent of ['nju', 'ipads']) {
    const target = `稿件/主题 ${parent}/lab.json`;
    const result = run(['theme', 'init', target, '--from', parent], { cwd, env: noPython });
    assert.equal(result.status, 0, result.stderr);
    const definition = JSON.parse(readFileSync(path.join(cwd, target), 'utf8'));
    assert.equal(definition.extends, parent);
    definition.primary = '#245a73';
    definition.code_keyword = '$primary';
    definition.brand_logo = 'logo.svg';
    definition.brand_label = '我的实验室';
    definition.affiliation_logo = null;
    writeFileSync(path.join(cwd, target), JSON.stringify(definition));
    writeFileSync(path.join(cwd, path.dirname(target), 'logo.svg'), '<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"><circle cx="4" cy="4" r="4"/></svg>');
    writeFileSync(path.join(cwd, '稿件/deck.md'), '# 自定义主题\n主题写在另一个目录。\n');
    const compiled = run(['稿件/deck.md', '--theme', `主题 ${parent}/lab.json`], { cwd });
    assert.equal(compiled.status, 0, compiled.stderr);
    const html = readFileSync(path.join(cwd, '稿件/deck.html'), 'utf8');
    assert.match(html, /--soda-primary:#245a73/);
    assert.match(html, /--soda-code-keyword:#245a73/);
    assert.match(html, /aria-label="我的实验室"/);
    assert.match(html, /data:image\/svg\+xml;base64,/);
    assert.doesNotMatch(html, /aria-label="Shanghai Jiao Tong University"/);
    writeFileSync(path.join(cwd, '稿件/deck.md'), `---\ntheme: 主题 ${parent}/lab.json\n---\n# 从 Markdown 选主题\n`);
    const frontmatter = run(['稿件/deck.md'], { cwd });
    assert.equal(frontmatter.status, 0, frontmatter.stderr);
    assert.match(readFileSync(path.join(cwd, '稿件/deck.html'), 'utf8'), /--soda-primary:#245a73/);
  }
});

test('theme init defaults are usable and existing files are preserved', t => {
  const cwd = mkdtempSync(path.join(tmpdir(), 'soda-theme-init-'));
  t.after(() => rmSync(cwd, { recursive: true, force: true }));
  const created = run(['theme', 'init'], { cwd, env: noPython });
  assert.equal(created.status, 0, created.stderr);
  const target = path.join(cwd, 'theme.json');
  assert.equal(JSON.parse(readFileSync(target, 'utf8')).extends, 'nju');
  writeFileSync(path.join(cwd, 'deck.md'), '# 继承主题\n');
  const compiled = run(['deck.md', '--theme', 'theme.json'], { cwd });
  assert.equal(compiled.status, 0, compiled.stderr);
  assert.match(readFileSync(path.join(cwd, 'deck.html'), 'utf8'), /aria-label="Nanjing University"/);
  writeFileSync(target, 'keep my theme');
  const repeated = run(['theme', 'init'], { cwd, env: noPython });
  assert.equal(repeated.status, 1);
  assert.match(repeated.stderr, /未覆盖/);
  assert.equal(readFileSync(target, 'utf8'), 'keep my theme');
  for (const args of [['init', 'bad.json', '--from', 'academic'], ['init', 'bad.md'], ['--from', 'nju'], ['--reference', 'init'], ['bad']]) {
    assert.equal(run(['theme', ...args], { cwd, env: noPython }).status, 1);
  }
  assert.equal(existsSync(path.join(cwd, 'bad.json')), false);
  assert.equal(existsSync(path.join(cwd, 'bad.md')), false);
});
