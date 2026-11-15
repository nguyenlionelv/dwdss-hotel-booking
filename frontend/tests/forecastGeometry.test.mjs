import test from 'node:test';
import assert from 'node:assert/strict';
import { forecastDomain, forecastLabelPosition, forecastNumber } from '../src/components/charts/forecastGeometry.js';

test('includes the post-cutoff actual peak that previously exceeded the domain', () => {
  const history = [{ target_guests: 130 }];
  const forecasts = [{ predicted_guest_count: 166, actual_guest_count: 213 }];
  const before = JSON.stringify({ history, forecasts });
  const domain = forecastDomain(history, forecasts);
  assert.equal(domain.min, 130 - (213 - 130) * .12);
  assert.equal(domain.max, 213 + (213 - 130) * .12);
  assert.equal(JSON.stringify({ history, forecasts }), before);
});

test('all displayed series and references fit with 12% upper and lower padding', () => {
  const domain = forecastDomain([{ target_guests: 0 }],
    [{ predicted_guest_count: 100, actual_guest_count: 1_000_000 }],
    { mean_guests_8w: 500, high_threshold: 2000, low_threshold: 10 });
  assert.equal(domain.min, -120000);
  assert.equal(domain.max, 1120000);
  for (const value of [0, 100, 1_000_000, 500, 2000, 10]) {
    const y = 26 + 210 - (value - domain.min) / (domain.max - domain.min) * 210;
    assert.ok(y > 26 + 6 && y < 236 - 6);
  }
});

test('equal and zero series have a finite, non-degenerate domain', () => {
  for (const value of [0, 100, .001]) {
    const domain = forecastDomain([{ target_guests: value }], [{ predicted_guest_count: value, actual_guest_count: value }]);
    assert.ok(Number.isFinite(domain.min) && Number.isFinite(domain.max));
    assert.ok(domain.min < value && domain.max > value);
  }
});

test('missing and invalid values stay gaps instead of becoming zero', () => {
  for (const value of [null, undefined, NaN, Infinity, '120']) assert.equal(forecastNumber(value), null);
  assert.equal(forecastNumber(0), 0);
  assert.equal(forecastDomain([{ target_guests: null }], [{ predicted_guest_count: null, actual_guest_count: NaN }]), null);
  assert.deepEqual(forecastDomain([], [{ predicted_guest_count: null, actual_guest_count: 500 }]), { min: 440, max: 560 });
});

test('domain includes only the historical slice actually rendered', () => {
  const history = [{ target_guests: 999999 }, ...Array.from({ length: 10 }, () => ({ target_guests: 100 }))];
  assert.deepEqual(forecastDomain(history), { min: 88, max: 112 });
});

test('marker labels fit horizontally and vertically at plot edges', () => {
  const plot = { left: 52, right: 250, top: 26, bottom: 236 };
  for (const [x, y] of [[52, 26], [250, 236], [100, 27]]) {
    const p = forecastLabelPosition(x, y, 60, 10, 3, plot);
    assert.ok(p.x - 30 >= plot.left && p.x + 30 <= plot.right);
    assert.ok(p.y - 10 >= plot.top && p.y + 3 <= plot.bottom);
  }
});
