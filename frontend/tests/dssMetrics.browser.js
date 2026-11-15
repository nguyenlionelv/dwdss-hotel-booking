async (page) => {
  // Run with Playwright browser_run_code_unsafe(filename=...). Real API cases
  // remain distinct from the explicitly intercepted zero-value UI fixture.
  const assert = (value, message) => { if (!value) throw new Error(message); };
  const base = 'http://localhost:5173';
  const guests = value => new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(value);
  const date = value => new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${value}T00:00:00Z`));
  const evidence = { liveCases: [], fixtureCases: [] };
  await page.goto(`${base}/dss/demand-forecast`);
  await page.locator('[data-testid="forecast-kpis"]').waitFor();
  const registry = await (await page.request.get(`${base}/api/dss/models`)).json();
  const models = registry.models.filter(model => model.kind === 'daily');
  assert(models.length === 3, 'Expected three saved daily model policies');

  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    const cssWidth = await page.evaluate(() => innerWidth);
    if (Math.abs(cssWidth - width) > 1) await page.setViewportSize({ width: Math.round(width * width / cssWidth), height: Math.round(900 * width / cssWidth) });
    for (const cutoff of ['2017-08-24', '2017-08-17']) {
      for (const model of models) {
        const response = await page.request.get(`${base}/api/dss/demand-forecast?as_of_date=${cutoff}&model_name=${model.id}&horizon=7`);
        assert(response.ok(), `API failed: ${model.id} at ${cutoff}`);
        const data = await response.json();
        await page.locator('#dss-cutoff-select').selectOption(cutoff);
        await page.locator('#dss-model-select').selectOption(model.id);
        await page.waitForFunction(total => document.querySelector('[data-testid="forecast-kpis"]')?.innerText.includes(total), guests(data.summary.total_predicted_guests_7d));
        const rendered = await page.evaluate(() => {
          const grid = document.querySelector('[data-testid="forecast-kpis"]');
          return {
            text: document.body.innerText,
            kpis: [...grid.children].map(el => el.innerText),
            boxes: [...grid.children].map(el => ({ width: el.getBoundingClientRect().width, x: el.getBoundingClientRect().x })),
            gridWidth: grid.getBoundingClientRect().width,
            documentWidth: document.documentElement.scrollWidth,
            viewport: innerWidth,
            forecastRows: document.querySelectorAll('table')[0].querySelectorAll('tbody tr').length,
            forecastValues: [...document.querySelectorAll('table')[0].querySelectorAll('tbody tr')].map(row => row.cells[2].innerText),
          };
        });
        assert(!/N\/A|Unavailable|unavailable|0H\s*\/\s*0N\s*\/\s*0L/.test(rendered.text), 'Misleading unavailable metric remains');
        assert(!/8-Week Rolling Mean|High Alert Threshold|Low Demand Threshold|Demand Tier Distribution|Projected Stay Nights|Projected stay-nights/.test(rendered.text), 'Unavailable metric is still visible');
        assert(rendered.kpis.length === 3, 'Expected guest total, peak and low cards');
        assert(rendered.kpis[1].includes(date(data.summary.peak_forecast_days[0].forecast_date)), 'Peak date changed');
        assert(rendered.kpis[1].includes(`${Math.round(data.summary.peak_forecast_days[0].predicted_guest_count)} guests`), 'Peak prediction changed');
        const low = data.forecasts.reduce((smallest, row) => !smallest || row.predicted_guest_count < smallest.predicted_guest_count ||
          row.predicted_guest_count === smallest.predicted_guest_count && row.forecast_date < smallest.forecast_date ? row : smallest, null);
        assert(rendered.kpis[2].includes(date(low.forecast_date)), 'Low date changed');
        assert(rendered.forecastRows === 7, 'Forecast rows lost');
        assert(rendered.forecastValues.every((text, i) => text === guests(data.forecasts[i].predicted_guest_count)), 'Rounded forecast values differ from the API');
        assert(rendered.documentWidth <= rendered.viewport + 1, 'Page overflows horizontally');
        if (width > 600) {
          assert(Math.abs(rendered.boxes[0].width - rendered.boxes[1].width) < 1, 'Unbalanced KPI widths');
          assert(rendered.boxes[0].width * 3 > rendered.gridWidth - 60, 'Empty KPI grid columns remain');
        } else {
          assert(rendered.boxes.every(box => Math.abs(box.width - rendered.gridWidth) < 1), 'Mobile cards do not fill their column');
        }
        evidence.liveCases.push({ width, cutoff, model: model.id,
          completeDays: data.dss_threshold_rule.complete_days_available,
          guestTotal: data.summary.total_predicted_guests_7d,
          peak: data.summary.peak_forecast_days[0], cards: rendered.kpis.length,
          noHorizontalOverflow: true, forecastPredictionsMatchApi: true });
      }
    }
  }

  // A valid zero is available data and must never be hidden or replaced.
  const zero = await (await page.request.get(`${base}/api/dss/demand-forecast`)).json();
  Object.assign(zero.dss_threshold_rule, { complete_days_available: 56, sufficient_history: true,
    mean_guests_8w: 0, std_guests_8w: 0, high_threshold: 0, low_threshold: 0 });
  zero.forecasts.forEach(row => Object.assign(row, { predicted_guest_count: 0,
    predicted_guest_count_display: 0, predicted_room_nights: 0, demand_level: 'HIGH',
    recommended_action: 'Fixture action' }));
  Object.assign(zero.summary, { total_predicted_guests_7d: 0, total_predicted_guests_7d_rounded: 0,
    demand_level_counts: { HIGH: 7 }, peak_forecast_days: [{ forecast_date: '2017-08-25', predicted_guest_count: 0, demand_level: 'HIGH' }] });
  await page.route('**/api/dss/demand-forecast?*', route => route.fulfill({ json: zero }));
  try {
    await page.reload();
    await page.waitForFunction(() => document.querySelector('[data-testid="forecast-kpis"]')?.firstElementChild?.innerText.includes('0'));
    const text = await page.locator('[data-testid="forecast-kpis"]').innerText();
    for (const label of ['8-Week Rolling Mean', 'High Alert Threshold', 'Low Demand Threshold', 'Demand Tier Distribution', 'Projected stay-nights: 0']) {
      assert(text.includes(label), `Valid metric was hidden: ${label}`);
    }
    assert(text.includes('7H / 0N / 0L'), 'Valid classified zero-category counts changed');
    assert(await page.getByRole('columnheader', { name: 'Projected Stay Nights', exact: true }).count() === 1, 'Supported stay-night data was hidden');
    evidence.fixtureCases.push({ kind: 'explicit browser fixture', sufficientHistory: true,
      zeroMetricsRetained: true, stayNightColumnRetained: true });
  } finally {
    await page.unroute('**/api/dss/demand-forecast?*');
    await page.reload();
    await page.locator('[data-testid="forecast-kpis"]').waitFor();
  }
  return { passed: true, ...evidence };
}
