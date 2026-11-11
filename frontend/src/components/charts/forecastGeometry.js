/** Preserve unknowns as gaps; only finite API numbers can enter the plot. */
export const forecastNumber = (value) => typeof value === 'number' && Number.isFinite(value) ? value : null;

/** Domain for every displayed series and reference line, with 12% headroom. */
export function forecastDomain(history = [], forecasts = [], thresholds = {}) {
  const values = [
    ...history.slice(-10).map(row => row.target_guests),
    ...forecasts.flatMap(row => [row.predicted_guest_count, row.actual_guest_count]),
    thresholds.mean_guests_8w, thresholds.high_threshold, thresholds.low_threshold,
  ].filter(value => forecastNumber(value) !== null);
  if (!values.length) return null;
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const span = maximum - minimum || Math.max(Math.abs(maximum), 1);
  const padding = span * 0.12;
  return { min: minimum - padding, max: maximum + padding };
}

/** Keep the entire data label inside the plot, including at endpoint markers. */
export function forecastLabelPosition(x, y, textWidth, ascent, descent, plot) {
  return {
    x: Math.max(plot.left + textWidth / 2 + 1, Math.min(plot.right - textWidth / 2 - 1, x)),
    y: Math.max(plot.top + ascent + 1, Math.min(plot.bottom - descent - 1, y - 12)),
  };
}
