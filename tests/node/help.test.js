import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const cli = path.join(root, 'bin/soda.js');
const noPython = { ...process.env, SODA_PYTHON: '/missing/python' };
const run = args => spawnSync(process.execPath, [cli, ...args], { encoding: 'utf8', env: noPython });

test('overview gives a starting workflow and topic help without Python', () => {
  const expected = run(['help']);
  assert.equal(expected.status, 0, expected.stderr);
  for (const args of [[], ['--help'], ['-h']]) assert.equal(run(args).stdout, expected.stdout);
  assert.match(expected.stdout, /soda example quickstart --copy my-talk/);
  assert.match(expected.stdout, /soda help compile/);
  assert.match(expected.stdout, /soda help theme/);
});

test('topic and subcommand help share offline content', () => {
  const cases = [
    ['compile', [['compile', '--help'], ['html', '-h'], ['deck.md', '--help'], ['compile']], /--target web/],
    ['theme', [['theme', '--help'], ['theme'], ['theme', 'init', '--help']], /primary/],
    ['example', [['example', '--help']], /--copy/],
    ['check', [['check', '--help'], ['check']], /--static/],
  ];
  for (const [topic, alternatives, content] of cases) {
    const expected = run(['help', topic]);
    assert.equal(expected.status, 0, expected.stderr);
    assert.match(expected.stdout, content);
    for (const args of alternatives) {
      const actual = run(args);
      assert.equal(actual.status, 0, actual.stderr);
      assert.equal(actual.stdout, expected.stdout, args.join(' '));
    }
  }
});

test('invalid help topics fail with guidance instead of invoking Python', () => {
  for (const args of [['help', 'unknown'], ['help', 'compile', 'extra'], ['--help', 'unknown']]) {
    const result = run(args);
    assert.equal(result.status, 1);
    assert.match(result.stderr, /soda help/);
    assert.doesNotMatch(result.stderr, /SODA_PYTHON|Traceback/);
  }
});

test('installation hints use commands appropriate to global, local and source installs', t => {
  const cwd = mkdtempSync(path.join(tmpdir(), 'soda-install-hint-'));
  t.after(() => rmSync(cwd, { recursive: true, force: true }));
  const { version } = JSON.parse(readFileSync(path.join(root, 'package.json'), 'utf8'));
  for (const [global, initial, command] of [
    ['true', root, 'soda'], ['false', cwd, 'npx soda'], ['false', root, 'node bin/soda.js'],
  ]) {
    const result = spawnSync(process.execPath, [path.join(root, 'bin/postinstall.js')], {
      cwd, encoding: 'utf8', env: { ...noPython, npm_config_global: global, INIT_CWD: initial },
    });
    assert.equal(result.status, 0, result.stderr);
    assert.ok(result.stdout.includes(`SODA ${version} 已安装`));
    assert.ok(result.stdout.includes(`使用总览：${command} help`));
    assert.ok(result.stdout.includes(`编译帮助：${command} help compile`));
    assert.ok(result.stdout.includes(`自定义主题：${command} help theme`));
  }
});
