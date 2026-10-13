import React, {createRef} from 'react';
import {createRoot} from 'react-dom/client';
import {flushSync} from 'react-dom';
import {Player} from '@remotion/player';

// A scene exports a React component and optional composition metadata.
// SODA owns the clock: never start a second, independently running player.
export function mountScene(scene, container, context) {
  const component = scene.default;
  if (!component || (typeof component !== 'function' && typeof component !== 'object')) {
    throw new Error('Remotion module must default-export a React component');
  }
  const config = {fps: 30, durationInFrames: 300, width: 960, height: 540, ...scene.config};
  for (const name of ['fps', 'durationInFrames', 'width', 'height']) {
    if (!Number.isFinite(config[name]) || config[name] <= 0 ||
        (name !== 'fps' && !Number.isInteger(config[name]))) {
      throw new Error(`Remotion config.${name} must be a positive ${name === 'fps' ? 'number' : 'integer'}`);
    }
  }
  const host = document.createElement('div');
  host.style.cssText = `position:absolute;left:50%;top:50%;width:${config.width}px;height:${config.height}px;transform-origin:center`;
  container.append(host);
  const resize = () => {
    const sx = container.clientWidth / config.width;
    const sy = container.clientHeight / config.height;
    const scale = context.fit === 'cover' ? Math.max(sx, sy) : Math.min(sx, sy);
    host.style.transform = `translate(-50%, -50%) scale(${context.fit === 'fill' ? sx : scale}, ${context.fit === 'fill' ? sy : scale})`;
  };
  const observer = new ResizeObserver(resize);
  observer.observe(container);
  resize();
  const root = createRoot(host);
  const ref = createRef();
  let previousProps = '';
  let failure;
  const onError = ({detail}) => { failure = detail.error; };
  function render(time, props = {}) {
    if (failure) throw failure;
    const inputProps = {...scene.defaultProps, ...props};
    const key = JSON.stringify(inputProps);
    if (key !== previousProps) {
      flushSync(() => root.render(React.createElement(Player, {
        ref, component, inputProps, fps: config.fps,
        durationInFrames: config.durationInFrames,
        compositionWidth: config.width, compositionHeight: config.height,
        controls: false, autoPlay: false, clickToPlay: false,
        doubleClickToFullscreen: false, spaceKeyToPlayOrPause: false,
        style: {width: config.width, height: config.height},
      })));
      previousProps = key;
    }
    const frame = Math.min(config.durationInFrames - 1, Math.max(0, Math.floor(time * config.fps + 1e-7)));
    if (ref.current && ref.current.getCurrentFrame() !== frame) {
      flushSync(() => ref.current.seekTo(frame));
    }
  }
  try {
    render(0, context.props);
    ref.current?.addEventListener('error', onError);
  } catch (error) {
    observer.disconnect();
    root.unmount();
    host.remove();
    throw error;
  }
  return {render, destroy() {
    observer.disconnect();
    ref.current?.removeEventListener('error', onError);
    root.unmount();
    host.remove();
  }};
}
