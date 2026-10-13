import { test } from 'node:test';
import assert from 'node:assert/strict';
import { markdownSlideIndex, motionSlideAt } from '../../bin/preview.js';

test('markdown change locator follows slide headings and ignores fenced headings', () => {
  const source = '# One\nintro\n```md\n## not-a-slide\n```\n## Two\nchanged\n';
  assert.equal(markdownSlideIndex(source, 1), 0);
  assert.equal(markdownSlideIndex(source, 3), 0);
  assert.equal(markdownSlideIndex(source, 6), 1);
});

test('motion change locator chooses the nearest preceding motion block', () => {
  const source = 'motion one {\n  title.fade_in();\n}\n\nmotion two {\n  title.fade_out();\n}\n';
  assert.equal(motionSlideAt(source, 1), 'one');
  assert.equal(motionSlideAt(source, 5), 'two');
  assert.equal(motionSlideAt(source, 0), 'one');
});


test('markdown notes headings stay on their owning slide', () => {
  const source = '## One\n::: notes\n## Hidden\n:::\n## Two\nBody';
  assert.equal(markdownSlideIndex(source, 2), 0);
  assert.equal(markdownSlideIndex(source, 5), 1);
});
