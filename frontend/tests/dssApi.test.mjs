import test from 'node:test';
import assert from 'node:assert/strict';
import { fetchDemandForecast, fetchForecastModels } from '../src/services/dssApi.js';
import { setDemoModeEnabled } from '../src/services/apiClient.js';

test('production API errors propagate without a mock forecast', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Artifacts unavailable' }), { status: 503 });
  try {
    setDemoModeEnabled(false);
    await assert.rejects(fetchDemandForecast(), /Artifacts unavailable/);
  } finally { globalThis.fetch = original; }
});

test('explicit Demo Mode is labeled', async () => {
  const result = await fetchDemandForecast({}, { demo: true });
  assert.equal(result.is_mock, true);
  assert.equal(result.demo_mode, true);
  assert.equal(result.forecasts.length, 7);
});

test('client passes documented params and preserves nulls and exact predictions', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async (path) => {
    const url = new URL(path, 'http://localhost');
    assert.equal(url.searchParams.get('as_of_date'), '2017-08-24');
    assert.equal(url.searchParams.get('model_name'), 'causal_causal_history');
    assert.equal(url.searchParams.get('horizon'), '3');
    assert.equal(url.searchParams.has('cutoff_date'), false);
    return new Response(JSON.stringify({ forecasts: [{ predicted_guest_count: 0, actual_guest_count: null }],
      decision_support: { policy_version: 'dss-v2', state: 'NEUTRAL', insights: [], metadata: { status: 'READY' } } }));
  };
  try {
    const result = await fetchDemandForecast({ as_of_date: '2017-08-24', model_name: 'causal_causal_history', horizon: 3 });
    assert.equal(result.forecasts[0].predicted_guest_count, 0);
    assert.equal(result.forecasts[0].actual_guest_count, null);
    assert.equal(result.is_mock, false);
    assert.deepEqual(result.decision_support, { policy_version: 'dss-v2', state: 'NEUTRAL', insights: [], metadata: { status: 'READY' } });
  } finally { globalThis.fetch = original; }
});

test('live FastAPI response reaches the real frontend client', { skip: !process.env.DWDSS_API_BASE_URL }, async () => {
  const original = globalThis.fetch;
  globalThis.fetch = (path, options) => original(new URL(path, process.env.DWDSS_API_BASE_URL), options);
  try {
    const { models } = await fetchForecastModels();
    assert.equal(models.filter((m) => m.kind === 'daily').length, 3);
    const model = models.find((m) => m.kind === 'daily' && m.default);
    const result = await fetchDemandForecast({ model_name: model.id });
    assert.equal(result.is_mock, false);
    assert.equal(result.forecasts.length, 7);
    assert.equal(result.forecasts[0].forecast_date, '2017-09-01');
    assert.equal(result.summary.total_predicted_guests_7d, result.forecasts.reduce((s, r) => s + r.predicted_guest_count, 0));
    assert.ok(result.forecasts.every((r) => r.predicted_room_nights === null));
    assert.equal(result.decision_support.policy_version, 'dss-v2');
    assert.equal(result.forecasts[6].forecast_date, '2017-09-07');
    assert.ok(result.forecasts.every((r) => r.actual_guest_count === null));
    await assert.rejects(fetchDemandForecast({ model_name: 'xgboost_regressor' }), /Unsupported/);
  } finally { globalThis.fetch = original; }
});

test('default request forecasts from the last published date', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async (path) => {
    const url = new URL(path, 'http://localhost');
    assert.equal(url.searchParams.get('as_of_date'), '2017-08-31');
    assert.equal(url.searchParams.get('horizon'), '7');
    return new Response(JSON.stringify({ forecasts: [] }));
  };
  try { await fetchDemandForecast(); } finally { globalThis.fetch = original; }
});
