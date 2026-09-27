import { Scene, DynamicPolyline, resamplePolylineByArcLength } from '@zanim/web';

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

export async function mount(container) {
  const tokens = getComputedStyle(container);
  const primary = tokens.getPropertyValue('--soda-primary').trim();
  const surface = tokens.getPropertyValue('--soda-surface').trim();
  const frame = document.createElement('div');
  frame.style.cssText = 'width:100%;height:100%;padding:24px;display:grid;grid-template-rows:minmax(0,1fr)32px;background:var(--soda-surface)';
  const canvas = document.createElement('canvas');
  canvas.style.cssText = 'width:100%;height:100%;min-height:0;display:block';
  const label = document.createElement('div');
  label.style.cssText = 'text-align:center;font:20px "SODA Academic Sans",sans-serif;color:var(--soda-primary)';
  frame.append(canvas, label);
  container.replaceChildren(frame);
  let iteration = 0;
  let currentTime = 0;
  const scene = await Scene.create(canvas, {
    observeResize: false,
    renderer: { background: surface, unitSize: 40 },
  });
  scene.add(new DynamicPolyline(() => {
    const lo = Math.floor(iteration);
    const hi = Math.min(3, lo + 1);
    const mix = iteration - lo;
    const target = levels[hi];
    const from = resamplePolylineByArcLength(levels[lo], target.length - 1);
    return target.map((p, i) => [
      from[i][0] + (p[0] - from[i][0]) * mix,
      from[i][1] + (p[1] - from[i][1]) * mix,
    ]);
  }, { stroke: primary, strokeWidth: 0.05 }));
  function draw() {
    const rect = canvas.getBoundingClientRect();
    scene.renderer.baseUnitSize = Math.max(1, Math.min(rect.width / 10, rect.height / 5));
    label.textContent = `iteration ${iteration.toFixed(2)}`;
    scene.seek(currentTime);
  }
  window.addEventListener('resize', draw);
  return {
    render(time, props = {}) {
      iteration = Math.max(0, Math.min(3, Number(props.iteration) || 0));
      currentTime = time;
      draw();
    },
    destroy() { window.removeEventListener('resize', draw); scene.destroy(); },
  };
}
