import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';

// 幻灯片负责时间线，场景模块负责几何图形和画框适配。
function subdivide(points) {
  const result = [];
  for (let i = 0; i < points.length - 1; i++) {
    const [x, y] = points[i];
    const dx = (points[i + 1][0] - x) / 3;
    const dy = (points[i + 1][1] - y) / 3;
    result.push([x, y], [x + dx, y + dy],
      [x + 1.5 * dx - Math.sqrt(3) * dy / 2,
       y + 1.5 * dy + Math.sqrt(3) * dx / 2], [x + 2 * dx, y + 2 * dy]);
  }
  result.push(points.at(-1));
  return result;
}

const levels = [[[-4, -1], [4, -1]]];
for (let i = 0; i < 3; i++) levels.push(subdivide(levels.at(-1)));

export const config = {width: 960, height: 540, fps: 30, durationInFrames: 300};
export default function Koch({iteration = 0}) {
  const frame = useCurrentFrame();
  const level = Math.max(0, Math.min(3, Number(iteration)));
  const points = levels[Math.floor(level)].map(([x,y]) => `${480+x*95},${330-y*95}`).join(' ');
  return React.createElement(AbsoluteFill, {style: {background: 'var(--soda-surface)', color: 'var(--soda-primary)'}},
    React.createElement('svg', {viewBox: '0 0 960 540', width: '100%', height: '100%'},
      React.createElement('polyline', {points, fill: 'none', stroke: 'currentColor', strokeWidth: 5}),
      React.createElement('text', {x: 480, y: 65, textAnchor: 'middle', fill: 'currentColor', fontSize: 28},
        `Koch · iteration ${level.toFixed(2)} · frame ${frame}`)));
}
