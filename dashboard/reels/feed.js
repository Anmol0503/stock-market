/* The Briefing — reels-only phone app (plain JS, no build step).
 *
 * The day's news is 10 narrated reels. This app is a full-screen vertical feed of them: swipe between reels,
 * tap the left/right edge to skip back/forward a chapter, tap the middle to pause. Nothing else.
 *
 * Data, relative to dashboard/reels/:
 *   ../briefing/index.json          {latest, days[{date, edition, status, stories}]}
 *   ../briefing/<date>.json         an edition; only stories[] with a reel script are used
 *   ../briefing/videos/<date>.json  rendered reels {items[{story, reel_hash, src, fallback_src, poster, duration_s,
 *                                   chapters?[{t, key, label}]}]}; a reel is used only if its reel_hash matches
 * Reels are rendered 10–25 minutes after an edition is published, so the manifest is polled and a "being made"
 * slide turns into the video when it arrives.
 *
 * iOS rules (learned the hard way in player.js): ONE shared <video playsinline muted> element is moved into the
 * slide on screen; autoplay is muted; sound needs a tap, and once granted it carries over to later reels on the
 * same element; if play() is refused (Low Power Mode) a big ▶ appears.
 *
 * Routes: #<date> · #<date>/<storyId>. Testing: ?now=2026-11-12T07:10 pins the clock (IST); see tests/ui/.
 * The old full app (explainers, briefs, quiz) lives at full.html.
 */
(() => {
'use strict';

/* ================================================================ constants */
const PATHS = {
  index: '../briefing/index.json',
  edition: d => `../briefing/${d}.json`,
  videos: d => `../briefing/videos/${d}.json`,
  full: (d, id) => `full.html#${d}${id ? '/' + id : ''}`,
};
const CHAPTERS = {
  hook: 'The question', what_happened: 'What happened', so_far: 'The story so far', why: 'Why it happened',
  players: 'Who’s involved', numbers: 'By the numbers', idea: 'The idea', example: 'Worked example',
  views: 'Different views', for_you: 'What it means for you', next: 'What’s next', remember: 'Remember this',
};
// Older reels have no chapters: each scene becomes a part, named by its kind (or its on-screen text).
const KIND_LABEL = { hook: 'The question', outro: 'Remember this', steps: 'Worked example', timeline: 'How we got here',
  players: 'Who’s involved', views: 'Different views', big_number: 'By the numbers', bar: 'By the numbers', line: 'By the numbers' };
const SEC = { world: 'World', india: 'India', affects_you: 'Money & life', markets: 'Markets', tech_ai: 'Tech & AI',
  science: 'Science', f1: 'Formula 1', cricket: 'Cricket' };
const SPEEDS = [1, 1.25, 1.5, 1.75, 2];
const LATE_AFTER_MIN = 6 * 60 + 45;
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const WD = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const IC = {
  play: '<polygon points="6 3 20 12 6 21 6 3"/>',
  pause: '<rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/>',
  fwd: '<polygon points="13 19 22 12 13 5 13 19"/><polygon points="2 19 11 12 2 5 2 19"/>',
  back: '<polygon points="11 19 2 12 11 5 11 19"/><polygon points="22 19 13 12 22 5 22 19"/>',
  ext: '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  up: '<path d="m18 15-6-6-6 6"/>',
  cal: '<rect x="3" y="4" width="18" height="18" rx="3"/><path d="M16 2v4M8 2v4M3 10h18"/>',
  replay: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
  book: '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
  mute: '<path d="M11 4.7a.7.7 0 0 0-1.2-.5L6.4 7.6A1.4 1.4 0 0 1 5.4 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.4a1.4 1.4 0 0 1 1 .4l3.4 3.4a.7.7 0 0 0 1.2-.5z"/><path d="m22 9-6 6"/><path d="m16 9 6 6"/>',
  alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
};

/* ================================================================ helpers */
const $ = id => document.getElementById(id);
const feed = $('feed');
const esc = s => (s == null ? '' : String(s)).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const safeUrl = u => (typeof u === 'string' && /^https?:\/\/[^\s]+$/i.test(u.trim())) ? u.trim() : null;
const arr = v => (Array.isArray(v) ? v : []);
const icon = (k, sz = 18, cls = '') => `<svg class="i ${cls}" width="${sz}" height="${sz}" viewBox="0 0 24 24" aria-hidden="true">${IC[k] || ''}</svg>`;
const secKey = k => (SEC[k] ? k : 'world');
const vars = k => `--a:var(--${secKey(k)}-a);--b:var(--${secKey(k)}-b)`;
const nwords = s => String(s || '').split(/\s+/).filter(Boolean).length;
const mmss = t => { t = Math.max(0, Math.floor(t || 0)); return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`; };
const plural = (n, w) => `${n} ${n === 1 ? w : w + 's'}`;

/** "YYYY-MM-DD[THH:MM[:SS]][Z|±HH:MM]" → epoch ms; no offset = IST (the pipeline writes IST). */
function parseTime(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?)?\s*(Z|[+-]\d{2}:?\d{2})?$/.exec(String(s || '').trim());
  if (!m) return NaN;
  let off = 330;
  if (m[7]) off = m[7] === 'Z' ? 0 : (m[7][0] === '-' ? -1 : 1) * (+m[7].slice(1, 3) * 60 + +m[7].slice(-2));
  return Date.UTC(+m[1], +m[2] - 1, +m[3], +(m[4] || 0), +(m[5] || 0), +(m[6] || 0)) - off * 60000;
}
const NOW_SKEW = (() => {
  let s = null;
  try { s = new URLSearchParams(location.search).get('now') || localStorage.getItem('briefing_now'); } catch (e) { /* private mode */ }
  const t = s ? parseTime(s) : NaN;
  return isNaN(t) ? 0 : t - Date.now();
})();
const now = () => Date.now() + NOW_SKEW;
function istNow() {
  const d = new Date(now() + 330 * 60000);
  return { date: d.toISOString().slice(0, 10), minutes: d.getUTCHours() * 60 + d.getUTCMinutes() };
}
function dayLabel(date, { rel = true } = {}) {
  const [y, m, d] = String(date).split('-').map(Number);
  if (!d) return '';
  const wd = new Date(Date.UTC(y, m - 1, d)).getUTCDay();
  if (rel) {
    const diff = Math.round((parseTime(istNow().date) - parseTime(date)) / 864e5);
    if (diff === 0) return 'Today';
    if (diff === 1) return 'Yesterday';
  }
  return `${WD[wd]} ${d} ${MON[m - 1]}`;
}
function stamp(s) {
  const t = parseTime(s); if (isNaN(t)) return '';
  const d = new Date(t + 330 * 60000), h = d.getUTCHours(), mi = d.getUTCMinutes();
  return `${d.getUTCDate()} ${MON[d.getUTCMonth()]}, ${h % 12 || 12}:${String(mi).padStart(2, '0')} ${h < 12 ? 'AM' : 'PM'}`;
}
async function getJSON(url) {
  try {
    const r = await fetch(`${url}${url.includes('?') ? '&' : '?'}_=${Date.now()}`, { cache: 'no-store' });
    return r.ok ? await r.json() : null;
  } catch (e) { return null; }
}
function toast(html, ms) {
  const t = $('toast'); t.innerHTML = html; t.classList.add('show');
  clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove('show'), ms || 2600);
}
const store = {
  get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } },
};

/* ================================================================ state */
let INDEX = null, DOC = null, DATE = null;
let REELS = [];            // [{s, v: {src, fallback, poster, duration, chapters}|null, failed}]
let CUR = -1;              // index of the slide on screen (REELS.length = the end slide)
let READY = false, lastIndexFetch = 0;
let io = null;
const pos = new Map();     // story id -> resume position (s)

const days = () => arr(INDEX && INDEX.days).slice().sort((a, b) => (a.date < b.date ? 1 : -1));
const latestDate = () => { const ds = days(), l = INDEX && INDEX.latest; return (l && ds.some(d => d.date === l)) ? l : (ds[0] && ds[0].date) || null; };
const isToday = () => DATE === istNow().date;
const reelAt = i => REELS[i] || null;
const slideAt = i => feed.querySelector(`.slide[data-i="${i}"]`);

/* ================================================================ the shared video element */
const V = document.createElement('video');
V.className = 'vid';
V.muted = true; V.defaultMuted = true; V.playsInline = true; V.preload = 'metadata';
for (const a of ['muted', 'playsinline', 'webkit-playsinline', 'disablepictureinpicture', 'disableremoteplayback']) V.setAttribute(a, '');
V.setAttribute('preload', 'metadata');
V.setAttribute('aria-hidden', 'true');          // captions are burned in
V.preservesPitch = true; V.webkitPreservesPitch = true;
let hostId = null, usingFallback = false, userPaused = false, wasPlaying = false, held = 0;
let sound = false;
let speed = (() => { const x = parseFloat(store.get('reelSpeed')); return SPEEDS.includes(x) ? x : 1; })();

function host() { return hostId ? feed.querySelector(`.slide[data-id="${CSS.escape(hostId)}"]`) : null; }
function setCls(k, on) { const h = host(); if (h) h.classList.toggle(k, !!on); }
function applySpeed() { V.defaultPlaybackRate = speed; if (V.playbackRate !== speed) V.playbackRate = speed; }

function attach(i) {
  const r = reelAt(i), slide = slideAt(i);
  if (!r || !r.v || !slide) return false;
  const mount = slide.querySelector('.vmount');
  if (V.parentNode !== mount) mount.appendChild(V);
  if (hostId !== r.s.id) {
    if (hostId && !V.ended && V.currentTime > 1) pos.set(hostId, V.currentTime);
    hostId = r.s.id; usingFallback = false;
    slide.classList.remove('started', 'blocked', 'paused', 'ended');
    slide.classList.add('loading');
    V.src = r.v.src;
    const at = pos.get(r.s.id), id = r.s.id;
    V.addEventListener('loadedmetadata', () => { if (hostId === id && at && at < (V.duration || 0) - 2) V.currentTime = at; }, { once: true });
  }
  return true;
}
function play() {
  if (held || document.hidden) return;
  applySpeed();
  userPaused = false;
  setCls('paused', false);
  V.muted = !sound;
  let p;
  try { p = V.play(); } catch (e) { p = null; }
  if (p && p.then) p.then(() => setCls('blocked', false), err => {
    if (err && err.name === 'AbortError') return;                 // src swapped mid-play; the newer play() wins
    if (!V.muted) { sound = false; paintSound(); V.muted = true; play(); return; }   // sound refused without a gesture
    setCls('loading', false); setCls('blocked', true);              // even muted autoplay refused (Low Power Mode)
  });
}
function pause(user) { if (user) userPaused = true; V.pause(); }
function detachVideo() {
  if (hostId && !V.ended && V.currentTime > 1) pos.set(hostId, V.currentTime);
  V.pause();
  if (V.parentNode) V.remove();
  V.removeAttribute('src'); try { V.load(); } catch (e) { /* ignore */ }
  hostId = null;
}

V.addEventListener('playing', () => { const h = host(); if (h) { h.classList.add('started'); h.classList.remove('loading', 'blocked', 'paused', 'ended'); } });
V.addEventListener('waiting', () => setCls('loading', true));
V.addEventListener('pause', () => { if (!V.ended && userPaused) setCls('paused', true); });
V.addEventListener('loadedmetadata', () => { applySpeed(); const r = REELS.find(x => x.s.id === hostId); if (r) { r.dur = V.duration; r.chap = chaptersFor(r); if (cur() === r) paintChrome(); } });
V.addEventListener('play', applySpeed);
V.addEventListener('timeupdate', () => paintProgress());
V.addEventListener('progress', () => paintBuffered());
V.addEventListener('ended', () => {
  setCls('ended', true);
  const r = REELS.find(x => x.s.id === hostId);
  if (r) pos.delete(r.s.id);
  if (!$('sheet').hidden || scrubbing) return;
  go(CUR + 1, { smooth: true });                                 // auto-advance (the end slide after the last reel)
});
V.addEventListener('error', () => {
  const r = REELS.find(x => x.s.id === hostId);
  if (!r || !V.getAttribute('src')) return;
  if (!usingFallback && r.v.fallback) { usingFallback = true; setCls('loading', true); V.src = r.v.fallback; play(); return; }
  r.failed = true; r.v = null;
  const i = REELS.indexOf(r);
  detachVideo();
  renderSlide(i);
  if (i === CUR) paintChrome();
});

/* ================================================================ chapters */
/** [{t, label, key}] for a reel: the manifest's (new reels), else estimated from each scene's share of the words. */
function chaptersFor(r) {
  const dur = r.dur || (r.v && r.v.duration) || 0;
  const m = r.v && arr(r.v.chapters).filter(c => c && isFinite(+c.t));
  if (m && m.length) return m.map(c => ({ t: +c.t, key: c.key || '', label: CHAPTERS[c.key] || c.label || 'Part' })).sort((a, b) => a.t - b.t);
  const scenes = arr(r.s.reel && r.s.reel.scenes);
  if (!scenes.length || !dur) return [];
  const hasCh = scenes.some(sc => sc && sc.chapter);
  const w = scenes.map(sc => nwords(sc && (sc.speak || sc.say)) + 1.5);   // +1.5 ≈ the pause after each scene
  const total = w.reduce((a, b) => a + b, 0) || 1;
  const out = [];
  let acc = 0;
  scenes.forEach((sc, k) => {
    const t = dur * acc / total;
    acc += w[k];
    const key = hasCh ? (sc.chapter || '') : `${k}`;
    if (out.length && out[out.length - 1].key === key) return;
    const label = hasCh ? (CHAPTERS[sc.chapter] || 'Part') : (KIND_LABEL[sc.kind] || String(sc.show || '').trim() || `Part ${out.length + 1}`);
    out.push({ t: Math.round(t * 10) / 10, key, label });
  });
  return out;
}
const cur = () => reelAt(CUR);
function chapterIdx(r, t) {
  const ch = arr(r && r.chap);
  let k = 0;
  for (let j = 0; j < ch.length; j++) if (ch[j].t <= t + 0.1) k = j;
  return k;
}
function seek(t) {
  if (!isFinite(V.duration)) { V.addEventListener('loadedmetadata', () => { V.currentTime = t; }, { once: true }); }
  else V.currentTime = Math.max(0, Math.min(t, V.duration - 0.2));
  paintProgress(t);
  if (V.paused) play();
}
function skipChapter(dir) {
  const r = cur();
  if (!r || !r.v || hostId !== r.s.id) return;
  const ch = arr(r.chap), t = V.currentTime || 0;
  if (!ch.length) { seek(t + dir * 10); return; }
  const k = chapterIdx(r, t);
  if (dir > 0) {
    if (k + 1 < ch.length) { seek(ch[k + 1].t); chapToast('fwd', ch[k + 1].label); }
    else go(CUR + 1, { smooth: true });
  } else {
    const back = (t - ch[k].t > 3 || k === 0) ? k : k - 1;
    seek(ch[back].t); chapToast('back', ch[back].label);
  }
}
function chapToast(kind, label) {
  const el = slideAt(CUR) && slideAt(CUR).querySelector('.ctoast');
  if (!el) return;
  el.innerHTML = `${icon(kind, 16, 'fill')}<span>${esc(label)}</span>`;
  el.classList.remove('show'); void el.offsetWidth; el.classList.add('show');
  clearTimeout(chapToast.t); chapToast.t = setTimeout(() => el.classList.remove('show'), 1300);
}

/* ================================================================ chrome (top bar + bottom bar) */
function paintSound() {
  document.documentElement.classList.toggle('sound-on', sound);
  const b = $('snd'); b.setAttribute('aria-pressed', String(sound)); b.setAttribute('aria-label', sound ? 'Turn sound off' : 'Turn sound on');
}
function paintSpeed() {
  const b = $('spd'); b.textContent = `${speed}×`; b.classList.toggle('fast', speed !== 1);
  b.setAttribute('aria-label', `Playback speed ${speed}×. Tap to change`);
}
function paintChrome() {
  const n = REELS.length, r = cur(), end = CUR >= n;
  $('count').textContent = n ? (end ? `${n} / ${n}` : `${CUR + 1} / ${n}`) : '';
  document.body.classList.toggle('at-end', end);
  document.body.classList.toggle('novideo', !r || !r.v);
  const ticks = $('track').querySelector('.ticks');
  const ch = arr(r && r.chap), dur = (r && (r.dur || (r.v && r.v.duration))) || 0;
  ticks.innerHTML = dur ? ch.slice(1).map(c => `<i style="left:${(100 * c.t / dur).toFixed(2)}%"></i>`).join('') : '';
  $('chap').disabled = !ch.length;
  paintProgress();
  paintBuffered();
}
function paintProgress(tOverride) {
  const r = cur();
  const on = r && r.v && hostId === r.s.id;
  const dur = on ? (isFinite(V.duration) && V.duration) || r.dur || r.v.duration || 0 : 0;
  const t = tOverride != null ? tOverride : (on ? V.currentTime : 0);
  const f = dur ? Math.max(0, Math.min(1, t / dur)) : 0;
  const tr = $('track');
  tr.querySelector('.fill').style.transform = `scaleX(${f})`;
  tr.querySelector('.knob').style.left = `${(f * 100).toFixed(2)}%`;
  tr.setAttribute('aria-valuenow', String(Math.round(f * 100)));
  tr.querySelector('.time').textContent = dur ? `${mmss(t)} / ${mmss(dur)}` : '';
  const ch = arr(r && r.chap), chap = $('chap');
  if (ch.length) {
    const k = chapterIdx(r, t);
    chap.querySelector('.cl').textContent = ch[k].label;
    chap.querySelector('.cn').textContent = `${k + 1}/${ch.length}`;
  } else {
    chap.querySelector('.cl').textContent = r ? (r.v ? 'Reel' : 'Reel being made') : '';
    chap.querySelector('.cn').textContent = '';
  }
}
function paintBuffered() {
  const r = cur(), b = $('track').querySelector('.buf');
  if (!r || hostId !== (r.s && r.s.id) || !isFinite(V.duration) || !V.buffered.length) { b.style.transform = 'scaleX(0)'; return; }
  b.style.transform = `scaleX(${Math.min(1, V.buffered.end(V.buffered.length - 1) / V.duration)})`;
}
function paintDate() {
  const lbl = DATE ? dayLabel(DATE) : 'The Briefing';
  $('dateLbl').textContent = lbl;
}

/* scrubbing the progress bar */
let scrubbing = false;
function scrubTo(e) {
  const r = cur(); if (!r || !r.v || hostId !== r.s.id) return;
  const rail = $('track').querySelector('.rail').getBoundingClientRect();
  const dur = (isFinite(V.duration) && V.duration) || r.dur || r.v.duration || 0;
  if (!dur) return;
  const f = Math.max(0, Math.min(1, (e.clientX - rail.left) / rail.width));
  V.currentTime = f * dur * 0.999;
  paintProgress(f * dur);
}
$('track').addEventListener('pointerdown', e => {
  const r = cur(); if (!r || !r.v) return;
  scrubbing = true; $('track').classList.add('scrub');
  try { $('track').setPointerCapture(e.pointerId); } catch (x) { /* ignore */ }
  scrubTo(e); e.preventDefault();
});
$('track').addEventListener('pointermove', e => { if (scrubbing) scrubTo(e); });
const endScrub = () => { if (!scrubbing) return; scrubbing = false; $('track').classList.remove('scrub'); if (V.paused && !userPaused) play(); };
$('track').addEventListener('pointerup', endScrub);
$('track').addEventListener('pointercancel', endScrub);
$('track').addEventListener('keydown', e => {
  if (e.key === 'ArrowRight') { e.preventDefault(); seek((V.currentTime || 0) + 5); }
  if (e.key === 'ArrowLeft') { e.preventDefault(); seek((V.currentTime || 0) - 5); }
});

/* ================================================================ rendering */
function slideInner(r, i) {
  const s = r.s, v = r.v;
  const bd = v && v.poster ? `<img class="bdimg" src="${esc(v.poster)}" alt="" aria-hidden="true" loading="${Math.abs(i - CUR) <= 1 ? 'eager' : 'lazy'}">` : '';
  const chip = `<span class="chip">${esc(SEC[secKey(s.section)])}</span>`;
  let frame;
  if (v) {
    frame = `<div class="frame">
      ${v.poster ? `<img class="poster" src="${esc(v.poster)}" alt="" loading="${Math.abs(i - CUR) <= 1 ? 'eager' : 'lazy'}">` : ''}
      <div class="vmount"></div>
      <button class="zone l" data-act="chprev" aria-label="Previous chapter"></button>
      <button class="zone c" data-act="toggle" aria-label="Pause or play"></button>
      <button class="zone r" data-act="chnext" aria-label="Next chapter"></button>
      <div class="spin" aria-hidden="true"></div>
      <div class="pp" aria-hidden="true">${icon('play', 34, 'fill')}</div>
      <button class="bigplay" data-act="play" aria-label="Play">${icon('play', 34, 'fill')}</button>
      <button class="sndpill" data-act="sound">${icon('mute', 16)}<span>Tap for sound</span></button>
      <div class="ctoast" aria-hidden="true"></div>
    </div>`;
  } else {
    const making = !r.failed && isToday();
    const status = r.failed ? `${icon('alert', 16)}<span>This reel couldn’t load</span>`
      : making ? `<span class="dots"><i></i><i></i><i></i></span><span><b>Reel being made</b><small>Ready in a few minutes</small></span>`
      : `${icon('alert', 16)}<span>No reel for this story</span>`;
    frame = `<div class="frame making">
      <div class="mk-in">
        ${chip}
        <h2 class="hl">${esc(s.headline)}</h2>
        ${s.question ? `<p class="q">${esc(s.question)}</p>` : ''}
        <div class="mk">${status}</div>
        ${r.failed ? `<button class="btn" data-act="retry" data-i="${i}">${icon('replay', 16)}Try again</button>` : ''}
        ${!making ? `<a class="btn ghost" href="${esc(PATHS.full(DATE, s.id))}">${icon('book', 16)}Read it instead</a>` : ''}
      </div>
    </div>`;
  }
  return `<div class="bd">${bd}</div><div class="stage">${frame}</div>`;
}
function renderSlide(i) {
  const r = reelAt(i), el = slideAt(i);
  if (!r || !el) return;
  if (V.parentNode && el.contains(V)) { if (hostId && !V.ended && V.currentTime > 1) pos.set(hostId, V.currentTime); V.pause(); V.remove(); hostId = null; }
  el.className = 'slide' + (r.v ? ' has-video' : ' pending');
  el.innerHTML = slideInner(r, i);
}
function endSlide() {
  const n = REELS.length;
  const mins = Math.round(REELS.reduce((a, r) => a + ((r.v && (r.dur || r.v.duration)) || 0), 0) / 60)
    || (DOC && DOC.cover && DOC.cover.watch_min) || 0;
  const ds = days(), k = ds.findIndex(d => d.date === DATE), prev = k >= 0 ? ds[k + 1] : null;
  return `<section class="slide end" data-i="${n}" aria-label="You're caught up">
    <div class="bd"></div>
    <div class="stage"><div class="endc">
      <div class="tick">${icon('check', 34)}</div>
      <h2>You’re caught up</h2>
      <p>${plural(n, 'reel')}${mins ? ` · about ${mins} min` : ''} · ${esc(dayLabel(DATE, { rel: false }))}</p>
      <div class="ebtns">
        ${prev ? `<button class="btn" data-act="day" data-date="${esc(prev.date)}">${icon('cal', 16)}${esc(dayLabel(prev.date) === 'Yesterday' ? 'Watch yesterday’s reels' : 'Watch ' + dayLabel(prev.date, { rel: false }))}</button>` : ''}
        <button class="btn ghost" data-act="go" data-i="0">${icon('up', 16)}Back to the first reel</button>
      </div>
    </div></div>
  </section>`;
}
function render() {
  detachVideo();
  if (io) io.disconnect();
  if (!REELS.length) {
    feed.innerHTML = `<section class="slide end" data-i="0"><div class="bd"></div><div class="stage"><div class="endc">
      <h2>No reels for ${esc(dayLabel(DATE))}</h2><p>${DOC ? 'This edition has no reels.' : 'This day couldn’t be loaded.'}</p>
      <div class="ebtns"><button class="btn" data-act="archive">${icon('cal', 16)}Pick another day</button></div></div></div></section>`;
    CUR = 0; paintChrome(); return;
  }
  feed.innerHTML = REELS.map((r, i) => `<section class="slide" data-i="${i}" data-id="${esc(r.s.id)}" style="${vars(r.s.section)}" aria-label="${esc(r.s.headline)}"></section>`).join('') + endSlide();
  REELS.forEach((_, i) => renderSlide(i));
  io = new IntersectionObserver(onIntersect, { root: feed, threshold: [0.6] });
  feed.querySelectorAll('.slide').forEach(s => io.observe(s));
}
function onIntersect(entries) {
  for (const e of entries) if (e.isIntersecting && e.intersectionRatio >= 0.6) activate(+e.target.dataset.i);
}
function activate(i) {
  if (i === CUR && (hostId || !cur() || !cur().v)) { paintChrome(); return; }
  const prev = CUR;
  CUR = i;
  const r = cur();
  if (r && r.v) {
    if (prev !== i || !hostId || hostId !== r.s.id) { attach(i); if (r.v && !r.chap) r.chap = chaptersFor(r); }
    if (!userPaused || prev !== i) play();
  } else {
    if (hostId) { pos.set(hostId, V.currentTime); V.pause(); }
  }
  // posters of the neighbours load eagerly
  [i - 1, i + 1].forEach(k => { const s = slideAt(k); if (s) s.querySelectorAll('img[loading="lazy"]').forEach(im => { im.loading = 'eager'; }); });
  paintChrome();
  const id = r ? r.s.id : null;
  const h = `#${DATE}${id && i > 0 ? '/' + id : ''}`;
  if (location.hash !== h) history.replaceState(null, '', h);
}
function go(i, { smooth = false } = {}) {
  const el = slideAt(Math.max(0, Math.min(i, REELS.length)));
  if (!el) return;
  feed.scrollTo({ top: el.offsetTop, behavior: smooth ? 'smooth' : 'auto' });
}

/* ================================================================ data */
function mediaUrl(u) {
  if (typeof u !== 'string' || !u.trim()) return null;
  u = u.trim();
  if (/^https?:\/\//i.test(u)) return u;
  if (/^[a-z][a-z0-9+.-]*:/i.test(u) || u.startsWith('//')) return null;
  return u;
}
/** manifest -> Map(storyId -> video info), only for reels made from this exact script (reel_hash). */
function match(m, stories) {
  const out = new Map();
  if (!m || !Array.isArray(m.items) || (m.date && m.date !== DATE)) return out;
  const byId = new Map(stories.map(s => [s.id, s]));
  for (const it of m.items) {
    const s = it && byId.get(it.story);
    if (!s || !s.reel_hash || it.reel_hash !== s.reel_hash) continue;
    const src = mediaUrl(it.src), fallback = mediaUrl(it.fallback_src);
    if (!src && !fallback) continue;
    out.set(s.id, { src: src || fallback, fallback: src ? fallback : null, poster: mediaUrl(it.poster),
                    duration: +it.duration_s || 0, chapters: arr(it.chapters) });
  }
  return out;
}
async function openDate(date, { storyId = null } = {}) {
  detachVideo();
  DATE = date; CUR = -1; pos.clear();
  paintDate();
  feed.innerHTML = '<div class="boot"><div class="spin"></div><span>Loading reels…</span></div>';
  const [doc, man] = await Promise.all([getJSON(PATHS.edition(date)), getJSON(PATHS.videos(date))]);
  if (date !== DATE) return false;
  DOC = doc;
  const stories = arr(doc && doc.stories).filter(s => s && s.reel && arr(s.reel.scenes).length);
  const vids = match(man, stories);
  REELS = stories.map(s => ({ s, v: vids.get(s.id) || null, failed: false, dur: 0, chap: null }));
  REELS.forEach(r => { if (r.v) r.chap = chaptersFor(r); });
  render();
  document.body.classList.remove('nochrome');
  const k = storyId ? REELS.findIndex(r => r.s.id === storyId) : 0;
  requestAnimationFrame(() => { go(Math.max(0, k)); if (k <= 0) activate(0); });
  return true;
}
/** Re-read the manifest; reels that arrived replace their "being made" slides. Returns the ids added. */
async function refresh() {
  if (!DATE || !REELS.length) return [];
  const d = DATE, m = await getJSON(PATHS.videos(d));
  if (d !== DATE || !m) return [];
  const vids = match(m, REELS.map(r => r.s)), added = [];
  REELS.forEach((r, i) => {
    const v = vids.get(r.s.id);
    if (!v || r.failed) return;
    if (!r.v) { r.v = v; r.dur = 0; r.chap = chaptersFor(r); renderSlide(i); added.push(r.s.id); if (i === CUR) { CUR = -1; activate(i); } }
    else if (r.v.src !== v.src && r.s.id !== hostId) { r.v = v; r.chap = chaptersFor(r); renderSlide(i); }
  });
  if (added.length) toast(`${icon('check', 16)}<span>${plural(added.length, 'new reel')} ready</span>`);
  const e = feed.querySelector('.slide.end');
  if (e && added.length) { const tmp = document.createElement('div'); tmp.innerHTML = endSlide(); e.replaceWith(tmp.firstElementChild); io && io.observe(feed.querySelector('.slide.end')); }
  return added;
}
const pending = () => REELS.some(r => !r.v && !r.failed);
function shouldPoll() { return !document.hidden && DATE && isToday() && pending() && istNow().minutes < 12 * 60; }
setInterval(() => { if (shouldPoll()) refresh(); }, 60000);

async function checkNewer() {
  lastIndexFetch = Date.now();
  const idx = await getJSON(PATHS.index);
  if (!idx) return;
  INDEX = idx;
  const l = latestDate(), p = $('newPill');
  if (l && DATE && l > DATE) { p.innerHTML = `${icon('up', 14)}<span>New: ${esc(dayLabel(l))}’s reels</span>`; p.hidden = false; }
  else p.hidden = true;
}

/* ================================================================ sheets */
let sheetWasPlaying = false;
function openSheet(title, html, cls) {
  sheetWasPlaying = !V.paused;
  held++; V.pause();
  $('stitle').textContent = title;
  $('sbody').innerHTML = html;
  const sh = $('sheet');
  sh.className = cls || '';
  sh.hidden = false;
  document.body.classList.add('sheet-open');
  requestAnimationFrame(() => sh.classList.add('open'));
  const on = sh.querySelector('.on'); if (on) on.scrollIntoView({ block: 'center' });
}
function closeSheet() {
  const sh = $('sheet');
  if (sh.hidden) return;
  sh.classList.remove('open');
  document.body.classList.remove('sheet-open');
  held = Math.max(0, held - 1);
  setTimeout(() => { if (!sh.classList.contains('open')) sh.hidden = true; }, 260);
  if (sheetWasPlaying && !held) play();
}
function chaptersSheet() {
  const r = cur(); if (!r || !r.v) return;
  const ch = arr(r.chap), k = chapterIdx(r, V.currentTime || 0);
  openSheet('Chapters', `<p class="sh-sub">${esc(r.s.headline)}</p><ol class="chs">${ch.map((c, j) =>
    `<li><button class="${j === k ? 'on' : ''}" data-act="seekch" data-k="${j}"><span class="n">${j + 1}</span><span class="t">${esc(c.label)}</span><span class="tm">${mmss(c.t)}</span></button></li>`).join('')}</ol>`, 'chapters');
}
function sourcesSheet() {
  const r = cur(); if (!r) return;
  const s = r.s, src = arr(s.sources);
  const rows = src.map(x => {
    const url = safeUrl(x.url);
    const inner = `<span class="n">${esc(x.n)}</span><span class="b"><span class="pub">${esc(x.pub)}${x.type === 'primary' ? ' <em>Primary</em>' : ''}</span>
      ${x.published ? `<span class="dt">${esc(stamp(x.published))}</span>` : ''}${x.excerpt ? `<span class="ex">“${esc(x.excerpt)}”</span>` : ''}</span>${url ? icon('ext', 16, 'go') : ''}`;
    return `<li>${url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${inner}</a>` : `<div>${inner}</div>`}</li>`;
  }).join('');
  openSheet('Sources', `<p class="sh-sub">${esc(s.headline)}</p>
    <p class="sh-note">Every fact in this reel comes from these dated reports, checked before publishing.</p>
    ${rows ? `<ol class="srcs">${rows}</ol>` : '<p class="sh-note">No sources listed.</p>'}
    <a class="txt" href="${esc(PATHS.full(DATE, s.id))}">${icon('book', 16)}<span>Text version of this story</span>${icon('ext', 14)}</a>`, 'sources');
}
function archiveSheet() {
  const ds = days().slice(0, 21);
  openSheet('Pick a day', ds.length ? `<ul class="days">${ds.map(d => {
    const n = d.stories != null ? plural(d.stories, 'reel') : '';
    return `<li><button class="${d.date === DATE ? 'on' : ''}" data-act="day" data-date="${esc(d.date)}">
      <span class="d">${esc(dayLabel(d.date))}</span><span class="m">${esc(dayLabel(d.date) !== dayLabel(d.date, { rel: false }) ? dayLabel(d.date, { rel: false }) + ' · ' : '')}${esc(n)}</span>
      ${d.date === DATE ? icon('check', 18, 'ck') : ''}</button></li>`;
  }).join('')}</ul>` : '<p class="sh-note">No other days yet.</p>', 'archive');
}

/* ================================================================ input */
document.addEventListener('click', e => {
  const t = e.target.closest('[data-act]');
  if (!t) return;
  const act = t.dataset.act;
  switch (act) {
    case 'toggle': {
      const r = cur(); if (!r || !r.v) return;
      if (hostId !== r.s.id) { attach(CUR); play(); return; }
      if (V.paused) { if (V.ended) V.currentTime = 0; play(); flashPP('play'); } else { pause(true); flashPP('pause'); }
      break;
    }
    case 'play': { const r = cur(); if (!r || !r.v) return; if (hostId !== r.s.id) attach(CUR); if (V.ended) V.currentTime = 0; play(); break; }
    case 'chnext': skipChapter(1); break;
    case 'chprev': skipChapter(-1); break;
    case 'sound':
      e.preventDefault();
      sound = !sound; V.muted = !sound; paintSound();
      if (sound && hostId && (V.paused || (host() && host().classList.contains('blocked'))) && !held) play();
      break;
    case 'speed':
      speed = SPEEDS[(SPEEDS.indexOf(speed) + 1) % SPEEDS.length];
      store.set('reelSpeed', String(speed));
      applySpeed(); paintSpeed();
      toast(`<span>Reels play at <b>${speed}×</b></span>`, 1400);
      break;
    case 'chapters': chaptersSheet(); break;
    case 'sources': sourcesSheet(); break;
    case 'archive': archiveSheet(); break;
    case 'close': closeSheet(); break;
    case 'seekch': {
      const r = cur(), c = r && arr(r.chap)[+t.dataset.k];
      closeSheet();
      if (c) { if (hostId !== r.s.id) attach(CUR); seek(c.t); chapToast('fwd', c.label); }
      break;
    }
    case 'day': { const d = t.dataset.date; closeSheet(); if (d) openDate(d); break; }
    case 'latest': { $('newPill').hidden = true; const l = latestDate(); if (l) openDate(l); break; }
    case 'go': go(+t.dataset.i, { smooth: true }); break;
    case 'retry': { const r = reelAt(+t.dataset.i); if (r) { r.failed = false; refresh(); } break; }
  }
});
function flashPP(kind) {
  const el = slideAt(CUR) && slideAt(CUR).querySelector('.pp');
  if (!el) return;
  el.innerHTML = icon(kind, 34, 'fill');
  el.classList.remove('show'); void el.offsetWidth; el.classList.add('show');
}
document.addEventListener('keydown', e => {
  if (e.target.closest && e.target.closest('input, textarea')) return;
  if (!$('sheet').hidden) { if (e.key === 'Escape') closeSheet(); return; }
  if (e.key === 'ArrowDown' || e.key === 'PageDown') { e.preventDefault(); go(CUR + 1, { smooth: true }); }
  else if (e.key === 'ArrowUp' || e.key === 'PageUp') { e.preventDefault(); go(CUR - 1, { smooth: true }); }
  else if (e.key === 'ArrowRight' && e.target === document.body) skipChapter(1);
  else if (e.key === 'ArrowLeft' && e.target === document.body) skipChapter(-1);
  else if (e.key === ' ' && e.target === document.body) { e.preventDefault(); const z = feed.querySelector(`.slide[data-i="${CUR}"] .zone.c`); if (z) z.click(); }
  else if (e.key === 'm') $('snd').click();
});
// swipe the sheet down to close it
let sy = null;
$('sheet').addEventListener('touchstart', e => { const sb = $('sbody'); sy = sb.scrollTop <= 0 ? e.touches[0].clientY : null; }, { passive: true });
$('sheet').addEventListener('touchend', e => { if (sy != null && e.changedTouches[0].clientY - sy > 80) closeSheet(); sy = null; });

document.addEventListener('visibilitychange', () => {
  if (document.hidden) { wasPlaying = !V.paused; if (wasPlaying) V.pause(); return; }
  if (wasPlaying && hostId && !held) play();
  wasPlaying = false;
  if (shouldPoll()) refresh();
  if (Date.now() - lastIndexFetch > 180000) checkNewer();
});
window.addEventListener('hashchange', () => {
  const m = /^#(\d{4}-\d{2}-\d{2})(?:\/([\w-]+))?$/.exec(location.hash);
  if (!m) return;
  if (m[1] !== DATE) openDate(m[1], { storyId: m[2] });
  else if (m[2]) { const k = REELS.findIndex(r => r.s.id === m[2]); if (k >= 0 && k !== CUR) go(k); }
});

/* ================================================================ boot */
async function boot() {
  paintSound(); paintSpeed();
  lastIndexFetch = Date.now();
  INDEX = await getJSON(PATHS.index);
  const m = /^#(\d{4}-\d{2}-\d{2})(?:\/([\w-]+))?$/.exec(location.hash);
  const want = m && days().some(d => d.date === m[1]) ? m[1] : latestDate();
  if (!want) {
    feed.innerHTML = `<div class="boot"><span>No reels yet. The first ones arrive after tomorrow’s 6 AM run.</span></div>`;
    READY = true; return;
  }
  await openDate(want, { storyId: m && m[1] === want ? m[2] : null });
  const t = istNow(), l = latestDate();
  if (l && l < t.date && t.minutes >= LATE_AFTER_MIN && want === l) toast(`${icon('alert', 16)}<span>Today’s reels are running late · showing ${esc(dayLabel(l))}</span>`, 4500);
  READY = true;
}

window.Feed = {
  get ready() { return READY; },
  refresh, openDate, go,
  get speed() { return speed; },
  get sound() { return sound; },
  _video: V,
  state: () => ({ date: DATE, cur: CUR, n: REELS.length, hostId, sound, speed, held,
    sheet: $('sheet').hidden ? null : $('stitle').textContent,
    reels: REELS.map(r => ({ id: r.s.id, video: !!(r.v), chapters: arr(r.chap).map(c => [c.t, c.label]) })) }),
};

if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost')) {
  const had = !!navigator.serviceWorker.controller;
  navigator.serviceWorker.register('./sw.js', { updateViaCache: 'none' }).then(r => r.update()).catch(() => {});
  let reloaded = false;
  // A new version took over: reload once, but never while a reel is playing.
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (had && !reloaded && V.paused && $('sheet').hidden) { reloaded = true; location.reload(); }
  });
}

boot();
})();
