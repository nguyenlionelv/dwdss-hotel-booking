import test from 'node:test';
import assert from 'node:assert/strict';
import {
  formatChartAxis, formatDate, formatGuests, formatMetric, formatMrr, formatRate, formatReference,
  formatRelativeImprovement, formatShare, formatSignedPercent, formatUnits,
} from '../src/lib/dssFormat.mjs';

test('forecast and allocation formatting rounds presentation only', () => {
  const predicted = 165.83;
  const mrr = 0.102234;
  assert.equal(formatGuests(predicted), '166');
  assert.equal(formatGuests(991.708), '992');
  assert.equal(formatReference(136.0042), '136');
  assert.equal(formatChartAxis(1_000_000), '1M');
  assert.equal(formatMetric(30.92716), '30.93');
  assert.equal(formatMrr(mrr), '10.22%');
  assert.equal(formatShare(14.5316), '14.53%');
  assert.equal(formatUnits(14.5316), '14.53 units');
  assert.equal(formatSignedPercent(21.934), '+21.93%');
  assert.equal(formatRate(0.6551724), '65.52%');
  assert.equal(formatRelativeImprovement(0.008624564, 0.110847282), '+7.78%');
  assert.equal(formatDate('2017-08-25'), '25 Aug 2017');
  assert.equal(predicted, 165.83);
  assert.equal(mrr, 0.102234);
});

test('missing and invalid values never become zero', () => {
  for (const value of [null, undefined, NaN, Infinity, -Infinity, '']) {
    assert.equal(formatGuests(value), '—');
    assert.equal(formatMrr(value), '—');
    assert.equal(formatUnits(value), '—');
  }
  assert.equal(formatGuests(0), '0');
  assert.equal(formatMrr(0), '0.00%');
  assert.equal(formatDate('2017-02-30'), '—');
});
