/* The Briefing — reel player (plain JS, no build step). Loaded before app.js; app.js calls Player.init().
 *
 * Rules this file implements:
 *  - ONE shared <video playsinline muted preload="metadata"> element is moved into whichever story card is ≥60%
 *    visible, with its src swapped. iOS only allows sound on an element after a user gesture on THAT element, so
 *    reusing one element means the first 🔊 tap unlocks sound for every later reel (and for Play all).
 *  - Muted autoplay can still be refused (iOS Low Power Mode): play() rejects → we show a big ▶ overlay.
 *  - The card's poster <img> stays visible until the video is actually playing (CSS: .started).
 *  - A reel is used only if its reel_hash equals the story's reel_hash: a video made for an older version of the
 *    story is stale and is ignored (the card keeps its gradient hero).
 *  - If src fails → try fallback_src → if that fails too, app.js turns the card back into the gradient hero.
 *  - Play all: full-screen story-style player across every available reel (tap right/left, auto-advance on ended,
 *    swipe down / ✕ to close, "Read explainer" pauses and opens the sheet).
 *  - While today's edition is open before 08:30 IST, ../briefing/videos/<date>.json is re-checked every 2 minutes;
 *    new reels are handed to app.js, which attaches them without disturbing the card being read.
 */
window.Player = (() => {
  'use strict';

  // ------------------------------------------------------------ the one shared video element
  const V = document.createElement('video');
  V.className = 'st-video';
  V.muted = true; V.defaultMuted = true; V.playsInline = true; V.preload = 'metadata';
  V.setAttribute('muted', ''); V.setAttribute('playsinline', ''); V.setAttribute('webkit-playsinline', '');
  V.setAttribute('preload', 'metadata'); V.setAttribute('disablepictureinpicture', ''); V.setAttribute('disableremoteplayback', '');
  V.setAttribute('aria-hidden', 'true');   // captions are burned in; the transcript lives in the explainer

  const IC = {
    play: '<polygon points="6 3 20 12 6 21 6 3"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    vol: '<path d="M11 4.7a.7.7 0 0 0-1.2-.5L6.4 7.6A1.4 1.4 0 0 1 5.4 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.4a1.4 1.4 0 0 1 1 .4l3.4 3.4a.7.7 0 0 0 1.2-.5z"/><path d="M16 9a5 5 0 0 1 0 6"/><path d="M19.4 18.4a9 9 0 0 0 0-12.8"/>',
    mute: '<path d="M11 4.7a.7.7 0 0 0-1.2-.5L6.4 7.6A1.4 1.4 0 0 1 5.4 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.4a1.4 1.4 0 0 1 1 .4l3.4 3.4a.7.7 0 0 0 1.2-.5z"/><path d="m22 9-6 6"/><path d="m16 9 6 6"/>',
    book: '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
  };
  const svg = (k, sz, cls) => `<svg class="i ${cls || ''}" width="${sz}" height="${sz}" viewBox="0 0 24 24" aria-hidden="true">${IC[k]}</svg>`;
  const esc = s => (s == null ? '' : String(s)).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // ------------------------------------------------------------ state
  let cfg = {};
  let date = null, stories = [];
  let avail = new Map();      // storyId -> {src, fallback, poster, duration}
  const failed = new Set();   // stories whose src AND fallback failed this session
  const pos = new Map();      // storyId -> last playback position (resume when you scroll back)
  let host = null;            // element whose classes reflect playback (a .card.story, or #pa)
  let hostId = null;          // story id loaded into V
  let usingFallback = false;
  let sound = false;          // the reader turned sound on (persists across src swaps on the same element)
  let userPaused = false, wasPlaying = false;
  let io = null, visible = null;   // visible: the .card.story that is ≥60% on screen
  let held = 0;               // >0 while the explainer covers the deck: never autoplay underneath it
  let pa = null;              // Play-all state: {ids, i}
  let lastPoll = 0;
  // Playback speed: the reader's choice, remembered on this device. Pitch is kept, so faster stays natural.
  const SPEEDS = [1, 1.25, 1.5, 1.75, 2];
  let speed = (() => { try { const x = parseFloat(localStorage.getItem('reelSpeed')); return SPEEDS.includes(x) ? x : 1; } catch (e) { return 1; } })();
  const speedLabel = x => `${x}×`;

  // ------------------------------------------------------------ manifest matching
  /** Only http(s) or plain relative paths (relative to the app, e.g. ../media/<date>/x.mp4) are allowed. */
  function mediaUrl(u) {
    if (typeof u !== 'string' || !u.trim()) return null;
    u = u.trim();
    if (/^https?:\/\//i.test(u)) return u;
    if (/^[a-z][a-z0-9+.-]*:/i.test(u) || u.startsWith('//')) return null;
    return u;
  }
  function match(m) {
    const out = new Map();
    if (!m || !Array.isArray(m.items) || (m.date && m.date !== date)) return out;
    const byId = new Map(stories.map(s => [s.id, s]));
    for (const it of m.items) {
      const s = it && byId.get(it.story);
      if (!s || !s.reel_hash || it.reel_hash !== s.reel_hash) continue;   // stale: made for an older version of the story
      if (failed.has(s.id)) continue;
      const src = mediaUrl(it.src), fallback = mediaUrl(it.fallback_src);
      if (!src && !fallback) continue;
      out.set(s.id, { src: src || fallback, fallback: src ? fallback : null, poster: mediaUrl(it.poster), duration: +it.duration_s || 0 });
    }
    return out;
  }

  /** Called by app.js for every edition it opens, with the already-fetched videos manifest (or null), before the
   *  deck is rendered, so story cards render in the right mode from the start (no layout shift later). */
  function load(d, st, manifest) {
    stopAll();
    date = d; stories = Array.isArray(st) ? st : []; failed.clear(); pos.clear(); hostId = null;
    avail = match(manifest);
    lastPoll = Date.now();
    return avail;
  }

  // ------------------------------------------------------------ card binding (IntersectionObserver)
  function bind(deck) {
    if (io) io.disconnect();
    visible = null;
    io = new IntersectionObserver(onIntersect, { root: deck, threshold: [0, 0.6] });
    deck.querySelectorAll('.slot[data-story]').forEach(s => io.observe(s));
  }
  function onIntersect(entries) {
    for (const e of entries) {
      const card = e.target.querySelector('.card.story');
      if (!card) continue;
      if (e.intersectionRatio >= 0.6) {
        visible = card;
        if (avail.has(card.dataset.story)) activate(card);
      } else if (visible === card || host === card) {
        if (visible === card) visible = null;
        if (host === card && !V.paused) { V.pause(); }
      }
    }
  }

  function setCls(k, on) { if (host) host.classList.toggle(k, !!on); }
  function clearHost(h) { if (h) h.classList.remove('started', 'blocked', 'ended', 'paused', 'loading'); }

  /** Move V into `mount` (inside hostEl) and make sure it holds story `id`. */
  function attach(hostEl, mount, id) {
    if (host !== hostEl) { clearHost(host); host = hostEl; if (hostId === id && V.currentTime > 0 && !V.ended) host.classList.add('started'); }
    if (V.parentNode !== mount) mount.appendChild(V);   // appended after the poster <img>, so it stacks above it
    if (hostId !== id) loadSrc(id);
  }
  function loadSrc(id) {
    if (hostId && !V.ended && V.currentTime > 1) pos.set(hostId, V.currentTime);
    hostId = id; usingFallback = false;
    const v = avail.get(id);
    clearHost(host); setCls('loading', true);
    paintProgress(0);
    V.src = v.src;
    const at = pos.get(id);
    if (at) V.addEventListener('loadedmetadata', () => { if (hostId === id && at < (V.duration || 0) - 2) V.currentTime = at; }, { once: true });
  }

  function activate(card) {
    if (pa || held || document.hidden) return;
    const id = card.dataset.story;
    if (!avail.has(id)) return;
    attach(card, card.querySelector('.st-media'), id);
    V.muted = !sound;
    play();
  }

  function applySpeed() {
    V.defaultPlaybackRate = speed;            // a new src starts at the default rate
    if (V.playbackRate !== speed) V.playbackRate = speed;
  }
  V.preservesPitch = true; V.webkitPreservesPitch = true;
  V.addEventListener('loadedmetadata', applySpeed);
  V.addEventListener('play', applySpeed);
  function paintSpeed() {
    document.querySelectorAll('.vspd').forEach(b => {
      b.textContent = speedLabel(speed);
      b.setAttribute('aria-label', `Playback speed ${speedLabel(speed)}. Tap to change`);
      b.classList.toggle('fast', speed !== 1);
    });
  }
  function cycleSpeed() {
    speed = SPEEDS[(SPEEDS.indexOf(speed) + 1) % SPEEDS.length];
    try { localStorage.setItem('reelSpeed', String(speed)); } catch (e) { /* private mode: this session only */ }
    applySpeed(); paintSpeed();
    if (cfg.toast) cfg.toast(`Reels play at ${speedLabel(speed)}`);
  }

  function play() {
    applySpeed();
    userPaused = false;
    setCls('paused', false);
    let p;
    try { p = V.play(); } catch (e) { p = null; }
    if (p && p.then) p.then(() => setCls('blocked', false), err => {
      if (err && err.name === 'AbortError') return;      // src swapped mid-play; the newer play() takes over
      if (!V.muted) { V.muted = true; sound = false; paintSound(); play(); return; }   // sound refused without a gesture
      setCls('loading', false); setCls('blocked', true); // muted autoplay refused too (e.g. iOS Low Power Mode)
    });
  }

  // ------------------------------------------------------------ video events
  V.addEventListener('playing', () => { setCls('started', true); setCls('blocked', false); setCls('ended', false); setCls('paused', false); setCls('loading', false); });
  V.addEventListener('waiting', () => setCls('loading', true));
  V.addEventListener('canplay', () => setCls('loading', false));
  V.addEventListener('pause', () => { if (userPaused && !V.ended) setCls('paused', true); });
  V.addEventListener('ended', () => {
    pos.delete(hostId);
    if (pa) paNext(); else setCls('ended', true);
  });
  V.addEventListener('timeupdate', () => paintProgress(V.duration ? V.currentTime / V.duration : 0));
  V.addEventListener('error', onError);

  function paintProgress(f) {
    f = Math.max(0, Math.min(1, f || 0));
    if (pa) { const b = document.querySelector(`#pa .pa-bars i:nth-child(${pa.i + 1}) b`); if (b) b.style.width = (f * 100) + '%'; }
    else if (host) { const b = host.querySelector('.st-prog i'); if (b) b.style.width = (f * 100) + '%'; }
  }

  function onError() {
    if (!hostId || !V.getAttribute('src')) return;
    const id = hostId, v = avail.get(id);
    if (v && !usingFallback && v.fallback) { usingFallback = true; setCls('loading', true); V.src = v.fallback; play(); return; }
    // both sources failed: forget this reel for the session and let app.js show the gradient hero instead
    failed.add(id); avail.delete(id); pos.delete(id); hostId = null;
    clearHost(host);
    V.removeAttribute('src'); try { V.load(); } catch (e) { /* ignore */ }
    if (pa) {
      pa.ids = pa.ids.filter(x => x !== id);
      if (!pa.ids.length) closePA(false); else paLoad(Math.min(pa.i, pa.ids.length - 1));
    } else if (host && host.classList.contains('story')) { host = null; }
    if (cfg.onVideoFailed) cfg.onVideoFailed(id);
  }

  // ------------------------------------------------------------ sound + taps (all inside user gestures)
  function paintSound() {
    document.documentElement.classList.toggle('sound-on', sound);
    document.querySelectorAll('.vbtn').forEach(b => { b.setAttribute('aria-pressed', String(sound)); b.setAttribute('aria-label', sound ? 'Turn sound off' : 'Turn sound on'); });
  }
  function toggleSound() {
    sound = !sound; V.muted = !sound; paintSound();
    // If the reel isn't running (e.g. blocked), this tap is our chance to start it with sound.
    if (sound && hostId && host && (V.paused || host.classList.contains('blocked'))) play();
  }
  function userPlay(btn) {
    const card = btn.closest('.card.story');
    if (card && host !== card) { if (!avail.has(card.dataset.story)) return; attach(card, card.querySelector('.st-media'), card.dataset.story); }
    if (V.ended) V.currentTime = 0;
    V.muted = !sound;
    play();
  }
  function tapMedia(el) {
    const card = el.closest('.card.story');
    if (!card || !avail.has(card.dataset.story)) return;
    if (host !== card) { userPlay(el); return; }
    if (V.paused) { if (V.ended) V.currentTime = 0; play(); }
    else { userPaused = true; V.pause(); }
  }

  document.addEventListener('click', e => {
    const t = e.target.closest('[data-act]');
    if (!t) return;
    switch (t.dataset.act) {
      case 'vsound': e.preventDefault(); toggleSound(); break;
      case 'vspeed': e.preventDefault(); cycleSpeed(); break;
      case 'vplay': e.preventDefault(); if (pa) { if (V.ended) V.currentTime = 0; play(); } else userPlay(t); break;
      case 'vtoggle': tapMedia(t); break;
      case 'playall': e.preventDefault(); playAll(t.dataset.story || null); break;
      case 'pa-close': closePA(true); break;
      case 'pa-prev': paPrev(); break;
      case 'pa-next': paNext(); break;
      case 'pa-read': paRead(); break;
      case 'pa-toggle': if (V.paused) play(); else { userPaused = true; V.pause(); } break;
    }
  });

  // ------------------------------------------------------------ Play all
  const paEl = () => document.getElementById('pa');
  function storyOf(id) { return stories.find(s => s.id === id); }

  function playAll(startId) {
    const ids = stories.filter(s => avail.has(s.id)).map(s => s.id);
    if (!ids.length) { if (cfg.toast) cfg.toast('No reels yet: they are added after the edition is published.'); return; }
    const root = paEl();
    root.innerHTML = `
      <div class="bgblur"></div>
      <div class="stage"></div>
      <button class="pa-zone prev" data-act="pa-prev" aria-label="Previous reel"></button>
      <button class="pa-zone next" data-act="pa-next" aria-label="Next reel"></button>
      <button class="st-play" data-act="vplay" aria-label="Play">${svg('play', 32, 'fill pl')}</button>
      <div class="st-spin"></div>
      <div class="pa-top">
        <div class="pa-bars"></div>
        <div class="pa-head"><span class="chip pa-chip"></span><span class="n"></span>
          <button class="pa-x" data-act="pa-close" aria-label="Close player"><span>${svg('x', 18)}</span></button></div>
      </div>
      <div class="pa-bot"><div class="pa-bot-in">
        <h3 class="pa-h clamp"></h3>
        <div class="pa-act">
          <button class="vbtn" data-act="vsound" aria-label="Turn sound off" aria-pressed="true">${svg('vol', 20, 'on')}${svg('mute', 20, 'off')}</button>
          <button class="vbtn vspd" data-act="vspeed">${speedLabel(speed)}</button>
          <button class="read" data-act="pa-read">${svg('book', 18)}<span>Read explainer</span></button>
        </div></div></div>`;
    root.hidden = false;
    paintSpeed();
    // The tap that opened Play all is the user gesture that lets this element play with sound.
    sound = true; V.muted = false; paintSound();
    if (host && host !== root) { V.pause(); clearHost(host); }
    host = null;
    pa = { ids, i: Math.max(0, ids.indexOf(startId)) };
    paLoad(pa.i);
    root.querySelector('.pa-x').focus({ preventScroll: true });
  }
  function paLoad(i) {
    const root = paEl();
    pa.i = i;
    const id = pa.ids[i], v = avail.get(id), s = storyOf(id) || {};
    const bars = root.querySelector('.pa-bars');
    if (bars.children.length !== pa.ids.length) bars.innerHTML = pa.ids.map(() => '<i><b></b></i>').join('');
    [...bars.children].forEach((el, k) => { el.classList.toggle('done', k < i); el.firstElementChild.style.width = k < i ? '100%' : '0'; });
    const sec = cfg.sectionKey ? cfg.sectionKey(s.section) : 'world';
    root.setAttribute('style', `--a:var(--${sec}-a);--b:var(--${sec}-b);--c:var(--${sec}-c)`);
    root.querySelector('.pa-chip').innerHTML = cfg.chipHTML ? cfg.chipHTML(s) : esc(s.section);
    root.querySelector('.n').textContent = `${i + 1} / ${pa.ids.length}`;
    root.querySelector('.pa-h').textContent = s.headline || '';
    const stage = root.querySelector('.stage');
    const blur = root.querySelector('.bgblur');
    blur.style.backgroundImage = v.poster ? `url("${encodeURI(v.poster)}")` : `linear-gradient(155deg,var(--a),var(--b))`;
    const oldPoster = stage.querySelector('.st-poster');
    if (oldPoster) oldPoster.remove();
    if (v.poster) { const img = new Image(); img.className = 'st-poster'; img.alt = ''; img.src = v.poster; stage.insertBefore(img, stage.firstChild); }
    attach(root, stage, id);
    if (hostId === id && !root.classList.contains('started') && V.currentTime > 0 && !V.paused) root.classList.add('started');
    V.muted = !sound;
    play();
  }
  function paNext() {
    if (!pa) return;
    if (pa.i < pa.ids.length - 1) paLoad(pa.i + 1);
    else { closePA(true); if (cfg.toast) cfg.toast('That’s all the reels. The briefs are waiting below.'); }
  }
  function paPrev() {
    if (!pa) return;
    if (V.currentTime > 3 || pa.i === 0) { V.currentTime = 0; play(); } else paLoad(pa.i - 1);
  }
  function paRead() {
    if (!pa) return;
    const id = pa.ids[pa.i];
    closePA(false);
    if (cfg.openExplainer) cfg.openExplainer(id);
  }
  function closePA(resume) {
    if (!pa) return;
    pa = null;
    V.pause();
    const root = paEl();
    clearHost(root);
    if (host === root) host = null;
    if (V.parentNode && root.contains(V)) V.remove();
    root.hidden = true; root.innerHTML = '';
    if (resume && visible && !held) activate(visible);
  }
  // swipe down to close, arrows/Escape on a keyboard
  let touch0 = null;
  document.addEventListener('touchstart', e => { if (pa && e.target.closest('#pa')) { const t = e.touches[0]; touch0 = { x: t.clientX, y: t.clientY }; } }, { passive: true });
  document.addEventListener('touchend', e => {
    if (!pa || !touch0) return;
    const t = e.changedTouches[0], dy = t.clientY - touch0.y, dx = t.clientX - touch0.x;
    touch0 = null;
    if (dy > 90 && Math.abs(dx) < 80) { e.preventDefault(); closePA(true); }
  });
  document.addEventListener('keydown', e => {
    if (!pa) return;
    if (e.key === 'Escape') { e.preventDefault(); closePA(true); }
    else if (e.key === 'ArrowRight') paNext();
    else if (e.key === 'ArrowLeft') paPrev();
    else if (e.key === ' ') { e.preventDefault(); if (V.paused) play(); else { userPaused = true; V.pause(); } }
  });

  // ------------------------------------------------------------ sheets, visibility, polling
  function hold() { held++; if (!V.paused) V.pause(); }
  function release() { held = Math.max(0, held - 1); if (!held && !pa && visible) activate(visible); }
  /** app.js calls this before re-rendering a card, so V is never thrown away with the old markup. */
  function detach(card) {
    if (host === card) { V.pause(); clearHost(card); host = null; if (V.parentNode) V.remove(); }
    if (visible === card) visible = null;
  }
  function stopAll() {
    if (pa) closePA(false);
    V.pause(); clearHost(host); host = null;
    if (V.parentNode) V.remove();
    V.removeAttribute('src'); try { V.load(); } catch (e) { /* ignore */ }
    hostId = null; visible = null;
    if (io) { io.disconnect(); io = null; }
  }

  function shouldPoll() {
    if (document.hidden || !date || !cfg.istNow) return false;
    const n = cfg.istNow();
    return n.date === date && n.minutes < 8 * 60 + 30;
  }
  /** Re-read the videos manifest; returns the ids that became available. */
  async function refresh() {
    if (!date) return [];
    const d = date;
    lastPoll = Date.now();
    const m = await cfg.getJSON(cfg.videosUrl(d));
    if (d !== date || !m) return [];
    const next = match(m), added = [];
    for (const [id, v] of next) {
      const cur = avail.get(id);
      if (!cur) { avail.set(id, v); added.push(id); }
      else if (cur.src !== v.src && id !== hostId) avail.set(id, v);   // re-rendered reel: swap quietly unless playing
    }
    if (added.length && cfg.onVideosChanged) cfg.onVideosChanged(added);
    return added;
  }
  setInterval(() => { if (shouldPoll()) refresh(); }, 120000);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { wasPlaying = !V.paused; if (wasPlaying) V.pause(); return; }
    if (wasPlaying && hostId && !held && (pa || (visible && host === visible))) play();
    wasPlaying = false;
    if (shouldPoll() && Date.now() - lastPoll > 60000) refresh();
  });

  function init(opts) { cfg = opts || {}; paintSound(); paintSpeed(); }

  return {
    init, load, bind, refresh, playAll, hold, release, detach, stopAll, mediaUrl,
    has: id => avail.has(id),
    info: id => avail.get(id) || null,
    list: () => stories.filter(s => avail.has(s.id)).map(s => s.id),
    seconds: () => [...avail.values()].reduce((n, v) => n + (v.duration || 0), 0),
    get sound() { return sound; },
    get speed() { return speed; },
    paintSpeed,
    get playingAll() { return !!pa; },
    // test hooks (used by tests/ui/flows.mjs)
    _video: V,
    _state: () => ({ hostId, sound, held, pa: pa ? { ids: pa.ids.slice(), i: pa.i } : null, avail: [...avail.keys()], visible: visible && visible.dataset.story }),
  };
})();
