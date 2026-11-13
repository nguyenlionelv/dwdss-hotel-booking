const numberFormatters = {
  integer: new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }),
  upToTwo: new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }),
  exactlyTwo: new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
};

export function finiteNumber(value) {
  if (value === null || value === undefined || value === '' || typeof value === 'boolean') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function formatted(value, style) {
  const number = finiteNumber(value);
  return number === null ? '—' : numberFormatters[style].format(number);
}

export const formatGuests = value => formatted(value, 'integer');
export const formatSignedGuests = value => {
  const number = finiteNumber(value);
  return number === null ? '—' : `${number > 0 ? '+' : number < 0 ? '−' : ''}${formatGuests(Math.abs(number))}`;
};
export const formatReference = value => formatted(value, 'upToTwo');
export const formatChartAxis = value => {
  const number = finiteNumber(value);
  if (number === null) return '—';
  return Math.abs(number) >= 10_000
    ? new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 2 }).format(number)
    : formatReference(number);
};
export const formatMetric = value => formatted(value, 'exactlyTwo');
export const formatUnits = value => `${formatted(value, 'upToTwo')}${finiteNumber(value) === null ? '' : ' units'}`;
export const formatMrr = value => finiteNumber(value) === null ? '—' : `${formatMetric(Number(value) * 100)}%`;
export const formatShare = value => finiteNumber(value) === null ? '—' : `${formatMetric(value)}%`;
export const formatRate = value => finiteNumber(value) === null ? '—' : `${formatMetric(Number(value) * 100)}%`;
export const formatSignedPercent = value => {
  const number = finiteNumber(value);
  return number === null ? '—' : `${number > 0 ? '+' : number < 0 ? '−' : ''}${formatMetric(Math.abs(number))}%`;
};
export const formatSignedPoints = value => {
  const number = finiteNumber(value);
  return number === null ? '—' : `${number > 0 ? '+' : number < 0 ? '−' : ''}${formatMetric(Math.abs(number))} pp`;
};
export const formatRelativeImprovement = (difference, baseline) => {
  const delta = finiteNumber(difference);
  const base = finiteNumber(baseline);
  return delta === null || base === null || base <= 0 ? '—' : formatSignedPercent(delta / base * 100);
};

export function formatDate(value, short = false) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return '—';
  const date = new Date(`${value}T00:00:00Z`);
  if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== value) return '—';
  return new Intl.DateTimeFormat('en-GB', {
    day: 'numeric', month: 'short', ...(short ? {} : { year: 'numeric' }), timeZone: 'UTC',
  }).format(date);
}

export function formatWeekday(value) {
  if (formatDate(value) === '—') return '—';
  return new Intl.DateTimeFormat('en-GB', { weekday: 'long', timeZone: 'UTC' }).format(new Date(`${value}T00:00:00Z`));
}
