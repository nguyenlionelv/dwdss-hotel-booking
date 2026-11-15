import test from 'node:test';
import assert from 'node:assert/strict';
import { layoutAxisLabels } from '../src/components/charts/axisLabels.js';

function checkBounds(labels, left, right, gap = 12) {
  for (let index = 0; index < labels.length; index++) {
    assert.ok(labels[index].left >= left);
    assert.ok(labels[index].right <= right);
    if (index) assert.ok(labels[index].left >= labels[index - 1].right + gap);
  }
}

test('dense weekly labels never collide with the forced last date or clip at either edge', () => {
  for (const width of [130, 240, 540, 1050, 1600]) {
    const series = Array.from({ length: 105 }, (_, index) => ({
      text: `2017-W${String(index + 1).padStart(2, '0')}`, index,
      width: 66, x: 50 + (index + 0.5) / 105 * width,
    }));
    const labels = layoutAxisLabels(series, 50, 50 + width);
    checkBounds(labels, 50, 50 + width);
    assert.equal(labels[labels.length - 1].index, 104);
    if (width >= 240) assert.equal(labels[0].index, 0);
  }
});

test('variable length date labels reserve their actual measured widths', () => {
  const labels = layoutAxisLabels([
    { text: '1 Sept', x: 12, width: 36 },
    { text: '12 Sept 2017', x: 70, width: 96 },
    { text: '20 Sept', x: 110, width: 44 },
    { text: '30 Sept', x: 145, width: 44 },
  ], 0, 150);
  checkBounds(labels, 0, 150);
  assert.equal(labels[0].text, '1 Sept');
  assert.equal(labels[labels.length - 1].text, '30 Sept');
});

test('tiny plots show complete dates rather than overlapping or clipped labels', () => {
  const input = [{ text: '2017-W01', x: 0, width: 66 }, { text: '2017-W02', x: 90, width: 66 }];
  const before = JSON.stringify(input);
  const labels = layoutAxisLabels(input, 0, 90);
  assert.equal(labels.length, 1);
  assert.equal(labels[0].text, '2017-W02');
  checkBounds(labels, 0, 90);
  assert.deepEqual(layoutAxisLabels(input, 0, 20), []);
  assert.equal(JSON.stringify(input), before);
});

test('empty and invalid plot widths are handled without invalid positions', () => {
  assert.deepEqual(layoutAxisLabels([], 0, 100), []);
  assert.deepEqual(layoutAxisLabels([{ text: 'date', width: 20, x: 0 }], 5, 5), []);
});
