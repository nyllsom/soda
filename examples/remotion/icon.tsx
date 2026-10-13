import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

export const config = {width: 960, height: 540, fps: 30, durationInFrames: 180};
export const defaultProps = {label: '准备就绪', color: '#6f145f'};

export default function CheckIcon({label, color}: typeof defaultProps) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const scale = spring({frame, fps, config: {damping: 14}});
  const draw = interpolate(frame, [10, 35], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', gap: 25, background: '#faf7fc'}}>
    <svg width="190" height="190" viewBox="0 0 100 100" style={{transform: `scale(${scale})`}}>
      <circle cx="50" cy="50" r="45" fill={color}/>
      <path d="M25 51 L43 69 L76 33" fill="none" stroke="white" strokeWidth="8"
        strokeLinecap="round" strokeLinejoin="round" pathLength="1" strokeDasharray="1" strokeDashoffset={1 - draw}/>
    </svg>
    <div style={{fontSize: 38, color, fontFamily: 'sans-serif'}}>{label}</div>
    <div style={{fontSize: 22, color: '#666'}}>frame {frame} · {fps} fps</div>
  </AbsoluteFill>;
}
