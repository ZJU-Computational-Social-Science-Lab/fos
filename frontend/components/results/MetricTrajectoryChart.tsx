/*
This file draws a simple metric chart from ready-made data.
MetricTrajectoryChart shows the metric name, draws one line for each agent, and shows a color key for the agent names.
*/

import React from 'react';
import { metricChartGeometry } from '@/utils/metricChartGeometry';
import type { Series } from '@/utils/resultsComputations';

interface MetricTrajectoryChartProps {
  series: Series[];
  metric: string;
  width?: number;
  height?: number;
}

const COLORS = [
  '#1f77b4',
  '#ff7f0e',
  '#2ca02c',
  '#d62728',
  '#9467bd',
  '#8c564b',
  '#e377c2',
  '#7f7f7f',
  '#bcbd22',
  '#17becf',
];

export function MetricTrajectoryChart({
  series,
  metric,
  width = 600,
  height = 300,
}: MetricTrajectoryChartProps): React.JSX.Element {
  const lines = metricChartGeometry(series, width, height);

  return (
    <div>
      <div>{metric}</div>
      <svg width={width} height={height} role="img" aria-label={metric}>
        {lines.map((line, index) => (
          <polyline
            key={line.agentId}
            data-agent={line.agentId}
            points={line.points}
            fill="none"
            stroke={COLORS[index % COLORS.length]}
            strokeWidth={2}
          />
        ))}
      </svg>
      <ul>
        {lines.map((line, index) => (
          <li key={line.agentId}>
            <span
              aria-hidden="true"
              style={{
                backgroundColor: COLORS[index % COLORS.length],
                display: 'inline-block',
                width: '0.75rem',
                height: '0.75rem',
                marginRight: '0.5rem',
              }}
            />
            {line.agentName}
          </li>
        ))}
      </ul>
    </div>
  );
}
