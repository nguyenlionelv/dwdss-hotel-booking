/** Fit measured axis labels inside the plot and reserve room for the last date. */
export function layoutAxisLabels(labels, left, right, gap = 12) {
  const available = right - left;
  if (!Number.isFinite(available) || available <= 0) return [];
  const candidates = labels.filter(label => label.text && Number.isFinite(label.x) &&
    Number.isFinite(label.width) && label.width > 0 && label.width <= available)
    .map(label => {
      const x = Math.max(left + label.width / 2, Math.min(right - label.width / 2, label.x));
      return { ...label, x, left: x - label.width / 2, right: x + label.width / 2 };
    });
  if (candidates.length < 2) return candidates;
  const first = candidates[0];
  const last = candidates[candidates.length - 1];
  // At extremely narrow widths, one complete date is better than clipped text.
  if (first.right + gap > last.left) return [last];
  const placed = [first];
  for (const label of candidates.slice(1, -1)) {
    if (label.left >= placed[placed.length - 1].right + gap && label.right + gap <= last.left) {
      placed.push(label);
    }
  }
  placed.push(last);
  return placed;
}
