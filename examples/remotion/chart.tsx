import {AbsoluteFill} from 'remotion';

export const config = {width: 960, height: 540, fps: 30, durationInFrames: 300};
export default function Bars({progress = 0, label = '初始值'}: {progress?: number; label?: string}) {
  const p = Math.max(0, Math.min(1, Number(progress)));
  const values = [35 + 45 * p, 55 + 10 * p, 25 + 65 * p];
  return <AbsoluteFill style={{padding: '45px 90px', background: '#faf7fc', fontFamily: 'sans-serif'}}>
    <div style={{fontSize: 32, color: '#6f145f'}}>{label}</div>
    <div style={{display: 'flex', alignItems: 'end', gap: 55, height: 330, borderBottom: '2px solid #ccc'}}>
      {values.map((value, i) => <div key={i} style={{flex: 1, height: `${value * 3}px`, background: ['#6f145f', '#aa6eab', '#dfb8dc'][i],
        display: 'grid', placeItems: 'center', color: 'white', fontSize: 30}}>{Math.round(value)}</div>)}
    </div>
    <div style={{fontSize: 22, color: '#666', marginTop: 20}}>progress = {p.toFixed(2)}</div>
  </AbsoluteFill>;
}
