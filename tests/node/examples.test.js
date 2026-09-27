import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm, writeFile, mkdir, symlink } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { exampleServer } from '../../bin/examples.js';

test('example server serves only its own files and handles HTTP methods', async t => {
  const work = await mkdtemp(path.join(tmpdir(), 'soda-server-'));
  const root = path.join(work, 'examples');
  await mkdir(root);
  await writeFile(path.join(root, 'index.html'), '<html lang="zh">范例</html>');
  await writeFile(path.join(work, 'outside.txt'), 'not public');
  const server = exampleServer(root);
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(async () => {
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
    await rm(work, { recursive: true, force: true });
  });
  const url = `http://127.0.0.1:${server.address().port}`;
  const response = await fetch(url);
  assert.equal(response.status, 200);
  assert.match(response.headers.get('content-type'), /text\/html/);
  assert.match(await response.text(), /范例/);
  const head = await fetch(url, { method: 'HEAD' });
  assert.equal(head.status, 200);
  assert.equal(await head.text(), '');
  assert.equal((await fetch(url, { method: 'POST' })).status, 405);
  assert.equal((await fetch(`${url}/missing`)).status, 404);
  assert.equal((await fetch(`${url}/%ZZ`)).status, 400);
  assert.equal((await fetch(`${url}/..%2foutside.txt`)).status, 403);
  if (process.platform !== 'win32') {
    await symlink(path.join(work, 'outside.txt'), path.join(root, 'link.txt'));
    assert.equal((await fetch(`${url}/link.txt`)).status, 403);
  }
});
