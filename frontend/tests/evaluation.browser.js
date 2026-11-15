async (page) => {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const base = 'http://localhost:5173';
  const two = value => new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
  const api = await page.request.get(`${base}/api/dss/demand-forecast?as_of_date=2017-08-24&horizon=7`);
  assert(api.ok(), 'Live forecast API unavailable');
  const data = await api.json();
  const evidence = [];

  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    const actualWidth = await page.evaluate(() => innerWidth);
    if (Math.abs(actualWidth - width) > 1) await page.setViewportSize({ width: Math.round(width * width / actualWidth), height: Math.round(900 * width / actualWidth) });
    await page.goto(`${base}/dss/demand-forecast`);
    await page.waitForFunction(() => document.querySelector('[data-testid="forecast-kpis"]')?.innerText.includes('Predicted Guests'));
    const headings = await page.locator('h2').allInnerTexts();
    for (const heading of ['7-Day Demand Forecast', 'Weekly Resource Allocation', 'Operational Demand Insights', 'Model & Decision Evaluation']) {
      assert(headings.includes(heading), `Missing dashboard section: ${heading}`);
    }
    const details = page.locator('[data-testid="model-decision-evaluation"]');
    await details.locator('summary').click();
    const ml = page.locator('section[aria-labelledby="ml-evaluation-heading"]');
    const dss = page.locator('section[aria-labelledby="dss-evaluation-heading"]');
    const selectedModel = data.model_comparison.find(model => model.is_selected);
    const selected = data.resource_allocation.policy_evaluation.validation_results;
    const chosen = selected.policies[selected.selected];
    assert((await ml.innerText()).includes(two(selectedModel.overall_mae)), 'Selected validation MAE changed');
    assert((await ml.innerText()).includes(two(selectedModel.overall_rmse)), 'Selected validation RMSE changed');
    assert(await ml.locator('tbody tr').count() === data.model_comparison.length, 'Model comparison lost a baseline');
    assert((await ml.locator('thead').innerText()).includes('h=7'), 'Horizon profile incomplete');
    assert((await dss.innerText()).includes(`${two(chosen.mean_mrr * 100)}%`), 'MRR ratio conversion incorrect');
    assert((await dss.innerText()).includes(`${two(chosen.median_mrr * 100)}%`), 'Median MRR conversion incorrect');
    assert(await dss.locator('tbody tr').count() === 6, 'Policy comparison lost a candidate');
    const baseline = selected.policies.uniform.mean_mrr;
    const improvement = chosen.mean_improvement_vs_uniform / baseline * 100;
    assert((await dss.innerText()).includes(`${two(improvement)}% relative MRR improvement`), 'Relative improvement conversion incorrect');
    assert((await dss.innerText()).includes('causal proxy forecasts, not saved-model validation'), 'Proxy caveat missing');
    assert(!(await page.locator('[data-testid="operational-support"]').innerText()).includes('Mean MRR'), 'Evaluation duplicated in allocation section');
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Horizontal page overflow');
    evidence.push({ width, modelRows: data.model_comparison.length, policyRows: 6, mrrPercent: two(chosen.mean_mrr * 100) });
  }
  return { passed: true, cases: evidence };
}
