import React from 'react';
import type { MetricAggregatePoint } from '@/utils/resultsComputations';

interface AggregateTrajectoryChartProps {
  points: MetricAggregatePoint[];
  metric: string;
  width?: number;
  height?: number;
  meanLabel?: string;
  rangeLabel?: string;
}

const MARGIN = { left: 48, right: 12, top: 12, bottom: 28 };

function f(n: number): number { return Number(n.toFixed(2)); }
function fmt(v: number): string { return Number.isInteger(v) ? String(v) : v.toFixed(1); }

export function AggregateTrajectoryChart({
  points,
  metric,
  width = 600,
  height = 300,
  meanLabel = 'Mean',
  rangeLabel = 'Range',
}: AggregateTrajectoryChartProps): React.JSX.Element {
  if (points.length === 0) return <div />;

  const plotWidth  = width  - MARGIN.left - MARGIN.right;
  const plotHeight = height - MARGIN.top  - MARGIN.bottom;
  const maxLen     = points.length;
  const yMin       = Math.min(...points.map((p) => p.min));
  const yMax       = Math.max(...points.map((p) => p.max));

  const toX = (i: number): number =>
    maxLen === 1 ? 0 : (i / (maxLen - 1)) * plotWidth;
  const toY = (v: number): number =>
    yMax === yMin ? plotHeight / 2 : plotHeight - ((v - yMin) / (yMax - yMin)) * plotHeight;

  // Band polygon: trace min values left→right, then max values right→left
  const bandPoints = [
    ...points.map((p, i) => `${f(toX(i))},${f(toY(p.min))}`),
    ...[...points].reverse().map((p, i) => `${f(toX(maxLen - 1 - i))},${f(toY(p.max))}`),
  ].join(' ');

  const meanPts = points.map((p, i) => `${f(toX(i))},${f(toY(p.mean))}`).join(' ');

  const yTicks = [
    { value: yMax, y: 0 },
    { value: (yMin + yMax) / 2, y: plotHeight / 2 },
    { value: yMin, y: plotHeight },
  ];
  const labelStep = Math.max(1, Math.ceil(maxLen / 10));
  const xTicks = points
    .map((p, i) => ({ round: p.round, x: toX(i), show: i % labelStep === 0 || i === maxLen - 1 }))
    .filter((t) => t.show);

  return (
    <div>
      <div style={{ fontSize: '12px', color: 'var(--ss-workspace-muted)', marginBottom: '4px' }}>{metric}</div>
      <svg width={width} height={height} role="img" aria-label={metric}>
        <g transform={`translate(${MARGIN.left}, ${MARGIN.top})`}>
          {yTicks.map((t, i) => (
            <g key={`y-${i}`}>
              <line x1={0} y1={t.y} x2={plotWidth} y2={t.y}
                stroke="var(--ss-workspace-border)" strokeWidth={1} />
              <text x={-8} y={t.y} textAnchor="end" dominantBaseline="middle"
                fontSize={10} fill="var(--ss-workspace-muted)">{fmt(t.value)}</text>
            </g>
          ))}
          {xTicks.map((t) => (
            <text key={`x-${t.round}`} x={t.x} y={plotHeight + 16}
              textAnchor="middle" fontSize={10} fill="var(--ss-workspace-muted)">{t.round}</text>
          ))}
          <polygon points={bandPoints}
            fill="var(--ss-brand-soft)" fillOpacity={0.5} stroke="none" />
          <polyline points={meanPts} fill="none"
            stroke="var(--ss-brand-primary)" strokeWidth={2} />
          {points.map((p, i) => (
            <circle key={i} cx={f(toX(i))} cy={f(toY(p.mean))} r={3}
              fill="var(--ss-brand-primary)" />
          ))}
        </g>
      </svg>
      <ul style={{ listStyle: 'none', padding: 0, margin: '8px 0 0', fontSize: '12px' }}>
        <li style={{ display: 'flex', alignItems: 'center', marginBottom: '2px' }}>
          <span aria-hidden="true" style={{ background: 'var(--ss-brand-primary)',
            display: 'inline-block', width: '1rem', height: '2px', marginRight: '0.5rem' }} />
          {meanLabel}
        </li>
        <li style={{ display: 'flex', alignItems: 'center' }}>
          <span aria-hidden="true" style={{ background: 'var(--ss-brand-soft)', opacity: 0.6,
            display: 'inline-block', width: '1rem', height: '0.75rem', marginRight: '0.5rem' }} />
          {rangeLabel}
        </li>
      </ul>
    </div>
  );
}
