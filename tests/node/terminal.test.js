import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { stripVTControlCharacters } from 'node:util';
import { fileURLToPath } from 'node:url';
import { supportsColor } from '../../bin/terminal.js';

const cli = fileURLToPath(new URL('../../bin/soda.js', import.meta.url));
const env = { ...process.env, SODA_PYTHON: '/missing/python' };
delete env.NO_COLOR;
delete env.FORCE_COLOR;
const run = (args, overrides = {}) => spawnSync(process.execPath, [cli, ...args], {
  encoding: 'utf8', env: { ...env, ...overrides },
});

test('automatic color respects terminal capability and explicit overrides', () => {
  assert.equal(supportsColor({ isTTY: true }, {}), true);
  assert.equal(supportsColor({}, {}), false);
  assert.equal(supportsColor({ isTTY: true }, { TERM: 'dumb' }), false);
  assert.equal(supportsColor({ isTTY: true }, { NO_COLOR: '1' }), false);
  assert.equal(supportsColor({ isTTY: true }, { NO_COLOR: '' }), true);
  assert.equal(supportsColor({ isTTY: true }, { FORCE_COLOR: '0' }), false);
  for (const value of ['', '1', '2', '3']) {
    assert.equal(supportsColor({}, { FORCE_COLOR: value, TERM: 'dumb' }), true);
  }
  assert.equal(supportsColor({}, { FORCE_COLOR: '1', NO_COLOR: '1' }), true);
});

test('every help entry colors output without changing text, examples or spacing', () => {
  const cases = [
    [], ['help'], ['--help'], ['-h'],
    ['help', 'compile'], ['compile', '--help'], ['html', '-h'], ['deck.md', '--help'],
    ['help', 'theme'], ['theme'], ['theme', 'init', '--help'], ['theme', '--reference'],
    ['help', 'example'], ['example', '--help'],
    ['help', 'check'], ['check', '--help'],
  ];
  for (const args of cases) {
    const plain = run(args);
    const colored = run(args, { FORCE_COLOR: '1' });
    assert.equal(plain.status, 0, plain.stderr);
    assert.equal(colored.status, 0, colored.stderr);
    assert.equal(plain.stdout, stripVTControlCharacters(plain.stdout));
    assert.notEqual(colored.stdout, plain.stdout, args.join(' '));
    assert.equal(stripVTControlCharacters(colored.stdout), plain.stdout, args.join(' '));
  }
});
