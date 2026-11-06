/* The Briefing — phone web app (plain JS, ES2020, no build step). player.js is loaded first.
 *
 * Data, relative to dashboard/reels/:
 *   ../briefing/index.json          {latest, days[{date, edition, status, stories, briefs, top_line}]}
 *   ../briefing/<date>.json         one edition (schema 1 — tests/fixtures/briefing/2026-11-03.json is the contract)
 *   ../briefing/videos/<date>.json  narrated reels (used only when reel_hash matches; see player.js)
 *   ../digest/index.json            the old Daily Digest, now a read-only archive at digest.html#<date>
 *
 * The deck is a vertical snap reel:
 *   cover → before you scroll → one card per big story → one card per section (a horizontal carousel of briefs)
 *   → quiet sections → also today → quiz → still developing → you're caught up.
 * Cards hold only fixed-size elements (clamped headline / question / dek). Nothing is shrunk or folded to fit:
 * a list too long for one screen continues on the next card (paginate), a long brief scrolls inside its card
 * (with a visible "More" hint), and depth lives in the full-screen explainer sheet (#<date>/<storyId>).
 *
 * Hash routes: #<date> · #<date>/<storyId> (opens the explainer) · #<date>/<sectionKey> · #<date>/<briefId>
 * Testing: ?now=2026-11-03T07:10 pins the clock (IST unless an offset is given); see tests/ui/.
 */
(() => {
'use strict';

/* ================================================================ constants */
const PATHS = {
  index: '../briefing/index.json',
  edition: d => `../briefing/${d}.json`,
  videos: d => `../briefing/videos/${d}.json`,
  archive: '../digest/index.json',
  archivePage: d => `digest.html#${d}`,
};
const PREFS_KEY = 'briefing_prefs';
const LATE_AFTER_MIN = 6 * 60 + 45;     // "running late" banner after 06:45 IST

// Lucide-style line icons (24×24 viewBox, stroke = currentColor)
const IC = {
  top: '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
  world: '<circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
  india: '<path d="M3 22h18"/><path d="M6 18v-7M10 18v-7M14 18v-7M18 18v-7"/><path d="M12 2 20 7H4z"/>',
  affects_you: '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>',
  markets: '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
  tech_ai: '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M15 2v2M15 20v2M2 15h2M2 9h2M20 15h2M20 9h2M9 2v2M9 20v2"/>',
  science: '<path d="M10 2v7.31"/><path d="M14 9.3V2"/><path d="M8.5 2h7"/><path d="M14 9.3a6.5 6.5 0 1 1-4 0"/><path d="M5.52 16h12.96"/>',
  f1: '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><path d="M4 22v-7"/>',
  cricket: '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
  star: '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  learn: '<path d="M21.42 10.92a1 1 0 0 0-.02-1.84L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.83l8.57 3.91a2 2 0 0 0 1.66 0z"/><path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/>',
  help: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
  zap: '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>',
  activity: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
  moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
  layers: '<path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/><path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>',
  eye: '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
  clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
  arrow: '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
  chev: '<path d="m9 18 6-6-6-6"/>', left: '<path d="m15 18-6-6 6-6"/>', up: '<path d="m18 15-6-6-6 6"/>', down: '<path d="m6 9 6 6 6-6"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  cal: '<rect x="3" y="4" width="18" height="18" rx="3"/><path d="M16 2v4M8 2v4M3 10h18"/>',
  play: '<polygon points="6 3 20 12 6 21 6 3"/>',
  replay: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
  vol: '<path d="M11 4.7a.7.7 0 0 0-1.2-.5L6.4 7.6A1.4 1.4 0 0 1 5.4 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.4a1.4 1.4 0 0 1 1 .4l3.4 3.4a.7.7 0 0 0 1.2-.5z"/><path d="M16 9a5 5 0 0 1 0 6"/><path d="M19.4 18.4a9 9 0 0 0 0-12.8"/>',
  mute: '<path d="M11 4.7a.7.7 0 0 0-1.2-.5L6.4 7.6A1.4 1.4 0 0 1 5.4 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.4a1.4 1.4 0 0 1 1 .4l3.4 3.4a.7.7 0 0 0 1.2-.5z"/><path d="m22 9-6 6"/><path d="m16 9 6 6"/>',
  book: '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
  ext: '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
  alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  shield: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
  history: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
  news: '<path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/><path d="M18 14h-8"/><path d="M15 18h-5"/><path d="M10 6h8v4h-8V6Z"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  hash: '<path d="M4 9h16M4 15h16M10 3 8 21M16 3l-2 18"/>',
  bulb: '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>',
  scale: '<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>',
  user: '<circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 0 0-16 0"/>',
  xc: '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6M9 9l6 6"/>',
  cc: '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
  calnext: '<path d="M21 7.5V6a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h3.5"/><path d="M16 2v4M8 2v4M3 10h5"/><path d="M17.5 17.5 16 16.3V14"/><circle cx="16" cy="16" r="6"/>',
  film: '<rect x="2" y="2" width="20" height="20" rx="2.18"/><path d="M7 2v20M17 2v20M2 12h20M2 7h5M2 17h5M17 17h5M17 7h5"/>',
  quote: '<path d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V20c0 1 0 1 1 1z"/><path d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2h.75c0 2.25.25 4-2.75 4v3c0 1 0 1 1 1z"/>',
};
IC.also = IC.zap; IC.quiz = IC.help; IC.dev = IC.activity; IC.quiet = IC.moon; IC.next = IC.check; IC.stories = IC.star;

// Section display names (the edition's own `title` wins where present; `short` is for chips and tabs)
const SEC = {
  top: { label: 'Top', short: 'Top', emoji: '⭐' },
  world: { label: 'World', short: 'World', emoji: '🌍' },
  india: { label: 'India', short: 'India', emoji: '🇮🇳' },
  affects_you: { label: 'Your money & life', short: 'Money & life', emoji: '🧾' },
  markets: { label: 'Markets & money', short: 'Markets', emoji: '📈' },
  tech_ai: { label: 'Tech & AI', short: 'Tech & AI', emoji: '🤖' },
  science: { label: 'Science, health & climate', short: 'Science', emoji: '🔬' },
  f1: { label: 'Formula 1', short: 'F1', emoji: '🏎️' },
  cricket: { label: 'Cricket', short: 'Cricket', emoji: '🏏' },
};
const THREAD = { new: 'New', developing: 'Developing', escalating: 'Escalating', cooling: 'Cooling', ongoing: 'Ongoing', update: 'Update', resolved: 'Resolved' };
const BRIEF_ST = { new: 'New', update: 'Update', developing: 'Developing', resolved: 'Resolved' };
const TODAY_ST = { update: 'Updated', no_change: 'No change', resolved: 'Resolved' };
const SRC_TYPE = { primary: 'Primary', wire: 'Wire', outlet: 'Outlet', analysis: 'Analysis' };
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const MONL = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const WD = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const WDL = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

/* ================================================================ small helpers */
const $ = id => document.getElementById(id);
const deck = $('deck');
const esc = s => (s == null ? '' : String(s)).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const rich = s => esc(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');              // only **bold** survives escaping
const safeUrl = u => (typeof u === 'string' && /^https?:\/\/[^\s]+$/i.test(u.trim())) ? u.trim() : null;
const arr = v => Array.isArray(v) ? v : (v == null ? [] : [v]);
const cap = s => s ? s.charAt(0).toUpperCase() + s.slice(1) : '';
const plural = (n, w, pl) => `${n} ${n === 1 ? w : (pl || w + 's')}`;
const icon = (k, sz = 18, cls = '') => `<svg class="i ${cls}" width="${sz}" height="${sz}" viewBox="0 0 24 24" aria-hidden="true">${IC[k] || ''}</svg>`;
/** Section keys go into CSS variable names, so only known keys are allowed. */
const sk = k => (SEC[k] && k !== 'top') ? k : 'top';
const sec = k => SEC[sk(k)];
const vars = k => `--a:var(--${k}-a);--b:var(--${k}-b);--c:var(--${k}-c)`;
const words = (...t) => t.filter(Boolean).join(' ').split(/\s+/).filter(Boolean).length;
const raf2 = fn => requestAnimationFrame(() => requestAnimationFrame(fn));

/* ---------------------------------------------------------------- time (everything is shown in IST) */
/** Parse "YYYY-MM-DD", "YYYY-MM-DDTHH:MM[:SS][Z|±HH:MM]" → epoch ms. No offset = IST (the pipeline writes IST). */
function parseTime(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?)?\s*(Z|[+-]\d{2}:?\d{2})?$/.exec(String(s || '').trim());
  if (!m) return NaN;
  let off = 330;
  if (m[7]) off = m[7] === 'Z' ? 0 : (m[7][0] === '-' ? -1 : 1) * (+m[7].slice(1, 3) * 60 + +m[7].slice(-2));
  return Date.UTC(+m[1], +m[2] - 1, +m[3], +(m[4] || 0), +(m[5] || 0), +(m[6] || 0)) - off * 60000;
}
// ?now=… (or localStorage briefing_now) pins the clock; it keeps ticking from that moment.
const NOW_SKEW = (() => {
  let s = null;
  try { s = new URLSearchParams(location.search).get('now') || localStorage.getItem('briefing_now'); } catch (e) { /* private mode */ }
  const t = s ? parseTime(s) : NaN;
  return isNaN(t) ? 0 : t - Date.now();
})();
const now = () => Date.now() + NOW_SKEW;
function ist(t) {
  const d = new Date(t + 330 * 60000);
  return { y: d.getUTCFullYear(), mo: d.getUTCMonth(), d: d.getUTCDate(), h: d.getUTCHours(), mi: d.getUTCMinutes(), wd: d.getUTCDay(), date: d.toISOString().slice(0, 10) };
}
const istNow = () => { const p = ist(now()); return { date: p.date, minutes: p.h * 60 + p.mi, h: p.h }; };
const clock = (h, mi) => `${h % 12 || 12}:${String(mi).padStart(2, '0')} ${h < 12 ? 'AM' : 'PM'}`;
/** "2026-11-02T21:00+05:30" → "2 Nov, 9:00 PM" (IST) */
function stamp(s) { const t = parseTime(s); if (isNaN(t)) return ''; const p = ist(t); return `${p.d} ${MON[p.mo]}, ${clock(p.h, p.mi)}`; }
/** "02:30" (IST wall time) → "2:30 AM" */
function hm(s) { const m = /^(\d{1,2}):(\d{2})/.exec(String(s || '')); return m ? clock(+m[1], +m[2]) : ''; }
function dparts(date) { const [y, m, d] = String(date).split('-').map(Number); return { y, mo: m - 1, d, wd: new Date(Date.UTC(y, m - 1, d)).getUTCDay() }; }
function fmtDay(date, style) {
  const p = dparts(date);
  if (isNaN(p.d)) return '';
  if (style === 'long') return `${WDL[p.wd]}, ${p.d} ${MONL[p.mo]}`;
  return `${WD[p.wd]} ${p.d} ${MON[p.mo]}`;
}
const dayDiff = (a, b) => Math.round((parseTime(b) - parseTime(a)) / 864e5);
const isoOf = (y, mo, d) => `${y}-${String(mo + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;

/* ---------------------------------------------------------------- fetch, prefs, toast */
/** Fetch JSON fresh (cache-busting query defeats the CDN cache; the service worker strips it for its own cache key). */
async function getJSON(url) {
  try {
    const r = await fetch(`${url}${url.includes('?') ? '&' : '?'}_=${Date.now()}`, { cache: 'no-store' });
    return r.ok ? await r.json() : null;
  } catch (e) { return null; }
}
function prefs() {
  try { return JSON.parse(localStorage.getItem(PREFS_KEY) || localStorage.getItem('digest_prefs')) || {}; } catch (e) { return {}; }
}
function savePrefs(p) { try { localStorage.setItem(PREFS_KEY, JSON.stringify(p)); } catch (e) { /* private mode */ } }
function toast(msg, ms) {
  const t = $('toast'); t.textContent = msg; t.classList.add('show');
  clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove('show'), ms || 2800);
}

/* ================================================================ state */
let INDEX = null, ARCHIVE = null, DOC = null, DATE = null;
let CUR = null;                 // data-id of the slot on screen
let EX = null, EX_PUSHED = false, EX_RETURN = null;
let LATE_DISMISSED = false;
let READY = false;
const LISTS = new Map();        // list-card id -> spec (so paginate() can re-render pages)
const PENDING = new Set();      // story ids (or 'cover') to re-render once they're off screen
let SRC_NS = new Set();         // source numbers of the story open in the explainer

const days = () => ((INDEX && INDEX.days) || []).slice().sort((a, b) => (a.date < b.date ? 1 : -1));
const latestDate = () => { const ds = days(); const l = INDEX && INDEX.latest; return (l && ds.some(d => d.date === l)) ? l : (ds[0] && ds[0].date) || null; };
const stories = () => (DOC && DOC.stories) || [];
const storyById = id => stories().find(s => s.id === id) || null;
function briefById(id) {
  for (const s of (DOC && DOC.sections) || []) for (const it of s.items || []) if (it.id === id) return { sec: s, it };
  return null;
}
const slotById = id => deck.querySelector(`.slot[data-id="${CSS.escape(id)}"]`);
/** Which section a reference ("s1", "b-cricket-1", …) belongs to. */
function refSection(ref) {
  const s = storyById(ref); if (s) return s.section;
  const b = briefById(ref); if (b) return b.sec.key;
  return null;
}

/** Make the edition safe to render even if optional parts are missing. */
function normalize(d) {
  d.cover = d.cover || {};
  d.stories = arr(d.stories).filter(s => s && s.id);
  d.sections = arr(d.sections).filter(s => s && s.key).map(s => ({ ...s, items: arr(s.items).filter(Boolean) }));
  d.also = arr(d.also).filter(x => x && x.text);
  d.quiz = arr(d.quiz).filter(q => q && q.q && arr(q.options).length);
  d.developing = arr(d.developing).filter(x => x && x.title);
  d.notes = arr(d.notes);
  return d;
}

/* ================================================================ boot + routing */
function parseHash() {
  const [date, sub] = decodeURIComponent((location.hash || '').replace(/^#/, '')).split('/');
  return { date: /^\d{4}-\d{2}-\d{2}$/.test(date || '') ? date : null, sub: sub || null };
}

async function boot() {
  applyTheme(prefs().theme);
  Player.init({
    getJSON, videosUrl: PATHS.videos, istNow, toast, sectionKey: sk,
    chipHTML: s => `${icon(sk(s.section), 15)}${esc(sec(s.section).short)}`,
    openExplainer: id => openExplainer(id),
    onVideosChanged: ids => { ids.forEach(id => PENDING.add(id)); PENDING.add('cover'); flushPending(); },
    onVideoFailed: id => rerenderStory(id),
  });
  const { date, sub } = parseHash();
  INDEX = await getJSON(PATHS.index);
  // An old Daily Digest link (#<date>/<section>) that predates the briefing → send it to the archive page.
  if (date && !days().some(d => d.date === date)) {
    ARCHIVE = ARCHIVE || await getJSON(PATHS.archive);
    if (ARCHIVE && arr(ARCHIVE.days).some(d => d.date === date)) { location.replace(PATHS.archivePage(date) + (sub ? '/' + sub : '')); return; }
  }
  if (!days().length) { renderEmpty(); return; }
  await openEdition(date && days().some(d => d.date === date) ? date : latestDate(), { sub });
  paintLate();
}

function renderEmpty() {
  $('sub').textContent = 'No editions yet';
  deck.innerHTML = `<div class="empty">${icon('news', 34)}<div>The first Morning Briefing lands around <b>5:40 AM IST</b>.</div>
    <a class="btn" href="digest.html" style="${vars('top')}">Read the old Daily Digest</a></div>`;
  READY = true;
}

/** Load and render one edition. opts.sub = the part of the hash after the date. */
async function openEdition(date, opts = {}) {
  $('sub').textContent = 'Loading…';
  const [doc, vids] = await Promise.all([getJSON(PATHS.edition(date)), getJSON(PATHS.videos(date))]);
  if (!doc) {
    if (!DOC) {
      deck.innerHTML = `<div class="empty">${icon('alert', 30)}<div>Couldn’t load the briefing for ${esc(fmtDay(date, 'long'))}.</div>
        <button class="btn" data-act="retry" data-date="${esc(date)}" style="${vars('top')}">Try again</button></div>`;
      $('sub').textContent = 'Offline?';
      READY = true;
    } else { toast('Couldn’t load that day. Check your connection.'); paintHeader(); }
    return false;
  }
  if (EX) closeExplainer({ silent: true });
  DOC = normalize(doc); DATE = date;
  Player.load(date, DOC.stories, vids);
  render();
  const sub = opts.sub;
  if (sub && storyById(sub)) openExplainer(sub, { fromHash: true });   // the overlay doesn't need layout
  await afterLayout();
  if (sub) routeSub(sub);
  else if (!EX) saveHash();
  return true;
}

/** Jump the deck to what the hash names (after layout, because pagination can add slots). */
function routeSub(sub) {
  if (storyById(sub)) { goSlot(sub, false); return; }
  if (briefById(sub)) { jump(sub, { smooth: false }); return; }
  if (SEC[sub] && slotById('sec-' + sub)) { goSlot('sec-' + sub, false); return; }
  if (slotById(sub)) goSlot(sub, false);
}

/** Back/forward and hand-edited hashes. Idempotent: replaceState-driven hashes never get here. */
async function onRoute() {
  const { date, sub } = parseHash();
  if (date && date !== DATE && days().some(d => d.date === date)) { await openEdition(date, { sub }); return; }
  if (sub && storyById(sub)) { if (EX !== sub) openExplainer(sub, { fromHash: true }); return; }
  if (EX) closeExplainer({ fromPop: true });
  if (sub && !EX) {
    const target = SEC[sub] ? 'sec-' + sub : sub;
    const cur = slotById(CUR || '');
    if (!(cur && (cur.dataset.id === target || cur.dataset.tab === sub))) routeSub(sub);
  }
}
window.addEventListener('popstate', onRoute);
window.addEventListener('hashchange', onRoute);

function saveHash() {
  if (EX || !DATE) return;
  const slot = slotById(CUR || '');
  const tab = slot && slot.dataset.tab;
  const h = '#' + DATE + (tab && SEC[tab] && tab !== 'top' ? '/' + tab : '');
  if (location.hash !== h) try { history.replaceState(null, '', h); } catch (e) { /* file:// etc. */ }
}

/* ================================================================ render the deck */
function render() {
  LISTS.clear(); PENDING.clear();
  const cards = [];
  const d = DOC, c = d.cover;
  cards.push({ id: 'cover', tab: 'today', label: 'Cover', html: coverHTML() });
  if (arr(c.changes).length) cards.push(listCard('changes', 'today', changesSpec(arr(c.changes))));
  d.stories.forEach((s, i) => cards.push({ id: s.id, tab: 'stories', story: s.id, label: s.headline, html: storyHTML(s, i, d.stories.length) }));
  const loud = d.sections.filter(s => !s.quiet && s.items.length);
  const quiet = d.sections.filter(s => s.quiet || !s.items.length);
  loud.forEach(s => cards.push({ id: 'sec-' + s.key, tab: sk(s.key), car: true, label: s.title, html: sectionHTML(s) }));
  if (quiet.length) cards.push(listCard('quiet', 'wrap', quietSpec(quiet)));
  if (d.also.length) cards.push(listCard('also', 'wrap', alsoSpec(d.also)));
  if (d.quiz.length) cards.push({ id: 'quiz', tab: 'wrap', car: true, label: 'Quiz', html: quizHTML(d.quiz) });
  if (d.developing.length) cards.push(listCard('developing', 'wrap', devSpec(d.developing)));
  const lessons = d.stories.filter(s => s.blocks && s.blocks.lesson && s.blocks.lesson.concept);
  if (lessons.length) cards.push(listCard('learned', 'wrap', learnedSpec(lessons)));
  cards.push({ id: 'end', tab: 'wrap', label: 'You’re caught up', html: endHTML() });

  deck.innerHTML = cards.map(slotHTML).join('');
  deck.scrollTop = 0;
  CUR = 'cover';
  paintHeader(); paintTabs(); paintTab('today'); paintProgress();
  observe();
  Player.bind(deck);
}
function slotHTML(c) {
  return `<section class="slot${c.car ? ' car' : ''}" data-id="${esc(c.id)}" data-tab="${esc(c.tab)}"${c.story ? ` data-story="${esc(c.story)}"` : ''}${c.list ? ` data-list="${esc(c.list)}"` : ''} aria-label="${esc(c.label || '')}">${c.html}</section>`;
}

/* ---------------------------------------------------------------- cover */
function greeting() {
  const h = istNow().h;
  return h < 4 ? 'Up late?' : h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
}
function coverHTML() {
  const d = DOC, c = d.cover, isToday = DATE === istNow().date;
  const diff = dayDiff(DATE, istNow().date);
  const greet = isToday ? greeting() : diff === 1 ? 'Yesterday’s edition' : 'From the archive';
  const reels = Player.list(), reelMin = Math.max(1, Math.round(Player.seconds() / 60));
  const meta = [`≈${c.read_min || '30'} min read`];
  if (reels.length) meta.push(`${reelMin} min of reels`);
  return `<article class="card cover fit" style="${vars('top')}">
    <div class="cv-hero">
      <div class="cv-greet">${icon('sun', 15)}${esc(greet)}<span class="ed">${esc(d.edition || '')}</span></div>
      <h1 class="cv-date">${esc(fmtDay(DATE, 'long'))}</h1>
      <div class="cv-meta"><span class="pill">${icon('clock', 13)}${esc(meta.join(' · '))}</span></div>
      ${c.top_line ? `<p class="cv-top">${rich(c.top_line)}</p>` : ''}
    </div>
    ${statusHTML()}
    ${reels.length ? `<button class="cv-play press" data-act="playall"><span class="pi">${icon('play', 20, 'fill')}</span>
      <span><b>Play all</b><small>${plural(reels.length, 'reel')} · about ${plural(reelMin, 'minute')}</small></span>${icon('arrow', 18, 'go')}</button>` : ''}
    ${arr(c.watch_today).length ? `<div class="cv-sec"><div class="kick">${icon('eye')}Watch today</div>
      <ul class="cv-watch">${arr(c.watch_today).slice(0, 3).map(w => `<li><span class="tm">${w.time_ist ? esc(hm(w.time_ist)) : 'Today'}</span><span>${esc(w.text)}</span></li>`).join('')}</ul></div>` : ''}
    ${marketsHTML()}
    <div class="cv-foot">${icon('up')}Swipe up to begin</div>
  </article>`;
}
function statusHTML() {
  const st = DOC.status;
  if (st !== 'partial' && st !== 'lite') return '';
  const lead = st === 'partial' ? 'Some stories didn’t pass our checks in time, so today’s edition is shorter.' : 'A shorter edition today.';
  const notes = DOC.notes.filter(Boolean);
  return `<div class="cv-status" role="note">${icon('alert', 18)}<div><b>${st === 'partial' ? 'Partial edition.' : 'Lite edition.'}</b> ${esc(lead)}
    ${notes.length ? `<ul>${notes.map(n => `<li>${esc(n)}</li>`).join('')}</ul>` : ''}</div></div>`;
}
function marketsHTML() {
  const m = DOC.markets, q = m && arr(m.quotes).filter(x => x && x.name && typeof x.last === 'number');
  if (!q || !q.length) return '';
  const asOf = m.as_of ? stamp(m.as_of) : '';
  return `<div class="cv-sec"><div class="kick">${icon('markets')}Markets${asOf ? `<small>· as of ${esc(asOf)}</small>` : ''}</div>
    <div class="cv-mk" data-scroll="x">${q.map(x => {
      const ch = typeof x.chg_pct === 'number' ? x.chg_pct : null;
      const dir = ch == null || ch === 0 ? 'flat' : ch > 0 ? 'up' : 'dn';
      const arrow = dir === 'up' ? '▲' : dir === 'dn' ? '▼' : '•';
      return `<div class="mq ${dir}"><span class="nm">${esc(x.name)}</span><b>${esc(x.last.toLocaleString('en-IN', { maximumFractionDigits: 2 }))}</b>
        <span class="ch">${arrow} ${ch == null ? '—' : esc(Math.abs(ch).toFixed(2)) + '%'}</span></div>`;
    }).join('')}</div></div>`;
}

/* ---------------------------------------------------------------- list cards (paginated, never shrunk) */
/** A list card spec: {cls, style, head(page,pages), items:[li html], foot}. Registered so paginate() can split it. */
function listCard(id, tab, spec) {
  LISTS.set(id, { ...spec, id, tab });
  return { id, tab, list: id, label: spec.label, html: listArticle(LISTS.get(id), spec.items, '') };
}
function listArticle(spec, items, pg) {
  return `<article class="card lc fit ${spec.cls || ''}" style="${spec.style || ''}">${spec.head(pg)}<ul class="plist">${items.join('')}</ul>${spec.foot || ''}</article>`;
}
const pgTag = pg => `<span class="lc-pg">${esc(pg)}</span>`;
const lcHead = (k, ic, kick, title, sub) => pg => `<div class="lc-head"><div class="lc-ic grad" style="${vars(k)}">${icon(ic, 22)}</div>
  <div class="kick">${esc(kick)}${pgTag(pg)}</div><h2 class="h2">${esc(title)}</h2>${sub ? `<p>${esc(sub)}</p>` : ''}</div>`;

function refRow(ref, inner) {
  const ok = ref && (storyById(ref) || briefById(ref));
  return ok ? `<button class="row press" data-act="jump" data-ref="${esc(ref)}">${inner}${icon('chev', 16, 'chev')}</button>` : `<div class="row">${inner}</div>`;
}
function changesSpec(list) {
  return {
    label: 'Before you scroll', cls: 'changes', style: vars('top'),
    head: lcHead('top', 'layers', 'Before you scroll', 'What changed since yesterday', `${plural(list.length, 'update')} · tap one to jump to it`),
    items: list.map(ch => {
      const k = sk(refSection(ch.ref));
      return `<li>${refRow(ch.ref, `<span class="sq grad" style="${vars(k)}">${icon(k, 18)}</span><span class="t">${esc(ch.text)}</span>`)}</li>`;
    }),
  };
}
function quietSpec(list) {
  const t = list.length === 1 ? `Quiet day for ${sec(list[0].key).short}` : `${plural(list.length, 'section')} had a quiet day`;
  return {
    label: 'Quiet today', cls: 'quiet', style: vars('quiet'),
    head: lcHead('quiet', 'moon', 'Quiet today', t, 'We checked. Nothing big enough to brief you on.'),
    items: list.map(s => `<li><div class="row"><span class="sq grad" style="${vars(sk(s.key))}">${esc(s.emoji || sec(s.key).emoji)}</span>
      <span class="t">${esc(s.title || sec(s.key).label)}<span>Quiet today${s.quiet_note ? ' — ' + esc(s.quiet_note) : ''}</span></span></div></li>`),
  };
}
function alsoSpec(list) {
  return {
    label: 'Also today', cls: 'also', style: vars('also'),
    head: lcHead('also', 'zap', `Also today · ${list.length}`, 'In one line', ''),
    items: list.map(x => {
      const k = sk(x.section), src = x.source || {}, url = safeUrl(src.url), when = stamp(src.published);
      const inner = `<span class="dot" style="${vars(k)}">${esc(sec(k).emoji)}</span><span class="t">${esc(x.text)}
        <small>${esc(src.pub || '')}${when ? ' · ' + esc(when) : ''}</small></span>`;
      return `<li>${url ? `<a class="row press" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${inner}${icon('ext', 15, 'ext')}</a>` : `<div class="row">${inner}</div>`}</li>`;
    }),
  };
}
function devSpec(list) {
  return {
    label: 'Still developing', cls: 'dv', style: vars('dev'),
    head: lcHead('dev', 'activity', 'Still developing', 'Stories we’re following', 'How long each has run, and what happened today'),
    items: list.map(t => {
      const st = TODAY_ST[t.today] ? t.today : 'no_change';
      const inner = `<span class="day grad" style="${vars('dev')}"><small>Day</small><b>${esc(t.day || 1)}</b></span>
        <span class="t"><span class="tt"><b>${esc(t.title)}</b><span class="today ${st}">${TODAY_ST[st]}</span></span>${t.line ? `<span class="ln">${esc(t.line)}</span>` : ''}</span>`;
      return `<li>${refRow(t.ref, inner)}</li>`;
    }),
  };
}

/* ---------------------------------------------------------------- story cards */
function threadBadge(t) {
  if (!t || !(t.day > 1)) return '';
  const st = THREAD[t.status] || cap(t.status || '');
  return `<span class="badge${t.status === 'escalating' ? ' esc' : ''}">${t.status === 'developing' || t.status === 'escalating' ? '<i class="pulse"></i>' : ''}Day ${esc(t.day)}${st ? ' · ' + esc(st) : ''}</span>`;
}
function storyBadges(s) {
  const b = threadBadge(s.thread) + (s.must_read ? `<span class="badge must">${icon('star', 12, 'fill')}Don’t miss</span>` : '');
  return b ? `<div class="badges">${b}</div>` : '';
}
function storyHTML(s, i, n) {
  const k = sk(s.section), v = Player.info(s.id), id = esc(s.id);
  return `<article class="card story${v ? ' has-video' : ''}" data-story="${id}" style="${vars(k)}">
    <div class="st-media"><div class="st-hero"><div class="big">${icon(k, 24)}</div></div>${v && v.poster ? `<img class="st-poster" src="${esc(v.poster)}" alt="" decoding="async">` : ''}</div>
    <div class="st-scrim"></div>
    <div class="st-top"><span class="chip">${icon(k, 15)}${esc(sec(k).short)}</span><span class="st-n">${i + 1} / ${n}</span></div>
    <div class="st-tap"${v ? ' data-act="vtoggle" aria-hidden="true"' : ''}></div>
    ${v ? `<button class="st-play" data-act="vplay" aria-label="Play the reel">${icon('play', 32, 'fill pl')}${icon('replay', 30, 'rp')}</button><div class="st-spin"></div>` : ''}
    <div class="st-body">
      ${storyBadges(s)}
      <div class="st-text" data-act="explain" data-story="${id}">
        <h2 class="st-h clamp">${esc(s.headline)}</h2>
        ${s.question ? `<p class="st-q clamp">${esc(s.question)}</p>` : ''}
        ${s.blocks && s.blocks.lesson && s.blocks.lesson.concept ? `<p class="st-learn">${icon('learn', 15)}<span>Learn: ${esc(s.blocks.lesson.concept)}</span></p>` : ''}
        ${!v && s.dek ? `<p class="st-d clamp">${esc(s.dek)}</p>` : ''}
      </div>
      <div class="st-act">
        ${v ? `<button class="vbtn" data-act="vsound" aria-pressed="${Player.sound}" aria-label="${Player.sound ? 'Turn sound off' : 'Turn sound on'}">${icon('vol', 20, 'on')}${icon('mute', 20, 'off')}</button>
        <button class="vbtn vspd${Player.speed !== 1 ? ' fast' : ''}" data-act="vspeed" aria-label="Playback speed ${Player.speed}×. Tap to change">${Player.speed}×</button>` : ''}
        <button class="read press" data-act="explain" data-story="${id}">${icon('book', 18)}<span>Explainer<span class="rmin"> · ${esc(s.read_min || 4)} min</span></span></button>
      </div>
    </div>
    ${v ? '<div class="st-prog"><i></i></div>' : ''}
  </article>`;
}
/** Re-render one story card in place (a reel arrived or failed). Never call it for the card being read. */
function rerenderStory(id) {
  const s = storyById(id), slot = slotById(id);
  if (!s || !slot) return;
  const old = slot.querySelector('.card.story');
  if (old) Player.detach(old);
  slot.innerHTML = storyHTML(s, stories().indexOf(s), stories().length);
  Player.bind(deck);
}
/** Apply deferred updates (new reels) to everything that isn't on screen right now. */
function flushPending() {
  for (const id of [...PENDING]) {
    if (id === CUR) continue;
    PENDING.delete(id);
    if (id === 'cover') {
      const slot = slotById('cover');
      if (slot) { slot.innerHTML = coverHTML(); hints(); }
    } else rerenderStory(id);
  }
}

/* ---------------------------------------------------------------- section carousels */
function sectionHTML(s) {
  const k = sk(s.key), items = s.items;
  const mins = Math.max(1, Math.round(items.reduce((n, it) => n + words(it.headline, it.text, it.background, it.why), 0) / 200));
  const intro = `<article class="card slide intro grad fit" style="${vars(k)}" data-slide="0">
      <div class="wmk">${icon(k, 24)}</div>
      <div class="emo" aria-hidden="true">${esc(s.emoji || sec(k).emoji)}</div>
      <div class="kick">${plural(items.length, 'brief')} · ${mins} min read</div>
      <h2 class="h2">${esc(s.title || sec(k).label)}</h2>
      ${s.gist ? `<p class="in-gist">${rich(s.gist)}</p>` : ''}
      <ol class="toc">${items.map((it, j) => `<li><button data-act="slide" data-to="${j + 1}"><span class="n">${j + 1}</span><span class="t clamp">${esc(it.headline)}</span>${icon('chev', 16)}</button></li>`).join('')}</ol>
      <div class="swipe">Swipe for the briefs ${icon('arrow', 16)}</div>
    </article>`;
  return `<div class="hcar" data-scroll="x">${intro}${items.map((it, j) => briefHTML(k, it, j, items.length)).join('')}</div>`;
}
function srcChips(list) {
  const a = arr(list).filter(Boolean).map(x => {
    const url = safeUrl(x.url), when = stamp(x.published);
    const inner = `<b>${esc(x.pub || 'Source')}</b>${when ? `<span>${esc(when)}</span>` : ''}${url ? icon('ext', 12) : ''}`;
    return url ? `<a class="src-a" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${inner}</a>` : `<span class="src-a">${inner}</span>`;
  });
  return a.length ? `<div class="br-src">${a.join('')}</div>` : '';
}
function briefHTML(k, it, j, n) {
  const st = BRIEF_ST[it.status] ? it.status : null;
  const day = it.thread && it.thread.day > 1 ? ` · Day ${esc(it.thread.day)}` : '';
  return `<article class="card slide brief" style="${vars(k)}" data-brief="${esc(it.id)}" data-slide="${j + 1}">
    <div class="br-in">
      <div class="br-top"><span class="br-sec">${icon(k, 14)}${esc(sec(k).short)}</span>${st ? `<span class="st ${st}">${BRIEF_ST[st]}${day}</span>` : ''}<span class="br-n">${j + 1} / ${n}</span></div>
      <h3 class="br-h">${esc(it.headline)}</h3>
      ${it.text ? `<p class="br-t">${rich(it.text)}</p>` : ''}
      ${it.background ? `<p class="br-bg"><span class="lab">Background</span>${rich(it.background)}</p>` : ''}
      ${it.why ? `<p class="br-why"><span class="lab">Why it matters</span>${rich(it.why)}</p>` : ''}
      ${srcChips(it.sources)}
    </div>
    <div class="more"><span>${icon('down', 13)}More</span></div>
  </article>`;
}

/* ---------------------------------------------------------------- quiz (one question per slide; nothing is saved) */
function learnedSpec(list) {
  return {
    label: 'What you learned today', cls: 'learned', style: vars('quiz'),
    head: lcHead('quiz', 'learn', 'What you learned today', `${plural(list.length, 'idea')} to keep`, 'Tap one to go back over its lesson'),
    items: list.map(s => {
      const k = sk(s.section), ls = s.blocks.lesson, line = arr(s.takeaways)[0] || ls.big_idea || '';
      return `<li><button class="row press" data-act="learn" data-story="${esc(s.id)}"><span class="sq grad" style="${vars(k)}">${icon('learn', 18)}</span>
        <span class="t">${esc(ls.concept)}${line ? `<span>${esc(line)}</span>` : ''}</span>${icon('chev', 16, 'chev')}</button></li>`;
    }),
  };
}

function optsHTML(q) {
  const ans = Number.isInteger(q.answer) ? q.answer : -1;
  return `<div class="opts" role="group">${arr(q.options).map((o, j) => `<button class="opt" data-act="answer" data-j="${j}" data-a="${ans}">
    <span class="k">${'ABCDEF'[j] || j + 1}</span><span>${esc(o)}</span>${icon('check', 18, 'mk y')}${icon('x', 18, 'mk n')}</button>`).join('')}</div>
    <div class="why" role="status"><b>${ans >= 0 ? 'Answer: ' + esc('ABCDEF'[ans] || '') + '. ' : ''}</b>${esc(q.why || '')}</div>`;
}
function quizHTML(list) {
  const n = list.length;
  return `<div class="hcar" data-scroll="x">${list.map((q, i) => {
    const s = q.story && storyById(q.story);
    return `<article class="card slide qz fit" style="${vars('quiz')}" data-slide="${i}">
      <div class="qz-top"><span class="sq grad">${icon('help', 18)}</span><div><b>Quick quiz</b><small>Question ${i + 1} of ${n}</small></div>
        <div class="qz-steps" aria-hidden="true">${list.map((_, j) => `<i class="${j === i ? 'on' : ''}"></i>`).join('')}</div></div>
      <p class="qz-q">${esc(q.q)}</p>
      ${optsHTML(q)}
      <div class="qz-next">${s ? `<button class="link" data-act="explain" data-story="${esc(s.id)}">${icon('book', 15)}Explainer</button>` : '<span class="hint">No scores kept</span>'}
        ${i < n - 1 ? `<button class="link" data-act="slide" data-to="${i + 1}">Next question ${icon('arrow', 15)}</button>` : `<button class="link" data-act="next-card">Keep going ${icon('down', 15)}</button>`}</div>
    </article>`;
  }).join('')}</div>`;
}
function answer(btn) {
  const box = btn.closest('.qz, .check');
  if (!box || box.classList.contains('answered')) return;
  const j = +btn.dataset.j, a = +btn.dataset.a;
  box.classList.add('answered');
  box.querySelectorAll('.opt').forEach(o => {
    const k = +o.dataset.j;
    if (k === a) o.classList.add('right');
    else if (k === j) o.classList.add('wrong');
    o.setAttribute('aria-disabled', 'true');
  });
  const why = box.querySelector('.why b');
  if (why) why.textContent = (j === a ? 'Correct! ' : 'Not quite. ') + why.textContent;
  hints();
}

/* ---------------------------------------------------------------- caught up */
function endHTML() {
  const c = DOC.cover, week = [], seen = new Set();
  arr(c.watch_today).forEach(w => week.push({ d: 'Today', time: w.time_ist ? hm(w.time_ist) : '', t: w.text || '' }));
  // Dated "what's next" items from the big stories that fall within the coming week (deduplicated)
  stories().forEach(s => arr(s.blocks && s.blocks.next && s.blocks.next.dates).forEach(x => {
    const dd = x && x.date ? dayDiff(DATE, x.date) : NaN, key = x && (x.date + '|' + String(x.what || '').toLowerCase());
    if (dd >= 1 && dd <= 7 && !seen.has(key)) { const p = dparts(x.date); seen.add(key); week.push({ d: `${WD[p.wd]} ${p.d}`, t: x.what || '', sort: x.date }); }
  }));
  week.sort((a, b) => (a.sort || '') < (b.sort || '') ? -1 : 1);
  // Keep the end card to one screen: at most 2 'today' rows, 4 rows in all (soonest first)
  week.splice(0, week.length, ...week.filter(w => w.d === 'Today').slice(0, 2), ...week.filter(w => w.d !== 'Today').slice(0, 2));
  const isToday = DATE === istNow().date;
  return `<article class="card end fit" style="${vars('next')}">
    <div class="done grad">${icon('check', 32)}</div>
    <h2 class="h2">You’re caught up</h2>
    <p class="end-sub">That’s the whole briefing for ${esc(fmtDay(DATE, 'long'))}.${isToday ? ' The next one lands around 5:40 AM.' : ''}</p>
    ${week.length ? `<div class="kick" style="margin-top:18px">${icon('cal')}This week</div>
      <ul class="wk">${week.map((w, i) => { const same = i && week[i - 1].d === w.d;
        return `<li${same ? ' class="cont"' : ''}><span class="d">${same ? '' : esc(w.d)}</span><span class="t">${w.time ? `<b>${esc(w.time)}</b>` : ''}${esc(w.t)}</span></li>`; }).join('')}</ul>` : ''}
    <div class="end-btns"><button class="btn" data-act="calendar">${icon('cal', 17)}Read another day</button>
      <button class="btn ghost" data-act="top">${icon('up', 17)}Back to top</button></div>
    ${DOC.disclaimer ? `<div class="disc">${esc(DOC.disclaimer)}</div>` : ''}
  </article>`;
}

/* ================================================================ layout: pagination + scroll hints */
function fontsReady() {
  if (!document.fonts || !document.fonts.load) return Promise.resolve();
  const want = ['700 26px Fraunces', '600 21px Fraunces', '400 16px Inter', '600 16px Inter', '700 16px Inter'].map(f => document.fonts.load(f).catch(() => null));
  return Promise.race([Promise.all(want).then(() => document.fonts.ready), new Promise(r => setTimeout(r, 3000))]);
}
async function afterLayout() {
  await fontsReady();
  relayout();
  READY = true;
}
/** Split any list card that doesn't fit into continuation cards, then refresh hints and observers. */
function relayout() {
  if (!DOC) return;
  const keep = CUR;
  for (const id of LISTS.keys()) paginate(id);
  hints(); observe();
  const s = keep && (slotById(keep) || slotById(keep.split('~')[0]));
  if (s && keep !== 'cover') deck.scrollTop = s.offsetTop;
}
function paginate(id) {
  const spec = LISTS.get(id);
  const old = [...deck.querySelectorAll(`.slot[data-list="${CSS.escape(id)}"]`)];
  if (!old.length) return;
  const make = (items, pg, n) => {
    const t = document.createElement('div');
    t.innerHTML = slotHTML({ id: n > 1 ? `${id}~${n}` : id, tab: spec.tab, list: id, label: spec.label, html: listArticle(spec, items, pg) });
    return t.firstElementChild;
  };
  const first = make(spec.items, '', 1);
  old[0].replaceWith(first); old.slice(1).forEach(s => s.remove());
  const pages = [first];
  for (let page = first, guard = 0; guard < 12; guard++) {
    const card = page.querySelector('.card'), ul = card.querySelector('.plist'), moved = [];
    while (card.scrollHeight > card.clientHeight + 1 && ul.children.length > 1) { const li = ul.lastElementChild; li.remove(); moved.unshift(li); }
    if (!moved.length) break;
    const next = make([], '', pages.length + 1);
    const nul = next.querySelector('.plist');
    moved.forEach(li => nul.appendChild(li));
    page.after(next); pages.push(next); page = next;
  }
  if (pages.length > 1) pages.forEach((p, i) => { const t = p.querySelector('.lc-pg'); if (t) t.textContent = `${i + 1} / ${pages.length}`; });
}
/** Toggle the "More ↓" hint on anything that can scroll inside a card (long briefs; safety-net cards). */
function hints(root) {
  (root || deck).querySelectorAll('.brief, .card.fit').forEach(el => {
    const can = el.scrollHeight > el.clientHeight + 2;
    el.classList.toggle('can-scroll', can);
    el.classList.toggle('at-end', !can || el.scrollTop + el.clientHeight >= el.scrollHeight - 4);
    if (can && !el.querySelector(':scope > .more')) el.insertAdjacentHTML('beforeend', `<div class="more"><span>${icon('down', 13)}More</span></div>`);
  });
}
deck.addEventListener('scroll', e => {
  const el = e.target;
  if (el.classList && el.classList.contains('can-scroll')) el.classList.toggle('at-end', el.scrollTop + el.clientHeight >= el.scrollHeight - 4);
}, true);
let RZ = null;
if (window.ResizeObserver) new ResizeObserver(() => { clearTimeout(RZ); RZ = setTimeout(() => { if (READY) relayout(); }, 180); }).observe(deck);

/* ================================================================ navigation: current card, tabs, progress, jumps */
let NAV = null;
function observe() {
  if (NAV) NAV.disconnect();
  NAV = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) setCurrent(e.target); }), { root: deck, rootMargin: '-45% 0px -45% 0px' });
  deck.querySelectorAll('.slot').forEach(s => NAV.observe(s));
}
function setCurrent(slot) {
  const id = slot.dataset.id;
  if (id === CUR) return;
  CUR = id;
  paintTab(slot.dataset.tab); paintProgress();
  if (PENDING.size) flushPending();
  saveHash();
}
const TAB_META = {
  today: { label: 'Today', icon: 'sun', color: 'top' },
  stories: { label: 'Top stories', icon: 'star', color: 'stories' },
  wrap: { label: 'Wrap-up', icon: 'check', color: 'next' },
};
function paintTabs() {
  const order = ['today', 'stories', ...DOC.sections.map(s => sk(s.key)), 'wrap'];
  const have = new Set([...deck.querySelectorAll('.slot')].map(s => s.dataset.tab));
  $('tabs').innerHTML = [...new Set(order)].filter(k => have.has(k)).map(k => {
    const m = TAB_META[k] || { label: sec(k).short, icon: k, color: k };
    const n = k === 'stories' ? stories().length : (DOC.sections.find(s => sk(s.key) === k) || { items: [] }).items.length;
    return `<button class="tab" data-act="tab" data-tab="${k}" style="${vars(m.color)}"><span>${icon(m.icon, 15)}${esc(m.label)}${n && k !== 'today' && k !== 'wrap' ? `<span class="n">${n}</span>` : ''}</span></button>`;
  }).join('');
}
function paintTab(tab) {
  const box = $('tabs');
  box.querySelectorAll('.tab').forEach(t => {
    const on = t.dataset.tab === tab;
    t.classList.toggle('on', on);
    t.setAttribute('aria-current', on ? 'true' : 'false');
    if (on) try { box.scrollTo({ left: t.offsetLeft - box.clientWidth / 2 + t.clientWidth / 2, behavior: READY ? 'smooth' : 'auto' }); } catch (e) { /* old Safari */ }
  });
  const m = TAB_META[tab] || { color: tab };
  const p = $('prog'); p.style.setProperty('--pa', `var(--${m.color}-a)`); p.style.setProperty('--pb', `var(--${m.color}-b)`);
}
function paintProgress() {
  const all = [...deck.querySelectorAll('.slot')], i = all.findIndex(s => s.dataset.id === CUR);
  $('prog').style.width = all.length ? Math.round((Math.max(0, i) + 1) / all.length * 100) + '%' : '0';
}
function goSlot(id, smooth = true) {
  const s = slotById(id);
  // Smooth for short hops; a long jump (tabs, "Back to top", far links) is instant, so it never drags through 8 cards.
  if (s) deck.scrollTo({ top: s.offsetTop, behavior: smooth && Math.abs(s.offsetTop - deck.scrollTop) <= deck.clientHeight * 2.5 ? 'smooth' : 'auto' });
  return s;
}
/** Jump to a story card ("s2"), a brief inside its section carousel ("b-cricket-1"), or any slot id. */
function jump(ref, { smooth = true } = {}) {
  if (!ref) return;
  if (storyById(ref)) { goSlot(ref, smooth); return; }
  const b = briefById(ref);
  if (b) {
    const slot = goSlot('sec-' + b.sec.key, smooth);
    const car = slot && slot.querySelector('.hcar'), el = car && car.querySelector(`[data-brief="${CSS.escape(ref)}"]`);
    if (el) { car.scrollTo({ left: el.offsetLeft - 8, behavior: smooth ? 'smooth' : 'auto' }); flash(el); }
    return;
  }
  goSlot(ref, smooth);
}
function flash(el) { el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash'); setTimeout(() => el.classList.remove('flash'), 1500); }
function goSlide(btn) {
  const car = btn.closest('.hcar'), el = car && car.querySelector(`.slide[data-slide="${CSS.escape(btn.dataset.to)}"]`);
  if (el) car.scrollTo({ left: el.offsetLeft - 8, behavior: 'smooth' });
}
function nextCard(btn) {
  const slot = btn.closest('.slot'), next = slot && slot.nextElementSibling;
  if (next) deck.scrollTo({ top: next.offsetTop, behavior: 'smooth' });
}

/* ================================================================ header bits */
function paintHeader() {
  if (!DOC) return;
  const st = DOC.status === 'partial' ? ' · Partial' : DOC.status === 'lite' ? ' · Lite' : '';
  const p = dparts(DATE);
  $('sub').innerHTML = `${esc(p.d + ' ' + MON[p.mo])} · ${esc(DOC.edition || '')}${esc(st)} ⌄`;
  document.title = `The Briefing · ${fmtDay(DATE, 'short')}`;
}
/** "Today's briefing is running late" when the newest edition is older than today (IST) after 06:45. */
function paintLate() {
  const el = $('late'), latest = latestDate(), t = istNow();
  const late = !LATE_DISMISSED && latest && latest < t.date && t.minutes >= LATE_AFTER_MIN;
  if (!late) { el.hidden = true; el.innerHTML = ''; return; }
  el.innerHTML = `<div class="late" role="status">${icon('clock', 18)}<span>Today’s briefing is running late — showing ${esc(fmtDay(latest, 'short'))}</span>
    <button data-act="late-x" aria-label="Dismiss">${icon('x', 16)}</button></div>`;
  el.hidden = false;
}
async function refresh() {
  const b = $('refresh');
  b.classList.add('spin');
  const ix = await getJSON(PATHS.index);
  b.classList.remove('spin');
  if (!ix) { toast('Couldn’t reach the server. Check your connection.'); return; }
  INDEX = ix; paintLate();
  const latest = latestDate(), cur = days().find(d => d.date === DATE);
  if (latest && (!DATE || latest > DATE)) { if (await openEdition(latest)) toast('Loaded the newest edition'); return; }
  if (cur && DOC && cur.edition && cur.edition !== DOC.edition) { if (await openEdition(DATE)) toast('Loaded the updated edition'); return; }
  const added = await Player.refresh();
  toast(added.length ? `${plural(added.length, 'new reel')} added` : 'You’re on the latest edition');
}

/* ================================================================ explainer sheet */
function sup(src) {
  const ns = arr(src).map(Number).filter(n => Number.isInteger(n) && SRC_NS.has(n));
  if (!ns.length) return '';
  return `<sup class="sr">${ns.map(n => `<a href="#src-${n}" data-act="src" data-n="${n}" aria-label="Source ${n}">${n}</a>`).join('')}</sup>`;
}
const para = (text, src) => text ? String(text).split(/\n{2,}/).map((p, i, all) => `<p>${rich(p)}${i === all.length - 1 ? sup(src) : ''}</p>`).join('') : '';
const blkHead = (label, ic, tag) => `<div class="bh"><span class="bl">${icon(ic, 15)}${esc(label)}</span>${tag ? `<span class="tag ${tag}">${cap(tag)}</span>` : ''}</div>`;
const initials = name => String(name || '?').split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join('').toUpperCase();

// The lesson: one idea built up step by step, a worked example line by line, then back to the news.
function lessonHTML(b) {
  if (!b || !b.concept) return '';
  const steps = arr(b.steps).filter(x => x && x.text), ex = b.example, lines = arr(ex && ex.lines).filter(x => x && x.calc);
  const ap = b.apply, pr = b.practice;
  return `<div class="lesson">
    <h3 class="ls-c">${esc(b.concept)}</h3>
    ${b.big_idea ? `<p class="ls-big">${rich(b.big_idea)}</p>` : ''}
    ${steps.length ? `<ol class="ls-steps">${steps.map((st, i) => `<li><span class="n">${i + 1}</span><div><b>${esc(st.title)}</b><p>${rich(st.text)}${sup(st.src)}</p></div></li>`).join('')}</ol>` : ''}
    ${lines.length ? `<div class="ls-ex"><div class="lab">${icon('hash', 14)}Worked example</div>${ex.setup ? `<p class="setup">${rich(ex.setup)}</p>` : ''}
      <ol class="ls-lines">${lines.map((l, i) => `<li><span class="n">${i + 1}</span><div><span class="k">${esc(l.label)}</span><span class="calc">${esc(l.calc)}</span>${l.note ? `<small>${esc(l.note)}</small>` : ''}</div></li>`).join('')}</ol>
      ${ex.result ? `<div class="res">${icon('cc', 18)}<p>${rich(ex.result)}</p></div>` : ''}</div>` : ''}
    ${ap && ap.text ? `<div class="ls-apply"><div class="lab">${icon('news', 14)}Back to the news</div><p>${rich(ap.text)}${sup(ap.src)}</p></div>` : ''}
    ${pr && pr.q ? `<details class="ls-try"><summary><span class="lab">${icon('help', 14)}Try it yourself</span><span class="q">${esc(pr.q)}</span>
      <span class="rv">Show the answer${icon('chev', 15, 'chev')}</span></summary><p>${rich(pr.answer)}</p></details>` : ''}
  </div>`;
}

// Fixed block order; optional blocks are skipped when missing.
const BLOCKS = [
  ['so_far', 'The story so far', 'history', 'fact', b => para(b.text, b.src)],
  ['what_happened', 'What happened', 'news', 'fact', b => para(b.text, b.src)],
  ['lesson', 'Learn the idea', 'learn', 'lesson', lessonHTML],
  ['why_chain', 'Why it happened', 'link', 'analysis', b => arr(b.steps).length ? `<ol class="chain">${arr(b.steps).map(st => `<li>${rich(st.text)}${sup(st.src)}</li>`).join('')}</ol>` : ''],
  ['players', 'Key players', 'users', null, b => arr(b.items).length ? `<div class="players">${arr(b.items).map(p => `<div class="player"><span class="av" aria-hidden="true">${esc(initials(p.name))}</span><div><b>${esc(p.name)}</b><span>${rich(p.who)}</span></div></div>`).join('')}</div>` : ''],
  ['numbers', 'By the numbers', 'hash', null, b => arr(b.items).length ? `<div class="nums">${arr(b.items).map(x => `<div class="num"><b>${esc(x.value)}</b><span>${rich(x.meaning)}${sup(x.src)}</span></div>`).join('')}</div>` : ''],
  ['analogy', 'Think of it like this', 'bulb', null, b => b.text ? `<div class="analogy"><p>${rich(b.text)}</p>${b.breaks ? `<div class="breaks">${icon('alert', 17)}<div><b>Where the comparison breaks</b>${rich(b.breaks)}</div></div>` : ''}</div>` : ''],
  ['views', 'Views', 'scale', 'views', b => arr(b.items).length ? `<div class="views">${arr(b.items).map(v => `<div class="view"><b>${esc(v.holder)}</b><p>${rich(v.view)}</p></div>`).join('')}</div>` : ''],
  ['for_you', 'What it means for you', 'user', null, b => b.text ? `<div class="foryou"><p>${rich(b.text)}${sup(b.src)}</p></div>` : ''],
  ['misconception', 'Common misconception', 'alert', null, b => (b.myth || b.fact) ? `<div class="myth">
      ${b.myth ? `<div class="mf m">${icon('xc', 18)}<div><b>Myth</b><p>${rich(b.myth)}</p></div></div>` : ''}
      ${b.fact ? `<div class="mf f">${icon('cc', 18)}<div><b>Fact</b><p>${rich(b.fact)}${sup(b.src)}</p></div></div>` : ''}</div>` : ''],
  ['next', 'What’s next', 'calnext', null, b => {
    const dates = arr(b.dates).filter(x => x && x.date), unk = arr(b.unknowns).filter(Boolean);
    return para(b.text) +
      (dates.length ? `<ul class="dates">${dates.map(x => { const p = dparts(x.date); return `<li><span class="d"><small>${MON[p.mo] || ''}</small><b>${esc(p.d)}</b></span><span>${esc(x.what)}<br><small style="color:var(--dim);font-size:13px">${esc(WDL[p.wd] || '')}</small></span></li>`; }).join('')}</ul>` : '') +
      (unk.length ? `<div class="unk"><span class="lab">Still unknown</span><ul>${unk.map(u => `<li>${icon('help', 16)}<span>${rich(u)}</span></li>`).join('')}</ul></div>` : '');
  }],
];

function explainerHTML(s) {
  const k = sk(s.section), b = s.blocks || {}, v = Player.info(s.id);
  SRC_NS = new Set(arr(s.sources).map(x => Number(x && x.n)).filter(Number.isInteger));
  const c = s.confidence || {}, lvl = ['high', 'medium', 'low'].includes(c.level) ? c.level : null;
  const conf = [];
  if (c.publishers) conf.push(plural(c.publishers, 'outlet'));
  if (c.primary) conf.push(plural(c.primary, 'official document'));
  if (c.newest) conf.push('newest ' + stamp(c.newest));
  const t = s.thread;
  const blocks = BLOCKS.map(([key, label, ic, tag, fn]) => { const body = b[key] ? fn(b[key]) : ''; return body ? `<section class="blk" data-block="${key}">${blkHead(label, ic, tag)}${body}</section>` : ''; }).join('');
  const terms = arr(s.terms).filter(x => x && x.term);
  const scenes = arr(s.reel && s.reel.scenes).filter(x => x && x.say);
  const chk = s.check && s.check.q && arr(s.check.options).length ? s.check : null;
  return `
  <div class="ex-bar"><div class="ex-bar-in">
    <button class="ex-x" data-act="ex-close" aria-label="Close explainer"><span>${icon('down', 20)}</span></button>
    <div class="ex-mid"><div class="ex-chip">${icon(k, 15)}${esc(sec(k).short)} · ${esc(s.read_min || 4)} min read</div><div class="ex-mini">${esc(s.headline)}</div></div>
    ${v ? `<button class="ex-watch" data-act="playall" data-story="${esc(s.id)}">${icon('play', 14, 'fill')}Watch</button>` : ''}
  </div></div>
  <header class="ex-hero"><div class="big">${icon(k, 24)}</div><div class="ex-hero-in">
    ${storyBadges(s)}
    <h1 class="ex-h">${esc(s.headline)}</h1>
    ${s.question ? `<p class="ex-q">${icon('help', 18)}${esc(s.question)}</p>` : ''}
  </div></header>
  <div class="ex-body">
    ${s.dek ? `<p class="ex-dek">${rich(s.dek)}</p>` : ''}
    ${(lvl || conf.length) ? `<div class="ex-conf">${icon('shield', 18)}<div>How sure are we? ${lvl ? `<span class="lvl ${lvl}"><i></i>${cap(lvl)}</span>` : ''}${conf.length ? ' · ' + conf.map(esc).join(' · ') : ''}</div></div>` : ''}
    ${s.contested ? `<div class="ex-contested">${icon('scale', 16)}<span>Contested: the people involved disagree. Each side’s view is set out under <b>Views</b>.</span></div>` : ''}
    ${t && (t.previously || t.changed) ? `<div class="thread"><div class="th-h">${icon('activity', 16)}Day ${esc(t.day || 1)} of this story${THREAD[t.status] ? ' · ' + THREAD[t.status] : ''}</div>
      ${t.previously ? `<div class="th-row"><span class="lab">Previously</span><p>${rich(t.previously)}</p></div>` : ''}
      ${t.changed ? `<div class="th-row now"><span class="lab">What changed</span><p>${rich(t.changed)}</p></div>` : ''}</div>` : ''}
    ${blocks}
    ${arr(s.takeaways).length ? `<section class="xs learned"><div class="xs-h"><span class="sq grad">${icon('learn', 18)}</span><div><h2>What you learned</h2><small>Three things to remember</small></div></div>
      <ul class="tk">${arr(s.takeaways).map(x => `<li>${icon('check', 16)}<span>${rich(x)}</span></li>`).join('')}</ul></section>` : ''}
    ${chk ? `<section class="xs check"><div class="xs-h"><span class="sq grad">${icon('help', 18)}</span><div><h2>Check yourself</h2><small>Tap an answer to reveal it</small></div></div>
      <p class="qq">${esc(chk.q)}</p>${optsHTML(chk)}</section>` : ''}
    ${terms.length ? `<section class="xs"><div class="xs-h"><span class="sq grad">${icon('book', 18)}</span><div><h2>Words to know</h2><small>Tap a word for its meaning</small></div></div>
      <div class="terms">${terms.map((x, i) => `<button class="term" data-act="term" data-i="${i}" aria-expanded="false">${esc(x.term)}</button>`).join('')}</div>
      <div class="term-def" hidden></div></section>` : ''}
    ${scenes.length ? `<section class="xs"><details class="trans"><summary>${icon('film', 18)}<span>Reel transcript<br><small>${plural(scenes.length, 'scene')} · what the narrator says</small></span>${icon('chev', 18, 'chev')}</summary>
      <ol class="scenes">${scenes.map(sc => `<li>${sc.show ? `<small>${esc(sc.show)}</small><br>` : ''}${esc(sc.say)}</li>`).join('')}</ol></details></section>` : ''}
    ${arr(s.sources).length ? `<section class="xs" id="ex-sources"><div class="xs-h"><span class="sq grad">${icon('link', 18)}</span><div><h2>Sources</h2><small>${plural(arr(s.sources).length, 'source')} · tap a number in the text to jump here</small></div></div>
      <ol class="srcs">${arr(s.sources).map(srcHTML).join('')}</ol></section>` : ''}
    <div class="ex-end">${DOC.disclaimer ? `<p class="disc">${esc(DOC.disclaimer)}</p>` : ''}
      <button class="btn" data-act="ex-close" style="margin-top:14px">${icon('left', 17)}Back to the briefing</button></div>
  </div>`;
}
function srcHTML(x) {
  if (!x) return '';
  const n = Number(x.n), url = safeUrl(x.url), when = stamp(x.published), ty = SRC_TYPE[x.type] ? x.type : null;
  return `<li class="src" id="src-${Number.isInteger(n) ? n : 0}">
    <div class="src-top"><span class="src-n">${esc(Number.isInteger(n) ? n : '•')}</span><b>${esc(x.pub || 'Source')}</b>
      ${when ? `<time>${esc(when)}</time>` : '<span class="ud">undated</span>'}${ty ? `<span class="ty ${ty}">${SRC_TYPE[ty]}</span>` : ''}</div>
    ${x.excerpt ? `<q>${esc(x.excerpt)}</q>` : ''}
    ${url ? `<a class="open" href="${esc(url)}" target="_blank" rel="noopener noreferrer">Open the source ${icon('ext', 14)}</a>` : ''}
  </li>`;
}

function openExplainer(id, { fromHash = false, block = '' } = {}) {
  const s = storyById(id);
  if (!s) return;
  const ex = $('ex'), sc = $('exScroll');
  EX_RETURN = document.activeElement;
  ex.setAttribute('style', vars(sk(s.section)));
  ex.setAttribute('aria-label', s.headline || 'Explainer');
  sc.innerHTML = explainerHTML(s);
  sc.scrollTop = 0; ex.classList.remove('scrolled');
  ex.hidden = false;
  raf2(() => ex.classList.add('open'));
  const already = !!EX;           // e.g. "Read explainer" from Play all while a sheet is already open
  EX = id;
  if (!already) Player.hold();    // one hold per open sheet, released once on close
  const h = `#${DATE}/${id}`;
  try {
    if (fromHash || already) history.replaceState({ ex: id }, '', h);   // swapping stories must not stack history
    else { history.pushState({ ex: id }, '', h); EX_PUSHED = true; }
    if (fromHash && !already) EX_PUSHED = false;
  } catch (e) { /* ignore */ }
  setTimeout(() => { const x = ex.querySelector('.ex-x'); if (x) x.focus({ preventScroll: true }); }, 60);
  if (block) setTimeout(() => {          // e.g. "What you learned today" opens straight at the lesson
    const el = sc.querySelector(`[data-block="${CSS.escape(block)}"]`), bar = ex.querySelector('.ex-bar');
    if (el) sc.scrollTop += el.getBoundingClientRect().top - sc.getBoundingClientRect().top - (bar ? bar.offsetHeight : 56) - 8;
  }, 380);
}
function closeExplainer({ fromPop = false, silent = false } = {}) {
  if (!EX) return;
  const ex = $('ex');
  EX = null;
  ex.classList.remove('open');
  setTimeout(() => { if (!EX) { ex.hidden = true; $('exScroll').innerHTML = ''; } }, 360);
  if (!fromPop && !silent) {
    if (EX_PUSHED) history.back();
    else try { history.replaceState(null, '', '#' + DATE); } catch (e) { /* ignore */ }
  }
  EX_PUSHED = false;
  Player.release();
  if (!silent) { saveHash(); if (EX_RETURN && document.contains(EX_RETURN)) EX_RETURN.focus({ preventScroll: true }); }
}
// mini header shows the headline once the hero has scrolled away
$('exScroll').addEventListener('scroll', () => {
  const sc = $('exScroll'), hero = sc.querySelector('.ex-hero');
  $('ex').classList.toggle('scrolled', !!hero && sc.scrollTop > hero.offsetHeight - 20);
}, { passive: true });
// swipe down (from the top of the sheet, or on its header) closes it
(() => {
  const ex = $('ex'), sc = $('exScroll');
  let y0 = null, dy = 0;
  ex.addEventListener('touchstart', e => { y0 = (sc.scrollTop <= 0 || e.target.closest('.ex-bar')) ? e.touches[0].clientY : null; dy = 0; }, { passive: true });
  ex.addEventListener('touchmove', e => {
    if (y0 == null) return;
    dy = e.touches[0].clientY - y0;
    if (dy <= 0) { if (ex.classList.contains('drag')) { ex.classList.remove('drag'); ex.style.transform = ''; } return; }
    e.preventDefault();
    ex.classList.add('drag'); ex.style.transform = `translateY(${dy * 0.9}px)`;
  }, { passive: false });
  ex.addEventListener('touchend', () => {
    if (y0 == null) return;
    y0 = null; ex.classList.remove('drag'); ex.style.transform = '';
    if (dy > 110) closeExplainer();
  });
})();
function scrollToSource(a) {
  const el = document.getElementById('src-' + a.dataset.n);
  if (!el) return;
  el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  el.classList.add('hit'); setTimeout(() => el.classList.remove('hit'), 1600);
}
function toggleTerm(btn) {
  const s = storyById(EX), x = s && arr(s.terms).filter(t => t && t.term)[+btn.dataset.i];
  const box = btn.closest('.xs'), def = box.querySelector('.term-def'), on = !btn.classList.contains('on');
  box.querySelectorAll('.term').forEach(t => { t.classList.remove('on'); t.setAttribute('aria-expanded', 'false'); });
  if (on && x) { btn.classList.add('on'); btn.setAttribute('aria-expanded', 'true'); def.innerHTML = `<b>${esc(x.term)}</b>: ${esc(x.meaning)}`; def.hidden = false; }
  else def.hidden = true;
}

/* ================================================================ bottom sheets: calendar + display */
let SHEET = null, CAL = null;
function openSheet(kind, title, html) {
  if (!SHEET) Player.hold();
  SHEET = kind; $('stitle').textContent = title; $('sbody').innerHTML = html;
  $('mask').classList.add('open'); $('sheet').classList.add('open');
}
function closeSheet() {
  if (!SHEET) return;
  SHEET = null; $('mask').classList.remove('open'); $('sheet').classList.remove('open');
  Player.release();
}
async function openCalendar() {
  const p = dparts(DATE || istNow().date);
  CAL = { y: p.y, mo: p.mo };
  openSheet('cal', 'Choose a day', calHTML());
  if (!ARCHIVE) {
    ARCHIVE = await getJSON(PATHS.archive) || { days: [] };
    if (SHEET === 'cal') $('sbody').innerHTML = calHTML();
  }
}
function calHTML() {
  const B = new Map(days().map(d => [d.date, d]));
  const A = new Map(arr(ARCHIVE && ARCHIVE.days).filter(d => d && d.date && !B.has(d.date)).map(d => [d.date, d]));
  const all = [...B.keys(), ...A.keys()].sort();
  const { y, mo } = CAL, lead = (new Date(Date.UTC(y, mo, 1)).getUTCDay() + 6) % 7, n = new Date(Date.UTC(y, mo + 1, 0)).getUTCDate();
  const ym = isoOf(y, mo, 1).slice(0, 7), minM = all.length ? all[0].slice(0, 7) : ym, maxM = all.length ? all[all.length - 1].slice(0, 7) : ym;
  const today = istNow().date, latest = latestDate();
  let cells = ['M', 'T', 'W', 'T', 'F', 'S', 'S'].map(w => `<div class="wd" aria-hidden="true">${w}</div>`).join('');
  for (let i = 0; i < lead; i++) cells += '<div></div>';
  for (let d = 1; d <= n; d++) {
    const key = isoOf(y, mo, d), b = B.get(key), a = A.get(key), t = key === today ? ' today' : '';
    if (b) {
      const part = b.status && b.status !== 'complete' ? ' part' : '';
      cells += `<button class="day has${part}${key === DATE ? ' sel' : ''}${t}" data-act="day" data-date="${key}" aria-label="${esc(fmtDay(key, 'long'))}: The Briefing${part ? ' (' + esc(b.status) + ')' : ''}">${d}</button>`;
    } else if (a) {
      cells += `<a class="day has old${t}" href="${esc(PATHS.archivePage(key))}" aria-label="${esc(fmtDay(key, 'long'))}: old Daily Digest">${d}</a>`;
    } else cells += `<div class="day${t}">${d}</div>`;
  }
  return `<div class="quick"><button class="seg ${DATE === latest ? 'on' : ''}" data-act="day" data-date="${esc(latest || '')}" ${latest ? '' : 'disabled'}>${icon('sun', 16)}Latest briefing</button>
      <a class="seg" href="digest.html">${icon('history', 16)}Old Digest</a></div>
    <div class="calhead"><button data-act="cal-move" data-v="-1" ${ym <= minM ? 'disabled' : ''} aria-label="Previous month">${icon('left', 16)}</button>
      <b>${MONL[mo]} ${y}</b>
      <button data-act="cal-move" data-v="1" ${ym >= maxM ? 'disabled' : ''} aria-label="Next month">${icon('chev', 16)}</button></div>
    <div class="cal">${cells}</div>
    <div class="legend"><span><i></i>Briefing</span><span><i class="p"></i>Partial or lite</span><span><i class="o"></i>Old Daily Digest</span></div>
    <p class="cal-note">Grey days open the archive of the old Daily Digest.</p>`;
}
function calMove(k) { CAL.mo += k; if (CAL.mo < 0) { CAL.mo = 11; CAL.y--; } if (CAL.mo > 11) { CAL.mo = 0; CAL.y++; } $('sbody').innerHTML = calHTML(); }
async function pickDay(d) {
  closeSheet();
  if (d && d !== DATE) { if (await openEdition(d)) saveHash(); }
}
function openDisplay() { openSheet('display', 'Display', displayHTML()); }
function displayHTML() {
  const p = prefs(), cur = (p.theme === 'dark' || p.theme === 'light') ? p.theme : 'auto', size = +(p.size || 1);
  const T = [['auto', 'Auto', 'linear-gradient(135deg,#0c0e13 50%,#eef0f5 50%)'], ['dark', 'Dark', '#0c0e13'], ['light', 'Light', '#eef0f5']];
  return `<div class="h4">Appearance</div><div class="themes">${T.map(([k, l, bg]) =>
      `<button class="theme ${k === cur ? 'on' : ''}" data-act="theme" data-v="${k}" aria-pressed="${k === cur}"><span class="sw" style="background:${bg}"></span><small>${l}</small></button>`).join('')}</div>
    <div class="h4">Text size</div>
    <div class="row2">${[[0.92, 'Smaller'], [1, 'Default'], [1.1, 'Larger']].map(([v, l]) => `<button class="seg ${size === v ? 'on' : ''}" data-act="size" data-v="${v}" aria-pressed="${size === v}">${l}</button>`).join('')}</div>`;
}
function applyTheme(t) {
  const dark = window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches;
  document.documentElement.dataset.theme = (t === 'dark' || t === 'light') ? t : (dark ? 'dark' : 'light');
  const m = document.querySelector('meta[name="theme-color"]');
  if (m) m.content = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim() || '#0c0e13';
}
function setTheme(t) { const p = prefs(); p.theme = t; savePrefs(p); applyTheme(t); $('sbody').innerHTML = displayHTML(); }
function setSize(v) { const p = prefs(); p.size = v; savePrefs(p); document.documentElement.style.setProperty('--tsz', v); $('sbody').innerHTML = displayHTML(); relayout(); }
try { matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { const t = prefs().theme; if (t !== 'dark' && t !== 'light') applyTheme('auto'); }); } catch (e) { /* old Safari */ }

/* ================================================================ one delegated click handler (player.js has its own for video acts) */
document.addEventListener('click', e => {
  const t = e.target.closest('[data-act]');
  if (!t) return;
  switch (t.dataset.act) {
    case 'calendar': openCalendar(); break;
    case 'refresh': refresh(); break;
    case 'display': openDisplay(); break;
    case 'sheet-close': closeSheet(); break;
    case 'theme': setTheme(t.dataset.v); break;
    case 'size': setSize(+t.dataset.v); break;
    case 'cal-move': calMove(+t.dataset.v); break;
    case 'day': pickDay(t.dataset.date); break;
    case 'tab': { const s = deck.querySelector(`.slot[data-tab="${CSS.escape(t.dataset.tab)}"]`); if (s) goSlot(s.dataset.id); break; }
    case 'jump': jump(t.dataset.ref); break;
    case 'slide': goSlide(t); break;
    case 'next-card': nextCard(t); break;
    case 'explain': openExplainer(t.dataset.story); break;
    case 'learn': openExplainer(t.dataset.story, { block: 'lesson' }); break;
    case 'ex-close': closeExplainer(); break;
    case 'answer': answer(t); break;
    case 'term': toggleTerm(t); break;
    case 'src': e.preventDefault(); scrollToSource(t); break;
    case 'top': goSlot('cover'); break;
    case 'late-x': LATE_DISMISSED = true; paintLate(); break;
    case 'retry': openEdition(t.dataset.date); break;
  }
});
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape' || Player.playingAll) return;
  if (SHEET) closeSheet(); else if (EX) closeExplainer();
});
document.addEventListener('visibilitychange', () => { if (!document.hidden && INDEX) paintLate(); });
// Sheets and Play all sit above the deck; the "playall" act also closes the explainer's hold via player.js.

/* ================================================================ go */
window.Briefing = {           // small surface for tests/ui (and debugging in the console)
  get ready() { return READY; },
  state: () => ({ date: DATE, cur: CUR, ex: EX, sheet: SHEET, slots: [...deck.querySelectorAll('.slot')].map(s => s.dataset.id), now: now() }),
  jump, openExplainer, closeExplainer, relayout, openCalendar,
};
boot();

if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost')) {
  const had = !!navigator.serviceWorker.controller;
  navigator.serviceWorker.register('./sw.js', { updateViaCache: 'none' }).then(r => r.update()).catch(() => {});
  let reloaded = false;
  // A new version took over: reload once, but never under the reader's nose (only before they've opened anything).
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (had && !reloaded && !EX && !Player.playingAll && (CUR === 'cover' || !CUR)) { reloaded = true; location.reload(); }
  });
}
})();
