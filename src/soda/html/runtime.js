(() => {
  const runtime = JSON.parse(document.getElementById('soda-runtime').textContent);
  const timeline = runtime.timeline;
  const slides = [...document.querySelectorAll('.slide')];
  const slideById = new Map(slides.map(slide => [slide.dataset.slide, slide]));
  const spanById = new Map(timeline.slides.map(span => [span.id, span]));
  const counter = document.querySelector('.counter');
  const stepLabel = document.querySelector('.step');
  const readyLabel = stepLabel.textContent;
  const scrub = document.querySelector('.scrub');
  const sharedOverlay = document.querySelector('.shared-transition-overlay');
  const diagnosticsPanel = document.querySelector('.layout-diagnostics');
  const stage = document.querySelector('.stage');
  const LOGICAL_WIDTH = 1600;
  const LOGICAL_HEIGHT = 900;
  const STAGE_MARGIN = 24;
  function updateStageScale() {
    const viewportWidth = window.visualViewport?.width || window.innerWidth;
    const viewportHeight = window.visualViewport?.height || window.innerHeight;
    const scale = Math.min(
      Math.max(0.01, (viewportWidth - STAGE_MARGIN * 2) / LOGICAL_WIDTH),
      Math.max(0.01, (viewportHeight - STAGE_MARGIN * 2) / LOGICAL_HEIGHT),
    );
    stage.style.setProperty('--soda-stage-scale', String(scale));
    return scale;
  }
  updateStageScale();
  window.addEventListener('resize', updateStageScale, {passive:true});
  window.visualViewport?.addEventListener('resize', updateStageScale, {passive:true});
  function currentStageScale() {
    return Number(getComputedStyle(stage).getPropertyValue('--soda-stage-scale')) || 1;
  }
  scrub.max = String(timeline.total_duration);
  const clipsBySlide = new Map();
  for (const clip of timeline.clips) {
    if (!clipsBySlide.has(clip.slide)) clipsBySlide.set(clip.slide, []);
    clipsBySlide.get(clip.slide).push(clip);
  }
  for (const clips of clipsBySlide.values()) clips.sort((a,b) => a.start - b.start || a.end - b.end);

  let currentTime = 0;
  let playbackToken = 0;
  let animationTargetTime = null;
  const zanimInstances = new Map();

  function parseZanimInitial(el) {
    try { return JSON.parse(el.dataset.zanimProps || '{}'); }
    catch { return {}; }
  }
  async function mountZanimScenes() {
    for (const el of document.querySelectorAll('[data-kind="zanim"][data-zanim-src]')) {
      if (zanimInstances.has(el)) continue;
      const viewport = el.querySelector('.zanim-viewport') || el;
      try {
        let mod;
        const source = el.dataset.zanimSrc || '';
        if (source.startsWith('soda-single-scene:')) {
          const bundleUrl = globalThis.__SODA_ZANIM_SCENE_BUNDLE_URL__;
          if (!bundleUrl) throw new Error('portable Zanim scene bundle is missing');
          const registry = await import(bundleUrl);
          const key = source.slice('soda-single-scene:'.length);
          mod = (registry.default || registry.scenes || {})[key];
          if (!mod) throw new Error(`portable Zanim scene ${key} is missing`);
        } else {
          const moduleUrl = new URL(source, window.location.href).href;
          mod = await import(moduleUrl);
        }
        const factory = mod.default?.mount || mod.mount || mod.default;
        if (typeof factory !== 'function') throw new Error('module must export default function or mount()');
        let authoredProps = {};
        try { authoredProps = JSON.parse(el.dataset.zanimProps || '{}'); } catch (_) {}
        const api = await factory(viewport, {
          objectId: el.dataset.object,
          fit: el.dataset.zanimFit || 'contain',
          props: authoredProps,
        });
        const loading = el.querySelector('.zanim-loading');
        if (loading) loading.remove();
        zanimInstances.set(el, api || {});
      } catch (error) {
        const loading = el.querySelector('.zanim-loading');
        if (loading) loading.textContent = `Zanim scene failed: ${error?.message || error}`;
      }
    }
    renderAt(currentTime);
  }
  function renderZanimScene(el, props, time) {
    const api = zanimInstances.get(el);
    if (!api) return;
    try {
      if (typeof api.render === 'function') api.render(time, props);
      else if (typeof api.renderAt === 'function') api.renderAt(time, props);
      else if (typeof api.set === 'function') {
        for (const [key, value] of Object.entries(props)) api.set(key, value);
      }
      el.removeAttribute('data-zanim-error');
      el.querySelector(':scope > .zanim-runtime-error')?.remove();
    } catch (error) {
      const message = String(error?.message || error);
      el.dataset.zanimError = message;
      let box = el.querySelector(':scope > .zanim-runtime-error');
      if (!box) { box = document.createElement('div'); box.className = 'zanim-runtime-error'; el.appendChild(box); }
      box.textContent = `Zanim render failed: ${message}`;
      console.error('Zanim scene render failed', el.dataset.object, error);
    }
  }

  const clamp = (value, lo, hi) => Math.max(lo, Math.min(hi, value));
  function eased(name, value) {
    const p = clamp(value, 0, 1);
    if ((name || 'SMOOTHSTEP').toUpperCase() === 'LINEAR') return p;
    return p * p * (3 - 2 * p);
  }
  const progress = (clip, time) => {
    if (clip.end <= clip.start) return time >= clip.end ? 1 : 0;
    return eased(clip.easing, (time - clip.start) / (clip.end - clip.start));
  };
  function codeSelection(args) {
    if (Number.isFinite(Number(args?.line))) {
      const line = Math.max(1, Math.floor(Number(args.line)));
      return [line, line];
    }
    if (Array.isArray(args?.range) && args.range.length === 2) {
      const a = Math.max(1, Math.floor(Number(args.range[0])));
      const b = Math.max(1, Math.floor(Number(args.range[1])));
      return [Math.min(a,b), Math.max(a,b)];
    }
    return null;
  }
  function selectionLabel(selection) {
    if (!selection) return '';
    return selection[0] === selection[1] ? `L${selection[0]}` : `L${selection[0]}–${selection[1]}`;
  }

  const slideRenderCache = new Map();
  const codeLayoutCache = new WeakMap();
  function codeLayout(el) {
    const codeRender = el.querySelector('.code-render');
    let cache = codeLayoutCache.get(el);
    const height = codeRender?.clientHeight || 0;
    if (!cache || cache.codeRender !== codeRender || cache.clientHeight !== height) {
      const lines = [...el.querySelectorAll('.code-line')];
      const byNumber = new Map(lines.map(line => [Number(line.dataset.line), line]));
      const indexByNumber = new Map(lines.map((line, index) => [Number(line.dataset.line), index]));
      const first = lines[0] || null;
      const second = lines[1] || null;
      const baseTop = first?.offsetTop || 0;
      const measuredHeight = first?.offsetHeight || 0;
      const measuredStep = second ? second.offsetTop - baseTop : measuredHeight;
      const lineStep = measuredStep > 0 ? measuredStep : measuredHeight || 1;
      const lineHeight = measuredHeight > 0 ? measuredHeight : lineStep;
      cache = {
        codeRender, lines, byNumber, indexByNumber, geometries: new Map(),
        baseTop, lineStep, lineHeight,
        focusBand: el.querySelector('.code-focus-band'),
        pulseBand: el.querySelector('.code-pulse-band'),
        label: el.querySelector('.code-range'),
        clientHeight: height, scrollMax: codeRender ? Math.max(0, codeRender.scrollHeight - height) : 0,
        lastDimInactive: false,
      };
      codeLayoutCache.set(el, cache);
    }
    return cache;
  }

  function codeSelectionGeometry(layout, selection) {
    if (!selection) return null;
    const key = `${selection[0]}:${selection[1]}`;
    if (layout.geometries.has(key)) return layout.geometries.get(key);
    const firstIndex = layout.indexByNumber.get(selection[0]);
    const lastIndex = layout.indexByNumber.get(selection[1]);
    if (firstIndex == null || lastIndex == null) return null;
    const top = layout.baseTop + firstIndex * layout.lineStep;
    const geometry = {
      top,
      height: (lastIndex - firstIndex) * layout.lineStep + layout.lineHeight,
    };
    layout.geometries.set(key, geometry);
    return geometry;
  }

  function codeFocusTop(layout, selection) {
    const geometry = codeSelectionGeometry(layout, selection);
    if (!geometry) return 0;
    const center = geometry.top + geometry.height / 2;
    return clamp(center - layout.clientHeight * 0.46, 0, layout.scrollMax);
  }

  function resetFrame(el) {
    el.style.setProperty('--soda-frame-x', '0px');
    el.style.setProperty('--soda-frame-y', '0px');
    el.style.setProperty('--soda-frame-reveal-y', '0px');
    el.style.setProperty('--soda-frame-rotation', '0rad');
    el.style.setProperty('--soda-frame-scale-x', '1');
    el.style.setProperty('--soda-frame-scale-y', '1');
    el.style.setProperty('--soda-frame-opacity', '1');
    el.style.setProperty('--soda-frame-brightness', '1');
    el.style.clipPath='';
    el.style.visibility='';
    el.style.position='';
    el.style.left='';
    el.style.top='';
    el.style.width='';
    el.style.height='';
    el.style.margin='';
    el.style.zIndex='';
  }

  function applyFrame(el, state) {
    el.style.setProperty('--soda-frame-x', `${state.tx}px`);
    el.style.setProperty('--soda-frame-y', `${state.ty}px`);
    el.style.setProperty('--soda-frame-reveal-y', `${state.revealY}px`);
    el.style.setProperty('--soda-frame-rotation', `${state.rotation}rad`);
    el.style.setProperty('--soda-frame-scale-x', String(state.scaleX ?? state.scale));
    el.style.setProperty('--soda-frame-scale-y', String(state.scaleY ?? state.scale));
    el.style.setProperty('--soda-frame-opacity', String(state.opacity));
    el.style.setProperty('--soda-frame-brightness', String(state.brightness));
    el.style.clipPath = state.hasClipPath ? `inset(0 ${state.clipRight}% 0 0)` : '';
  }

  function resetObject(el) {
    resetFrame(el);
    el.classList.remove('shared-surface-hidden');
    if (el.classList.contains('math-object')) {
      const svg = el.querySelector(':scope > svg.math-svg');
      if (svg) svg.style.opacity = '';
    }
  }

  function renderFitClone(slide, sourceEl, fitState) {
    const {sourceRect, targetRect, p} = fitState;
    const slideRect = slide.getBoundingClientRect();
    const lerp = (a, b) => a + (b - a) * p;
    const clone = sourceEl.cloneNode(true);
    clone.classList.add('fit-motion-clone');
    for (const node of [clone, ...clone.querySelectorAll('[data-object], [data-slide-object]')]) {
      node.removeAttribute('data-object');
      node.removeAttribute('data-slide-object');
    }
    clone.setAttribute('aria-hidden','true');
    const stageScale = currentStageScale();
    clone.style.left = `${(lerp(sourceRect.left, targetRect.left) - slideRect.left) / stageScale}px`;
    clone.style.top = `${(lerp(sourceRect.top, targetRect.top) - slideRect.top) / stageScale}px`;
    clone.style.width = `${lerp(sourceRect.width, targetRect.width) / stageScale}px`;
    clone.style.height = `${lerp(sourceRect.height, targetRect.height) / stageScale}px`;
    clone.style.visibility = 'visible';
    clone.style.transform = 'none';
    clone.style.margin = '0';
    slide.appendChild(clone);
    sourceEl.style.visibility = 'hidden';
  }

  function slideRenderState(span, slide) {
    let cache = slideRenderCache.get(span.id);
    if (cache?.slide === slide) return cache;
    const slideClips = clipsBySlide.get(span.id) || [];
    const groups = new Map();
    const resetIds = new Set();
    let needsBaseFrames = false;
    for (const clip of slideClips) {
      if (!groups.has(clip.target)) groups.set(clip.target, []);
      groups.get(clip.target).push(clip);
      resetIds.add(String(clip.target));
      if (clip.op === 'fit_to') {
        needsBaseFrames = true;
        if (clip.args?.target) resetIds.add(String(clip.args.target));
      }
    }
    // Transitions also mutate static objects. Include their endpoints in the
    // reset set even when those objects have no authored per-slide motion.
    for (const tr of timeline.transitions) {
      if (tr.kind === 'shared' && (tr.source === span.id || tr.target === span.id)) {
        for (const id of transitionSharedIds(tr)) resetIds.add(id);
      }
      if (tr.kind === 'embed_zoom' && tr.source === span.id) {
        const ref = slide.querySelector(`[data-kind="slide-ref"][data-target-slide="${CSS.escape(tr.target)}"]`);
        if (ref?.dataset.object) resetIds.add(ref.dataset.object);
      }
    }
    const objectsById = new Map();
    for (const el of slide.querySelectorAll('[data-object]')) {
      if (!objectsById.has(el.dataset.object)) objectsById.set(el.dataset.object, el);
    }
    cache = {
      slide, slideClips, groups, needsBaseFrames, objectsById,
      resetElements: [...resetIds].map(id => objectsById.get(id)).filter(Boolean),
      slideObjects: needsBaseFrames ? [...slide.querySelectorAll('[data-slide-object="true"]')] : [],
    };
    slideRenderCache.set(span.id, cache);
    return cache;
  }

  function renderSlideObjects(span, time) {
    const slide = slideById.get(span.id);
    if (!slide) return;
    const runtime = slideRenderState(span, slide);
    for (const clone of slide.querySelectorAll(':scope > .fit-motion-clone')) clone.remove();
    for (const el of runtime.resetElements) resetObject(el);
    // Layout reads are expensive and force synchronization with style changes.
    // Only fit_to() needs physical browser rectangles; ordinary code focus,
    // Zanim animation and opacity motion stay entirely layout-read-free here.
    const baseFrames = new Map();
    if (runtime.needsBaseFrames) {
      for (const item of runtime.slideObjects) {
        baseFrames.set(item.dataset.object, item.getBoundingClientRect());
      }
    }

    const slideClips = runtime.slideClips;
    const groups = runtime.groups;
    // fit_to() treats its target as a geometry slot by default. Hiding the
    // target preserves its browser layout rectangle while avoiding a duplicate
    // object under the moving source. Authors can opt out with show_target=true.
    for (const clip of slideClips) {
      if (clip.op !== 'fit_to' || clip.args?.show_target === true) continue;
      const targetId = String(clip.args?.target || '');
      const targetEl = runtime.objectsById.get(targetId);
      if (targetEl) targetEl.style.visibility = 'hidden';
    }

    for (const [target, clips] of groups) {
      const el = runtime.objectsById.get(String(target));
      if (!el) continue;
      let opacity = 1;
      let clipRight = 0;
      let tx = 0, ty = 0, scale = 1, scaleX = 1, scaleY = 1, rotation = 0, revealY = 0;
      let focused = false;
      let brightness = 1;
      let hasClipPath = false;
      let focusSelection = null;
      let focusFromSelection = null;
      let focusProgress = 1;
      let hasFocusState = false;
      let pulseSelection = null;
      let pulseProgress = 0;
      let mathReveal = null;
      let fitState = null;
      let zanimState = el.dataset.kind === 'zanim' ? parseZanimInitial(el) : null;

      for (const clip of clips) {
        const p = progress(clip, time);
        const args = clip.args || {};
        if (clip.op === 'fade_in') {
          opacity = p;
          revealY = 14 * (1 - p);
        } else if (clip.op === 'fade_out') {
          opacity = 1 - p;
        } else if (clip.op === 'create') {
          if (el.classList.contains('math-object')) {
            opacity = 1;
            mathReveal = p;
          } else {
            opacity = p;
            clipRight = 100 * (1 - p);
            hasClipPath = true;
          }
        } else if (clip.op === 'scale') {
          const by = Number(args.by ?? 1);
          scale *= 1 + (by - 1) * p;
        } else if (clip.op === 'rotate') {
          rotation += Number(args.by ?? 0) * p;
        } else if (clip.op === 'move') {
          const v = args.by;
          if (Array.isArray(v)) {
            tx += Number(v[0] || 0) * p;
            ty += Number(v[1] || 0) * p;
          }
        } else if (clip.op === 'fit_to') {
          const sourceRect = baseFrames.get(target);
          const targetId = String(args.target || '');
          const targetRect = baseFrames.get(targetId);
          if (time > clip.start && sourceRect && targetRect && sourceRect.width && sourceRect.height) {
            // Resize the actual visual frame instead of scaling its pixels. Text,
            // code and other DOM content therefore keep their authored font size
            // while the browser naturally reflows inside the interpolated box.
            fitState = { sourceRect, targetRect, p };
          }
        } else if (clip.op === 'opacity') {
          const to = Number(args.to ?? 1);
          opacity = opacity + (to - opacity) * p;
        } else if (clip.op === 'focus') {
          if (time > clip.start) {
            const nextSelection = codeSelection(args);
            focusFromSelection = focusSelection;
            focusSelection = nextSelection;
            hasFocusState = true;
            focused = true;
            focusProgress = time < clip.end ? p : 1;
          }
        } else if (clip.op === 'highlight') {
          if (time > clip.start && time < clip.end) {
            focused = true;
            pulseSelection = codeSelection(args);
            pulseProgress = Math.sin(Math.PI * p);
            if (!el.classList.contains('code-block')) brightness *= 1 + 0.04 * pulseProgress;
          }
        } else if (clip.op === 'set') {
          // An instant clip has a 1ms span. Its start may equal the preceding
          // step's stop: do not apply the next step before it has been entered.
          if (zanimState && time >= clip.end) {
            const key = String(args.name || 'value');
            zanimState[key] = args.value;
          }
        } else if (clip.op === 'animate') {
          if (zanimState && time >= clip.start) {
            const key = String(args.name || 'value');
            const to = args.to;
            const from = args.from ?? zanimState[key] ?? 0;
            if (typeof from === 'number' && typeof to === 'number') zanimState[key] = from + (to - from) * p;
            else zanimState[key] = p < 1 ? from : to;
          }
        } else {
          throw new Error(`Unsupported SODA motion op: ${clip.op}`);
        }
      }

      applyFrame(el, {
        opacity, clipRight, tx, ty, scale, scaleX: scale * scaleX, scaleY: scale * scaleY, rotation, revealY, brightness, hasClipPath,
      });
      el.classList.toggle('motion-focus', focused);
      if (zanimState) renderZanimScene(el, zanimState, time - span.start);
      if (mathReveal !== null) {
        // Typst draws fraction/radical rules as paths alongside glyph groups.
        // Reveal the complete mathematical expression together: SVG storage
        // order is not reading order, and every drawable must be hidden at t=0.
        const svg = el.querySelector(':scope > svg.math-svg');
        if (svg) svg.style.opacity = String(mathReveal);
      }
      if (el.classList.contains('code-block')) {
        const layout = codeLayout(el);
        const {codeRender, lines, focusBand, pulseBand} = layout;
        const selectionGeometry = selection => codeSelectionGeometry(layout, selection);
        const lerp = (a, b, p) => a + (b - a) * p;
        const setBand = (band, geometry, bandOpacity) => {
          if (!band || !geometry) {
            if (band) band.style.opacity = '0';
            return;
          }
          band.style.transform = `translateY(${geometry.top}px)`;
          band.style.height = `${geometry.height}px`;
          band.style.opacity = String(clamp(bandOpacity, 0, 1));
        };

        const nextHasFocus = hasFocusState ? 'true' : 'false';
        if (el.dataset.hasFocus !== nextHasFocus) el.dataset.hasFocus = nextHasFocus;
        const targetGeometry = selectionGeometry(focusSelection);
        const sourceGeometry = selectionGeometry(focusFromSelection) || targetGeometry;
        let focusGeometry = targetGeometry;
        let focusBandOpacity = hasFocusState ? 1 : 0;
        if (hasFocusState && sourceGeometry && targetGeometry) {
          focusGeometry = {
            top: lerp(sourceGeometry.top, targetGeometry.top, focusProgress),
            height: lerp(sourceGeometry.height, targetGeometry.height, focusProgress),
          };
          if (!focusFromSelection) focusBandOpacity = focusProgress;
        }
        setBand(focusBand, focusGeometry, focusBandOpacity);
        setBand(pulseBand, selectionGeometry(pulseSelection), pulseProgress);

        // Match the old zanim-slides behavior: focus is primarily one moving
        // attention band. Source text stays stable unless dim_inactive=true is
        // explicitly authored. When dimming is requested, use the continuous
        // focus interval instead of cross-fading discrete line states.
        const dimInactive = codeRender?.dataset.dimInactive === 'true';
        let continuousStart = null;
        let continuousEnd = null;
        if (hasFocusState && focusSelection) {
          const from = focusFromSelection || focusSelection;
          continuousStart = lerp(from[0], focusSelection[0], focusProgress);
          continuousEnd = lerp(from[1], focusSelection[1], focusProgress);
        }
        if (dimInactive && continuousStart !== null && continuousEnd !== null) {
          for (const line of lines) {
            const number = Number(line.dataset.line);
            const distance = number < continuousStart
              ? continuousStart - number
              : number > continuousEnd ? number - continuousEnd : 0;
            const edge = clamp(distance, 0, 1);
            const smooth = edge * edge * (3 - 2 * edge);
            line.style.setProperty('--code-focus-opacity', String(1 - 0.32 * smooth));
          }
        } else if (layout.lastDimInactive) {
          for (const line of lines) line.style.setProperty('--code-focus-opacity', '1');
        }
        layout.lastDimInactive = dimInactive;

        const label = layout.label;
        if (label) {
          let nextLabel = '';
          if (pulseSelection) nextLabel = selectionLabel(pulseSelection);
          else if (focusSelection) {
            const shown = focusFromSelection && focusProgress < 0.5 ? focusFromSelection : focusSelection;
            nextLabel = selectionLabel(shown);
          }
          if (label.textContent !== nextLabel) label.textContent = nextLabel;
        }
        if (codeRender && focusSelection) {
          const key = `${focusSelection[0]}:${focusSelection[1]}`;
          const toTop = codeFocusTop(layout, focusSelection);
          if (layout.lastScrollKey !== key) {
            layout.lastScrollKey = key;
            if (animationTargetTime != null && typeof codeRender.scrollTo === 'function') {
              codeRender.scrollTo({top: toTop, behavior: 'smooth'});
            } else {
              codeRender.scrollTop = toTop;
            }
          } else if (animationTargetTime == null && Math.abs(codeRender.scrollTop - toTop) > 1) {
            // Random-access seek/scrub remains exact; only authored playback uses
            // browser-managed smooth scrolling.
            codeRender.scrollTop = toTop;
          }
        }
      }
      if (fitState) renderFitClone(slide, el, fitState);
    }
  }

  function resetSlideFrame(slide) {
    slide.classList.remove('visible');
    slide.setAttribute('aria-hidden','true');
    slide.style.transform='';
    slide.style.transformOrigin='';
    slide.style.borderRadius='';
    slide.style.boxShadow='';
    slide.style.opacity='';
    slide.style.zIndex='';
  }

  function showSlide(id, z=1) {
    const slide = slideById.get(id);
    if (!slide) return null;
    slide.classList.add('visible');
    slide.setAttribute('aria-hidden','false');
    slide.style.zIndex=String(z);
    return slide;
  }

  function activeTransitionAt(time) {
    return timeline.transitions.find(tr => time > tr.start && time < tr.end) || null;
  }

  function staticSpanAt(time) {
    let result = timeline.slides[0];
    for (const span of timeline.slides) {
      if (time >= span.start) result = span;
      else break;
    }
    return result;
  }

  function transitionSharedIds(tr) {
    return Object.entries(tr.args || {})
      .filter(([key]) => /^_\d+$/.test(key))
      .sort((a,b) => Number(a[0].slice(1)) - Number(b[0].slice(1)))
      .map(([,value]) => String(value));
  }

  function clearSharedOverlay() {
    sharedOverlay.replaceChildren();
  }

  function lerpNumber(a, b, p) {
    return a + (b - a) * p;
  }

  function regionSurfaceStyle(el) {
    const style = getComputedStyle(el, '::before');
    return {
      backgroundColor: style.backgroundColor,
      borderColor: style.borderColor,
      borderWidth: parseFloat(style.borderTopWidth) || 0,
      borderRadius: parseFloat(style.borderTopLeftRadius) || 0,
    };
  }

  function renderSharedRegionSurface(sourceEl, targetEl, sourceRect, targetRect, p) {
    const sourceStyle = regionSurfaceStyle(sourceEl);
    const targetStyle = regionSurfaceStyle(targetEl);
    const proxy = document.createElement('div');
    proxy.className = 'shared-region-surface';
    proxy.setAttribute('aria-hidden', 'true');
    proxy.style.left = `${lerpNumber(sourceRect.left, targetRect.left, p)}px`;
    proxy.style.top = `${lerpNumber(sourceRect.top, targetRect.top, p)}px`;
    proxy.style.width = `${lerpNumber(sourceRect.width, targetRect.width, p)}px`;
    proxy.style.height = `${lerpNumber(sourceRect.height, targetRect.height, p)}px`;
    proxy.style.backgroundColor = `color-mix(in srgb, ${sourceStyle.backgroundColor} ${100*(1-p)}%, ${targetStyle.backgroundColor})`;
    proxy.style.borderStyle = 'solid';
    proxy.style.borderColor = `color-mix(in srgb, ${sourceStyle.borderColor} ${100*(1-p)}%, ${targetStyle.borderColor})`;
    proxy.style.borderWidth = `${lerpNumber(sourceStyle.borderWidth, targetStyle.borderWidth, p)}px`;
    proxy.style.borderRadius = `${lerpNumber(sourceStyle.borderRadius, targetStyle.borderRadius, p)}px`;
    sharedOverlay.appendChild(proxy);
  }

  function renderSharedVisual(sourceEl, sourceRect, targetRect, p) {
    const proxy = sourceEl.cloneNode(true);
    proxy.classList.add('shared-visual-proxy');
    for (const node of [proxy, ...proxy.querySelectorAll('[data-object], [data-slide-object]')]) {
      node.removeAttribute('data-object');
      node.removeAttribute('data-slide-object');
    }
    proxy.removeAttribute('id');
    proxy.setAttribute('aria-hidden', 'true');
    proxy.style.left = `${lerpNumber(sourceRect.left, targetRect.left, p)}px`;
    proxy.style.top = `${lerpNumber(sourceRect.top, targetRect.top, p)}px`;
    proxy.style.width = `${lerpNumber(sourceRect.width, targetRect.width, p)}px`;
    proxy.style.height = `${lerpNumber(sourceRect.height, targetRect.height, p)}px`;
    proxy.style.visibility = 'visible';
    proxy.style.opacity = '1';
    proxy.style.filter = 'none';
    proxy.style.clipPath = 'none';
    proxy.style.transform = 'none';
    sharedOverlay.appendChild(proxy);
  }

  function applySharedTransition(source, target, tr, p) {
    const ids = transitionSharedIds(tr);
    if (!ids.length) return applyPush(source, target, p, tr.args?.direction || 'LEFT');
    source.style.opacity = String(1-p);
    target.style.opacity = String(p);
    clearSharedOverlay();
    for (const id of ids) {
      const sourceEl = source.querySelector(`[data-slide-object="true"][data-object="${CSS.escape(id)}"]`);
      const targetEl = target.querySelector(`[data-slide-object="true"][data-object="${CSS.escape(id)}"]`);
      if (!sourceEl || !targetEl) continue;
      const sourceRect = sourceEl.getBoundingClientRect();
      const targetRect = targetEl.getBoundingClientRect();
      if (!sourceRect.width || !sourceRect.height || !targetRect.width || !targetRect.height) continue;
      if (sourceEl.dataset.kind === 'region' && targetEl.dataset.kind === 'region') {
        // A region owns only its presentation surface; its children are distinct
        // objects and stay with their respective pages. This mirrors Zanim's
        // explicit object identity instead of implicitly replacing a subtree.
        sourceEl.classList.add('shared-surface-hidden');
        targetEl.classList.add('shared-surface-hidden');
        renderSharedRegionSurface(sourceEl, targetEl, sourceRect, targetRect, p);
      } else {
        // Stable visual leaves use one transient for the entire handoff. Both
        // endpoints are hidden, so there is never a source/target cross-fade.
        sourceEl.style.visibility = 'hidden';
        targetEl.style.visibility = 'hidden';
        renderSharedVisual(sourceEl, sourceRect, targetRect, p);
      }
    }
  }

  function applyTransition(tr, time) {
    const source = showSlide(tr.source, 1);
    const target = showSlide(tr.target, 4);
    if (!source || !target) return;
    const raw = clamp((time - tr.start) / Math.max(1e-9, tr.end - tr.start), 0, 1);
    const p = eased(tr.easing, raw);

    if (tr.kind === 'cut') {
      if (p < 0.5) target.classList.remove('visible');
      else source.classList.remove('visible');
      return;
    }
    if (tr.kind === 'fade') {
      source.style.opacity=String(1-p);
      target.style.opacity=String(p);
      return;
    }
    if (tr.kind === 'shared') {
      applySharedTransition(source, target, tr, p);
      return;
    }
    if (tr.kind === 'embed_zoom') {
      const ref = source.querySelector(`[data-kind="slide-ref"][data-target-slide="${CSS.escape(tr.target)}"]`);
      if (!ref) return applyPush(source, target, p, tr.args?._0 || 'LEFT');
      const visual = ref.querySelector('.mini-slide') || ref;
      const targetRect = target.getBoundingClientRect();
      const sourceRect = visual.getBoundingClientRect();
      if (!targetRect.width || !targetRect.height || !sourceRect.width || !sourceRect.height) return;

      // Never scale the real target slide. Chrome can keep a low-resolution
      // compositor surface after a thumbnail-to-fullscreen transform, leaving
      // text blurred until a later page switch forces re-rasterization. Animate
      // a disposable clone instead; the target remains pristine and becomes the
      // next static frame immediately after the transition.
      const proxy = target.cloneNode(true);
      proxy.classList.add('embed-zoom-proxy', 'visible');
      proxy.removeAttribute('data-slide');
      proxy.removeAttribute('data-index');
      proxy.setAttribute('aria-hidden', 'true');
      for (const node of [proxy, ...proxy.querySelectorAll('[data-object], [data-slide-object]')]) {
        node.removeAttribute('data-object');
        node.removeAttribute('data-slide-object');
      }
      for (const video of proxy.querySelectorAll('video')) {
        video.removeAttribute('autoplay');
        video.controls = false;
      }

      const left = lerpNumber(sourceRect.left, targetRect.left, p);
      const top = lerpNumber(sourceRect.top, targetRect.top, p);
      const scaleX = lerpNumber(sourceRect.width / LOGICAL_WIDTH, targetRect.width / LOGICAL_WIDTH, p);
      const scaleY = lerpNumber(sourceRect.height / LOGICAL_HEIGHT, targetRect.height / LOGICAL_HEIGHT, p);
      proxy.style.position = 'fixed';
      proxy.style.left = `${left}px`;
      proxy.style.top = `${top}px`;
      proxy.style.width = `${LOGICAL_WIDTH}px`;
      proxy.style.height = `${LOGICAL_HEIGHT}px`;
      proxy.style.margin = '0';
      proxy.style.transformOrigin = 'top left';
      proxy.style.transform = `scale(${scaleX},${scaleY})`;
      proxy.style.zIndex = '70';
      proxy.style.pointerEvents = 'none';
      sharedOverlay.appendChild(proxy);

      // The source still provides the surrounding page while its embedded
      // preview is replaced by the geometrically identical proxy. Keep the real
      // target hidden throughout the transition so it is never composited at a
      // scaled resolution.
      target.classList.remove('visible');
      target.setAttribute('aria-hidden', 'true');
      ref.style.visibility='hidden';
      return;
    }
    applyPush(source, target, p, tr.args?._0 || 'LEFT');
  }

  function applyPush(source, target, p, direction='LEFT') {
    const d = String(direction).toUpperCase();
    if (d === 'RIGHT') {
      source.style.transform=`translateX(${100*p}%)`;
      target.style.transform=`translateX(${-100*(1-p)}%)`;
    } else if (d === 'UP') {
      source.style.transform=`translateY(${-100*p}%)`;
      target.style.transform=`translateY(${100*(1-p)}%)`;
    } else if (d === 'DOWN') {
      source.style.transform=`translateY(${100*p}%)`;
      target.style.transform=`translateY(${-100*(1-p)}%)`;
    } else {
      source.style.transform=`translateX(${-100*p}%)`;
      target.style.transform=`translateX(${100*(1-p)}%)`;
    }
  }

  function stopAtOrBefore(time) {
    let result = timeline.stops[0];
    for (const stop of timeline.stops) {
      if (stop.time <= time + 0.0005) result = stop;
      else break;
    }
    return result;
  }

  function updateHud(time) {
    const tr = activeTransitionAt(time);
    if (tr) {
      const source = spanById.get(tr.source);
      const target = spanById.get(tr.target);
      counter.textContent=`${source.index+1}→${target.index+1}/${timeline.slides.length}`;
      stepLabel.textContent=tr.kind;
      return;
    }
    const span = staticSpanAt(time);
    const stop = stopAtOrBefore(time);
    counter.textContent=`${span.index+1}/${timeline.slides.length}`;
    stepLabel.textContent=stop?.slide === span.id && stop.kind !== 'ready' ? stop.label : readyLabel;
  }

  function syncVideoVisibility() {
    for (const slide of slides) {
      const visible = slide.classList.contains('visible');
      const wasVisible = slide.dataset.mediaVisible === 'true';
      for (const video of slide.querySelectorAll('video')) {
        if (video.closest('.embedded-slide-copy')) continue;
        if (!visible) {
          if (!video.paused) video.pause();
        } else if (!wasVisible && video.dataset.autoplay === 'true') {
          const attempt = video.play();
          if (attempt && typeof attempt.catch === 'function') attempt.catch(() => {});
        }
      }
      slide.dataset.mediaVisible = visible ? 'true' : 'false';
    }
  }

  function renderAt(time) {
    currentTime = clamp(Number(time) || 0, 0, timeline.total_duration);
    clearSharedOverlay();
    for (const slide of slides) resetSlideFrame(slide);
    for (const span of timeline.slides) {
      const sampleTime = clamp(currentTime, span.start, span.motion_end);
      renderSlideObjects(span, sampleTime);
    }

    const tr = activeTransitionAt(currentTime);
    if (tr) applyTransition(tr, currentTime);
    else {
      const span = staticSpanAt(currentTime);
      showSlide(span.id, 1);
    }
    // renderSlideObjects() samples every slide for deterministic random access,
    // but temporary fit visuals belong only to slides currently participating
    // in the frame. Remove them from hidden slides so completed source cards do
    // not leak into later pages via visibility:visible descendants.
    for (const slide of slides) {
      if (slide.classList.contains('visible')) continue;
      for (const clone of slide.querySelectorAll(':scope > .fit-motion-clone')) clone.remove();
    }
    syncVideoVisibility();
    updateHud(currentTime);
    scrub.value = String(currentTime);
    return currentTime;
  }

  function hydrateEmbeddedSlides() {
    for (const ref of document.querySelectorAll('[data-kind="slide-ref"][data-target-slide]')) {
      const target = slideById.get(ref.dataset.targetSlide);
      const surface = ref.querySelector('.mini-slide');
      if (!target || !surface) continue;
      const copy = target.cloneNode(true);
      copy.classList.remove('visible');
      copy.classList.add('embedded-slide-copy');
      copy.setAttribute('aria-hidden','true');
      copy.removeAttribute('data-slide');
      copy.removeAttribute('data-index');
      // Keep the exact target's logical layout, then scale only its preview.
      // A percentage width reflows the copy and makes it differ from the page
      // that embed_zoom promotes into view.
      const fitPreview = () => copy.style.setProperty('--soda-preview-scale', String(surface.clientWidth / LOGICAL_WIDTH));
      fitPreview();
      if (typeof ResizeObserver !== 'undefined') new ResizeObserver(fitPreview).observe(surface);
      for (const el of [copy, ...copy.querySelectorAll('[data-object]')]) {
        if (el.dataset?.object) {
          el.dataset.previewObject = el.dataset.object;
          el.removeAttribute('data-object');
        }
      }
      const placeholder = surface.querySelector('.placeholder');
      if (placeholder) placeholder.remove();
      surface.appendChild(copy);
    }
  }

  function collectLayoutDiagnostics() {
    const restore = currentTime;
    const issues = [];
    for (const candidate of slides) resetSlideFrame(candidate);
    clearSharedOverlay();
    for (const span of timeline.slides) {
      const slide = slideById.get(span.id);
      if (!slide) continue;
      for (const el of slide.querySelectorAll('.obj')) resetObject(el);
      showSlide(span.id, 1);
      const root = slide.querySelector('[data-object="slide"]');
      const frame = root?.getBoundingClientRect() || slide.getBoundingClientRect();
      const stageScale = currentStageScale();
      const rootStyle = getComputedStyle(root || slide);
      const safeFrame = {
        left: frame.left + parseFloat(rootStyle.paddingLeft || 0) * stageScale,
        right: frame.right - parseFloat(rootStyle.paddingRight || 0) * stageScale,
        top: frame.top + parseFloat(rootStyle.paddingTop || 0) * stageScale,
        bottom: frame.bottom - parseFloat(rootStyle.paddingBottom || 0) * stageScale,
      };
      for (const el of slide.querySelectorAll('[data-slide-object="true"]')) {
        if (el.dataset.object === 'slide' || el.closest('.embedded-slide-copy')) continue;
        const rect = el.getBoundingClientRect();
        const over = {
          left: Math.max(0, frame.left - rect.left), right: Math.max(0, rect.right - frame.right),
          top: Math.max(0, frame.top - rect.top), bottom: Math.max(0, rect.bottom - frame.bottom),
        };
        const maxOver = Math.max(over.left, over.right, over.top, over.bottom) / stageScale;
        if (maxOver > 3) {
          issues.push({slide: span.id, object: el.dataset.object, kind: 'bounds', detail: `outside slide frame by ${maxOver.toFixed(1)} logical px`});
        }
        // Keep authored content inside the safe area, not merely inside the
        // physical slide. Also detect overflow into an adjacent grid region.
        const parent = el.parentElement;
        const parentFrame = parent?.classList.contains('kind-region')
          ? parent.getBoundingClientRect() : safeFrame;
        const spill = Math.max(0, parentFrame.left - rect.left,
          rect.right - parentFrame.right, parentFrame.top - rect.top,
          rect.bottom - parentFrame.bottom) / stageScale;
        if (maxOver <= 3 && spill > 3) {
          issues.push({slide: span.id, object: el.dataset.object, kind: 'layout-overflow', detail: `outside content area by ${spill.toFixed(1)} logical px`});
        }
      }
      const title = slide.querySelector('h1[data-object="title"]');
      if (title) {
        const lineHeight = parseFloat(getComputedStyle(title).lineHeight || 0);
        if (lineHeight > 0) {
          const lines = Math.round((title.getBoundingClientRect().height / currentStageScale()) / lineHeight);
          if (lines > 2) issues.push({slide: span.id, object: 'title', kind: 'title-wrap', detail: `${lines} title lines`});
        }
      }
      resetSlideFrame(slide);
    }
    renderAt(restore);
    return issues;
  }

  function toggleLayoutDiagnostics() {
    const showing = diagnosticsPanel.classList.toggle('visible');
    if (!showing) return;
    const issues = collectLayoutDiagnostics();
    diagnosticsPanel.replaceChildren();
    const title = document.createElement('strong');
    title.textContent = `Layout diagnostics · ${issues.length} issue${issues.length===1?'':'s'}`;
    diagnosticsPanel.appendChild(title);
    if (!issues.length) {
      const ok = document.createElement('div'); ok.className='ok'; ok.textContent='No overflow detected.'; diagnosticsPanel.appendChild(ok);
    } else {
      for (const issue of issues) {
        const row = document.createElement('div'); row.className='warn';
        row.textContent = `${issue.slide}.${issue.object} · ${issue.kind} · ${issue.detail}`;
        diagnosticsPanel.appendChild(row);
      }
    }
  }

  function nearestStop(direction, fromTime = currentTime) {
    if (direction > 0) return timeline.stops.find(stop => stop.time > fromTime + 0.0005) || null;
    for (let i=timeline.stops.length-1;i>=0;i--) {
      if (timeline.stops[i].time < fromTime - 0.0005) return timeline.stops[i];
    }
    return null;
  }
  function completeActiveAnimation() {
    if (animationTargetTime == null) return currentTime;
    const completed = animationTargetTime;
    ++playbackToken;
    animationTargetTime = null;
    renderAt(completed);
    return completed;
  }

  function finishAnimationTarget(token) {
    if (token === playbackToken) animationTargetTime = null;
  }

  function startAnimationTo(targetTime) {
    // This primitive only starts playback. It never preempts by itself.
    // Preemption belongs to the caller handling a newer navigation request.
    const from = currentTime;
    const to = clamp(targetTime, 0, timeline.total_duration);
    const token = ++playbackToken;
    animationTargetTime = to;
    const durationMs = Math.abs(to - from) * 1000;
    if (durationMs < 1) { renderAt(to); finishAnimationTarget(token); return Promise.resolve(currentTime); }
    const started = performance.now();
    return new Promise(resolve => {
      const frame = now => {
        if (token !== playbackToken) return resolve(currentTime);
        const p = clamp((now - started) / durationMs, 0, 1);
        renderAt(from + (to - from) * p);
        if (p < 1) requestAnimationFrame(frame);
        else { finishAnimationTarget(token); resolve(currentTime); }
      };
      requestAnimationFrame(frame);
    });
  }

  function animateTo(targetTime) {
    // Public direct animation requests follow the same preemption rule as
    // keyboard navigation: finish whatever is currently running, then start
    // exactly the newest requested animation.
    completeActiveAnimation();
    return startAnimationTo(targetTime);
  }

  function seek(time) {
    ++playbackToken;
    animationTargetTime = null;
    return renderAt(time);
  }

  scrub.addEventListener('input', () => seek(Number(scrub.value)));

  function prepareCodeFocusNavigation(targetTime) {
    const currentSpan = staticSpanAt(currentTime);
    const targetSpan = staticSpanAt(targetTime);
    if (!currentSpan || !targetSpan || currentSpan.id !== targetSpan.id) return;
    const slide = slideById.get(currentSpan.id);
    if (!slide?.classList.contains('visible')) return;
    const runtime = slideRenderState(currentSpan, slide);
    for (const [target, clips] of runtime.groups) {
      const el = runtime.objectsById.get(String(target));
      if (!el?.classList.contains('code-block')) continue;
      let selection = null;
      for (const clip of clips) {
        if (clip.op === 'focus' && targetTime >= clip.start - 0.0005) {
          selection = codeSelection(clip.args);
        }
      }
      if (!selection) continue;
      const layout = codeLayout(el);
      const codeRender = layout.codeRender;
      if (!codeRender) continue;
      const top = codeFocusTop(layout, selection);
      const key = `${selection[0]}:${selection[1]}`;
      const distance = Math.abs(codeRender.scrollTop - top);
      const farJump = distance > Math.max(240, layout.clientHeight * 1.5);
      layout.lastScrollKey = key;
      if (!farJump && typeof codeRender.scrollTo === 'function') {
        codeRender.scrollTo({top, behavior: 'smooth'});
      } else {
        codeRender.scrollTop = top;
      }
    }
  }

  function navigate(direction) {
    // Every authored animation is preemptible. Only a *new* navigation event
    // completes the currently active animation; the first event starts it
    // normally and leaves it visible until completion or the next event.
    if (animationTargetTime != null) completeActiveAnimation();
    const stop = nearestStop(direction, currentTime);
    if (stop) {
      prepareCodeFocusNavigation(stop.time);
      startAnimationTo(stop.time);
    }
  }

  document.addEventListener('keydown', e => {
    if (e.key==='ArrowRight' || e.key===' ' || e.key==='PageDown') {
      e.preventDefault(); navigate(1);
    } else if (e.key==='ArrowLeft' || e.key==='PageUp') {
      e.preventDefault(); navigate(-1);
    } else if ((e.key==='d' || e.key==='D') && !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.preventDefault(); toggleLayoutDiagnostics();
    } else if (e.key==='Home') {
      e.preventDefault(); animateTo(0);
    } else if (e.key==='End') {
      e.preventDefault(); animateTo(timeline.total_duration);
    }
  });

  // Establish every slide's authored t=0 state before cloning nested SlideObjects.
  for (const span of timeline.slides) renderSlideObjects(span, span.start);
  hydrateEmbeddedSlides();
  slideRenderCache.clear();
  renderAt(0);
  mountZanimScenes();

  // Public random-access renderer. No forward/backward lifecycle state exists:
  // every frame is reconstructed solely from absolute presentation time.
  window.sodaTimeline = {
    renderAt: seek,
    seek,
    animateTo,
    get time() { return currentTime; },
    get duration() { return timeline.total_duration; },
    stops: timeline.stops,
  };
  window.sodaDiagnostics = { layout: collectLayoutDiagnostics, toggle: toggleLayoutDiagnostics };
  window.sodaObjects = {
    get(slideId, objectId) {
      const slide = slideById.get(slideId);
      return slide?.querySelector(`[data-slide-object="true"][data-object="${CSS.escape(objectId)}"]`) || null;
    },
    frame(slideId, objectId) {
      const el = this.get(slideId, objectId);
      if (!el) return null;
      const rect = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      return {
        x: rect.x, y: rect.y, width: rect.width, height: rect.height,
        transform: style.transform, opacity: Number(style.opacity),
      };
    },
  };
})();
