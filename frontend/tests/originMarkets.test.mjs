import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildTopCountryBarItems,
  formatSharePct,
} from '../src/services/analyticsApi.js';
import { MOCK_ANALYTICS_IMPACT } from '../src/data/mockData.js';

test('formatSharePct formats integers, decimals, and nullish values consistently', () => {
  assert.equal(formatSharePct(8), '8.0%');
  assert.equal(formatSharePct(17.4), '17.4%');
  assert.equal(formatSharePct(null), '0.0%');
  assert.equal(formatSharePct(undefined), '0.0%');
});

test('buildTopCountryBarItems uses guests exclusively without room_nights fallback', () => {
  const items = buildTopCountryBarItems([
    {
      code: 'PRT',
      name: 'Portugal',
      guests: 0,
      room_nights: 54210,
      share_pct: 8,
    },
    {
      code: 'FRA',
      name: 'France',
      guests: undefined,
      room_nights: 45120,
      share_pct: 17.4,
    },
    {
      code: 'DEU',
      name: 'Germany',
      guests: null,
      room_nights: 31890,
      share_pct: null,
    },
  ]);

  assert.deepEqual(items, [
    {
      label: 'Portugal (PRT)',
      value: 0,
      formattedValue: '0 (8.0%)',
      color: 'series1',
    },
    {
      label: 'France (FRA)',
      value: 0,
      formattedValue: '0 (17.4%)',
      color: 'series3',
    },
    {
      label: 'Germany (DEU)',
      value: 0,
      formattedValue: '0 (0.0%)',
      color: 'series3',
    },
  ]);
});

test('buildTopCountryBarItems preserves order, caps at 5, assigns semantic tokens, and formats values', () => {
  const input = [
    { code: 'PRT', name: 'Portugal', guests: 12000, share_pct: 24.5 },
    { code: 'FRA', name: 'France', guests: 9500, share_pct: 19 },
    { code: 'DEU', name: 'Germany', guests: 6100, share_pct: 12.2 },
    { code: 'GBR', name: 'United Kingdom', guests: 4000, share_pct: 8 },
    { code: 'ESP', name: 'Spain', guests: 2500, share_pct: 5.0 },
    { code: 'ITA', name: 'Italy', guests: 1800, share_pct: 3.6 },
    { code: 'UNK', name: 'Unknown', guests: 500, share_pct: 1.0 },
  ];

  const items = buildTopCountryBarItems(input);

  assert.equal(items.length, 5);
  assert.deepEqual(
    items.map((item) => item.label),
    [
      'Portugal (PRT)',
      'France (FRA)',
      'Germany (DEU)',
      'United Kingdom (GBR)',
      'Spain (ESP)',
    ]
  );
  assert.deepEqual(
    items.map((item) => item.color),
    ['series1', 'series3', 'series3', 'series5', 'series5']
  );
  assert.deepEqual(
    items.map((item) => item.formattedValue),
    [
      '12,000 (24.5%)',
      '9,500 (19.0%)',
      '6,100 (12.2%)',
      '4,000 (8.0%)',
      '2,500 (5.0%)',
    ]
  );
  assert.deepEqual(buildTopCountryBarItems(null), []);
  assert.deepEqual(buildTopCountryBarItems(), []);
});

test('MOCK_ANALYTICS_IMPACT.top_countries produces 5 strictly descending items with formatted labels', () => {
  const items = buildTopCountryBarItems(MOCK_ANALYTICS_IMPACT.top_countries);

  assert.equal(items.length, 5);
  for (let i = 1; i < items.length; i++) {
    assert.ok(
      items[i - 1].value > items[i].value,
      `Expected index ${i - 1} (${items[i - 1].value}) > index ${i} (${items[i].value})`
    );
  }
  for (const item of items) {
    assert.match(item.formattedValue, /^[\d,]+ \(\d+\.\d%\)$/);
  }
  assert.deepEqual(
    items.map((item) => item.formattedValue),
    [
      '18,450 (20.8%)',
      '14,820 (16.7%)',
      '10,140 (11.5%)',
      '8,790 (9.9%)',
      '7,420 (8.4%)',
    ]
  );
});
