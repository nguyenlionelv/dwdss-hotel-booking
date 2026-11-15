async (page) => {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const tab = await page.context().newPage();
  const base = 'http://localhost:5173';
  const guests = value => new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(value);
  const evidence = { liveCases: [], fixtureCases: [] };
  try {
    await tab.goto(`${base}/dss/demand-forecast`, { waitUntil: 'domcontentloaded' });
    await tab.locator('[data-testid="operational-support"]').waitFor();
    const registry = await (await tab.request.get(`${base}/api/dss/models`)).json();
    const models = registry.models.filter(model => model.kind === 'daily');
    for (const width of [1440, 390]) {
      await tab.setViewportSize({ width, height: 1000 });
      const css = await tab.evaluate(() => innerWidth);
      if (Math.abs(css-width)>1) await tab.setViewportSize({width:Math.round(width*width/css),height:Math.round(1000*width/css)});
      for (const model of models) {
        const response = await tab.request.get(`${base}/api/dss/demand-forecast?as_of_date=2017-08-24&model_name=${model.id}`);
        assert(response.ok(),'Live API failed');
        const data = await response.json();
        assert(data.decision_support.metadata.available_case_56.sample_count===53,'Expected truthful 53-day context');
        assert(data.dss_threshold_rule.sufficient_history===false,'Legacy strict classification changed');
        await tab.locator('#dss-model-select').selectOption(model.id);
        await tab.waitForFunction(total => document.querySelector('[data-testid="forecast-kpis"]')?.innerText.includes(total), guests(data.summary.total_predicted_guests_7d));
        const section = tab.locator('[data-testid="operational-support"]');
        const insightsSection = tab.locator('[data-testid="demand-insights"]');
        const lowDay = data.forecasts.reduce((lowest, row) => !lowest || row.predicted_guest_count < lowest.predicted_guest_count ||
          (row.predicted_guest_count === lowest.predicted_guest_count && row.forecast_date < lowest.forecast_date) ? row : lowest, null);
        const kpis = tab.locator('[data-testid="forecast-kpis"]');
        assert((await kpis.innerText()).includes('Peak Forecast Day'),'Peak KPI missing from forecast summary');
        assert((await kpis.innerText()).includes('Low Forecast Day'),'Low KPI missing from forecast summary');
        assert((await kpis.innerText()).includes(new Intl.DateTimeFormat('en-GB',{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(`${lowDay.forecast_date}T00:00:00Z`))),'Low KPI date differs from forecast minimum');
        if (width > 1000) {
          const positions = await kpis.evaluate(root => {
            const labels = [...root.querySelectorAll('div')].filter(el => !el.children.length);
            return ['Peak Forecast Day', 'Low Forecast Day'].map(text =>
              labels.find(el => el.textContent.trim() === text)?.getBoundingClientRect().top);
          });
          assert(positions.every(Number.isFinite) && Math.abs(positions[0]-positions[1])<2,'Peak and low KPIs should share a row on desktop');
        }
        assert(data.resource_allocation.status==='ready','Seven-day allocation missing');
        assert(data.resource_allocation.daily_allocation.length===7,'Allocation must cover seven dates');
        assert((await section.innerText()).includes('Weekly Resource Allocation'),'Allocation section missing');
        assert(!(await section.innerText()).includes('Mean MRR'),'Detailed MRR leaked into allocation decisions');
        assert(await tab.locator('[data-testid="model-decision-evaluation"]').count()===1,'Unified evaluation missing');
        assert((await section.innerText()).toLowerCase().includes(data.resource_allocation.selected_policy.replaceAll('_',' ')),'Selected policy missing');
        assert(await section.locator('[aria-label="Seven-day relative resource allocation chart"] time').count()===7,'Seven allocation bars not rendered');
        assert(await insightsSection.locator('article').count()===data.decision_support.insights.length,'UI insight count differs from API');
        if (!data.decision_support.insights.length) assert((await insightsSection.innerText()).includes('No supported planning insights'),'Neutral state missing');
        for (const insight of data.decision_support.insights) {
          assert((await insightsSection.innerText()).includes(insight.title),'Live insight missing');
          assert((await insightsSection.innerText()).includes(guests(insight.predicted_guests)),'Formatted forecast evidence missing');
        }
        assert(!/PARTIAL|COMPLETE|INSUFFICIENT_HISTORY|coverage|Peak Forecast Day|Low Forecast Day|Lowest Forecast Day/.test(await section.innerText()),'Technical or max/min copy leaked');
        assert(await tab.evaluate(() => document.documentElement.scrollWidth<=innerWidth+1),'Horizontal overflow');
        evidence.liveCases.push({width,model:model.id,state:data.decision_support.state,count:data.decision_support.insights.length,sampleCount:53});
      }
      const original = await (await tab.request.get(`${base}/api/dss/demand-forecast`)).json();
      const fixture = structuredClone(original);
      // Presentation-only fixtures: never used to assess engine accuracy or signal frequency.
      fixture.decision_support = { policy_version:'dss-v2',state:'ACTIONABLE',insights:[
        {forecast_date:'2017-08-25',signal:'ABOVE_TYPICAL_DEMAND',title:'Above typical demand',evidence:'210.0 forecast vs 135.0 typical Friday (+55.6%).',recommended_action:'Review reception and housekeeping readiness.'},
        {forecast_date:'2017-08-26',signal:'DEMAND_DROP',title:'Unusual demand decrease',evidence:'-85.0 forecast guests vs -10.0 typical change into Saturday.',recommended_action:'Reassess supply preparation and workload allocation.'},
        {forecast_date:'2017-08-27',signal:'DEMAND_SURGE',title:'Unusual demand increase',evidence:'+90.0 forecast guests vs +5.0 typical change into Sunday.',recommended_action:'Review staffing continuity across adjacent days.'},
      ]};
      const pattern='**/api/dss/demand-forecast?*';
      await tab.route(pattern,route=>route.fulfill({json:fixture}));
      await tab.reload({waitUntil:'domcontentloaded'});
      const cards=tab.locator('[data-testid="demand-insights"] article');
      await cards.first().waitFor();
      assert(await cards.count()===3,'Three API cards not rendered');
      for (let i=0;i<3;i++) {
        const insight=fixture.decision_support.insights[i], card=cards.nth(i);
        assert(await card.getAttribute('aria-label')===insight.title,'API title not rendered');
        assert(await card.locator('time').getAttribute('datetime')===insight.forecast_date,'API date not rendered');
        assert((await card.innerText()).includes(insight.evidence),'Numeric evidence not rendered');
        assert((await card.innerText()).includes(insight.recommended_action),'API action not rendered');
      }
      const boxes=await cards.evaluateAll(elements=>elements.map(el=>el.getBoundingClientRect().toJSON()));
      assert(width>1000 ? boxes.every(box=>Math.abs(box.top-boxes[0].top)<1) : boxes[1].top>=boxes[0].bottom,'Responsive card layout failed');
      assert(await tab.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Fixture overflow');
      evidence.fixtureCases.push({width,cards:3,apiCopyPreserved:true,responsive:true});
      await tab.unroute(pattern);
      await tab.reload({waitUntil:'domcontentloaded'});
      await tab.locator('[data-testid="operational-support"]').waitFor();
    }
    return evidence;
  } finally { await tab.close(); }
}
