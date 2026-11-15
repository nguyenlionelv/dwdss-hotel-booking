async (page) => {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const tab = await page.context().newPage();
  const evidence = [];
  try {
    await tab.addInitScript(() => {
      const original = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function (...args) {
        const ctx = original.apply(this, args);
        if (args[0] !== '2d' || !ctx || ctx.__forecastCaptured) return ctx;
        ctx.__forecastCaptured = true;
        let path = [];
        for (const name of ['clearRect', 'beginPath', 'moveTo', 'lineTo', 'stroke', 'arc', 'fillText']) {
          const method = ctx[name];
          ctx[name] = function (...values) {
            if (this.canvas.getAttribute('aria-label') === 'Actual versus 7-day forecast demand trajectory canvas chart') {
              const canvas = this.canvas;
              if (name === 'clearRect') { canvas.__draw = []; path = []; }
              canvas.__draw ||= [];
              if (name === 'beginPath') path = [];
              if (name === 'moveTo' || name === 'lineTo') path.push({ command: name, x: values[0], y: values[1] });
              if (name === 'stroke') canvas.__draw.push({ kind: 'path', color: this.strokeStyle, points: [...path] });
              if (name === 'arc') canvas.__draw.push({ kind: 'marker', x: values[0], y: values[1], radius: values[2] });
              if (name === 'fillText' && (this.font.startsWith('600 11px') || /^(HIGH|LOW|μ_8w)/.test(values[0]))) {
                const metrics = this.measureText(values[0]);
                canvas.__draw.push({ kind: 'label', text: values[0], x: values[1], y: values[2],
                  width: Math.min(metrics.width, values[3] ?? Infinity),
                  ascent: metrics.actualBoundingBoxAscent, descent: metrics.actualBoundingBoxDescent });
              }
            }
            return method.apply(this, values);
          };
        }
        return ctx;
      };
    });
    const base = 'http://localhost:5173';
    const original = await (await tab.request.get(`${base}/api/dss/demand-forecast?as_of_date=2017-08-24`)).json();
    const fixtures = [
      ['real-cutoff-2017-08-24', null],
      ['actual-far-above-forecast', data => { data.forecasts[0].actual_guest_count = 1_000_000; }],
      ['equal-values', data => { data.recent_history.forEach(row => { row.target_guests = 100; }); data.forecasts.forEach(row => { row.predicted_guest_count = 100; row.actual_guest_count = 100; }); }],
      ['zero-values', data => { data.recent_history.forEach(row => { row.target_guests = 0; }); data.forecasts.forEach(row => { row.predicted_guest_count = 0; row.actual_guest_count = 0; }); }],
      ['missing-values', data => { data.recent_history[0].target_guests = null; data.forecasts[0].actual_guest_count = null; data.forecasts[2].predicted_guest_count = null; data.forecasts[3].actual_guest_count = null; }],
      ['all-missing', data => { data.recent_history.forEach(row => { row.target_guests = null; }); data.forecasts.forEach(row => { row.predicted_guest_count = null; row.actual_guest_count = null; }); }],
    ];
    for (const width of [1440, 390]) {
      await tab.setViewportSize({ width, height: 1000 });
      const cssWidth = await tab.evaluate(() => innerWidth);
      if (Math.abs(cssWidth - width) > 1) await tab.setViewportSize({ width: Math.round(width * width / cssWidth), height: Math.round(1000 * width / cssWidth) });
      for (const [name, change] of fixtures) {
        const data = structuredClone(original);
        if (change) change(data);
        const pattern = '**/api/dss/demand-forecast?*';
        if (change) await tab.route(pattern, route => route.fulfill({ json: data }));
        await tab.goto(`${base}/dss/demand-forecast`, { waitUntil: 'domcontentloaded' });
        await tab.locator('table tbody tr').first().waitFor();
        await tab.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        const drawing = await tab.evaluate(() => {
          const canvas = document.querySelector('canvas[aria-label="Actual versus 7-day forecast demand trajectory canvas chart"]');
          const width = parseFloat(canvas.style.width);
          const height = parseFloat(canvas.style.height);
          return { events: canvas.__draw ?? [], plot: { left: 52, right: width - 24, top: 26, bottom: height - 44 } };
        });
        const { plot, events } = drawing;
        const paths = events.filter(event => event.kind === 'path' && ['#315b52', '#547a9b', '#92958b'].includes(event.color.toLowerCase()));
        const markers = events.filter(event => event.kind === 'marker');
        const labels = events.filter(event => event.kind === 'label');
        for (const path of paths) for (const p of path.points) {
          assert(Number.isFinite(p.x) && Number.isFinite(p.y), `${name}: non-finite path point`);
          assert(p.x >= plot.left && p.x <= plot.right && p.y >= plot.top && p.y <= plot.bottom, `${name}: series point outside plot`);
        }
        for (const p of markers) assert(p.x - p.radius >= plot.left && p.x + p.radius <= plot.right && p.y - p.radius >= plot.top && p.y + p.radius <= plot.bottom, `${name}: clipped marker`);
        for (const p of labels) assert(p.x - p.width / 2 >= plot.left && p.x + p.width / 2 <= plot.right && p.y - p.ascent >= plot.top && p.y + p.descent <= plot.bottom, `${name}: clipped data label`);
        const expectedMarkers = data.recent_history.slice(-10).filter(row => typeof row.target_guests === 'number').length + data.forecasts.filter(row => typeof row.predicted_guest_count === 'number').length;
        assert(markers.length === expectedMarkers, `${name}: missing values were drawn or valid points lost`);
        if (name === 'all-missing') assert(paths.length === 0 && labels.length === 0, 'Missing series fabricated plot data');
        else assert(paths.length >= 3, `${name}: a displayed series disappeared`);
        evidence.push({ width, scenario: name, pathsInsidePlot: true, markersInsidePlot: true,
          labelsInsidePlot: true, markerCount: markers.length, missingValuesPreserved: true });
        if (change) await tab.unroute(pattern);
      }
    }
    return { passed: true, cases: evidence };
  } finally {
    await tab.close();
  }
}
