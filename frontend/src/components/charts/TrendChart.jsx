import { useMemo } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  AreaChart,
  Area,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  ReferenceLine,
  ReferenceArea,
  Brush,
} from "recharts";

const fmt = (n) => Number(n).toLocaleString();

const COLOR_NORMAL = "hsl(var(--primary) / 0.65)";
const COLOR_PEAK = "#059669";
const COLOR_PRIMARY = "hsl(var(--primary))";

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-xs shadow-md space-y-1 select-none pointer-events-none">
      <div className="font-semibold text-foreground">{label}</div>
      <div className="flex justify-between gap-6">
        <span className="text-muted-foreground">Room Nights</span>
        <span className="font-bold tabular-nums">{fmt(d.room_nights)}</span>
      </div>
      {d.arrivals != null && (
        <div className="flex justify-between gap-6">
          <span className="text-muted-foreground">Arrivals</span>
          <span className="font-bold tabular-nums">{fmt(d.arrivals)}</span>
        </div>
      )}
      {(d.is_peak || d.is_holiday_period) && (
        <div className="text-emerald-600 font-medium">
          {d.is_peak ? "Peak Demand Period" : "National Holiday"}
        </div>
      )}
    </div>
  );
}

export default function TrendChart({ series, grain, onDrill, canDrill }) {
  const isDense = series.length > 31; // dense time series (full days)
  const avg = useMemo(
    () => series.reduce((s, x) => s + x.room_nights, 0) / (series.length || 1),
    [series],
  );

  const axisProps = {
    tickLine: false,
    axisLine: false,
    tick: { fontSize: 11, fill: "hsl(var(--muted-foreground))" },
  };

  const handleClick = (e) => {
    const item = e?.activePayload?.[0]?.payload;
    if (item && canDrill) onDrill(item);
  };

  const common = {
    data: series,
    margin: { top: 8, right: 8, left: 0, bottom: 0 },
    onClick: handleClick,
    style: { cursor: canDrill ? "pointer" : "default" },
  };

  const grid = (
    <CartesianGrid
      vertical={false}
      strokeDasharray="3 3"
      stroke="hsl(var(--border))"
    />
  );

  const xAxis = (
    <XAxis
      dataKey="period_label"
      minTickGap={isDense ? 40 : 8}
      {...axisProps}
    />
  );

  const yAxis = <YAxis width={48} tickFormatter={fmt} {...axisProps} />;

  // cursor={false} prevents any rectangular box/overlay when clicking or hovering
  const tooltip = (
    <Tooltip
      content={<ChartTooltip />}
      cursor={false}
      isAnimationActive={false}
    />
  );

  const avgLine = (
    <ReferenceLine
      y={avg}
      stroke="hsl(var(--primary) / 0.45)"
      strokeDasharray="4 4"
      label={{
        value: `Avg ${fmt(Math.round(avg))}`,
        position: "insideTopRight",
        fontSize: 10,
        fill: "hsl(var(--muted-foreground))",
      }}
    />
  );

  return (
    <div className="h-72 w-full outline-none focus:outline-none select-none [&_.recharts-surface]:outline-none [&_.recharts-surface]:focus:outline-none">
      <ResponsiveContainer width="100%" height="100%">
        {isDense ? (
          /* Dense view → Area with soft gradient & Brush */
          <AreaChart {...common}>
            <defs>
              <linearGradient id="rnFill" x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="0%"
                  stopColor={COLOR_PRIMARY}
                  stopOpacity={0.35}
                />
                <stop
                  offset="100%"
                  stopColor={COLOR_PRIMARY}
                  stopOpacity={0.02}
                />
              </linearGradient>
            </defs>
            {grid}
            {xAxis}
            {yAxis}
            {tooltip}
            {avgLine}
            {series
              .filter((s) => s.is_holiday_period)
              .map((s) => (
                <ReferenceArea
                  key={s.period_label}
                  x1={s.period_label}
                  x2={s.period_label}
                  fill="#059669"
                  fillOpacity={0.15}
                  ifOverflow="extendDomain"
                />
              ))}
            <Area
              type="monotone"
              dataKey="room_nights"
              stroke={COLOR_PRIMARY}
              strokeWidth={2}
              fill="url(#rnFill)"
              dot={false}
              activeDot={{ r: 4 }}
            />
            <Brush
              dataKey="period_label"
              height={24}
              stroke={COLOR_PRIMARY}
              travellerWidth={8}
              tickFormatter={() => ""}
            />
          </AreaChart>
        ) : (
          /* Standard view → Light blue bars with rounded corners */
          <BarChart {...common} barCategoryGap="22%">
            {grid}
            {xAxis}
            {yAxis}
            {tooltip}
            {avgLine}
            <Bar
              dataKey="room_nights"
              maxBarSize={56}
              radius={[6, 6, 0, 0]}
              onClick={(data) => {
                const item = data?.payload || data;
                if (canDrill && item) onDrill(item);
              }}
            >
              {series.map((s) => (
                <Cell
                  key={s.period_label}
                  cursor={canDrill ? "pointer" : "default"}
                  fill={
                    s.is_peak || s.is_holiday_period
                      ? COLOR_PEAK
                      : COLOR_NORMAL
                  }
                  className="transition-opacity hover:opacity-85 focus:outline-none"
                  onClick={() => {
                    if (canDrill) onDrill(s);
                  }}
                />
              ))}
            </Bar>
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
