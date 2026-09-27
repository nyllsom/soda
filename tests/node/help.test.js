import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
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
