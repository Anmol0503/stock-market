// Screenshot + overflow check for The Briefing (dashboard/reels). Run: cd tests/ui && npm install && node shoot.mjs
//
// What it does
//  1. Builds a throwaway site in a temp dir: copies dashboard/reels + dashboard/digest (the real archive), puts the
//     fixtures at dashboard/briefing/… and two generated test reels (ffmpeg) at dashboard/media/2026-11-03/….
//     The real dashboard/briefing/ is never touched.
//  2. Serves it with `python3 -m http.server` and drives the system Chrome through playwright-core.
//  3. For each viewport × theme it visits every card, checks for clipped text / unintended overflow, and saves
//     screenshots of the key screens to tests/ui/out/<viewport>-<theme>/.
//  4. Fails (exit 1) on any console error, or if overflow targets are missed:
//     0 at 390×664 and 412×780, at most 1 at 375×548 (390×844 is reported, target 0).
//
// Env overrides: CHROME=/path/to/chrome  FFMPEG=/path/to/ffmpeg  ONLY=390x664  THEMES=dark
// This module also exports the harness (setup/teardown/helpers) for flows.mjs.

import { chromium } from 'playwright-core';
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const HERE = path.dirname(fileURLToPath(import.meta.url));
export const ROOT = path.resolve(HERE, '..', '..');
export const OUT = path.join(HERE, 'out');
export const FIX = path.join(ROOT, 'tests', 'fixtures', 'briefing');
export const DATE = '2026-11-03';
export const NOW = '2026-11-03T07:10';           // IST; before 08:30 so reel polling is live, after the edition
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

/* ------------------------------------------------------------------ test media (generated once, cached in out/) */
function ffmpegBin() {
  const cands = [process.env.FFMPEG, path.join(os.homedir(), '.local', 'bin', 'ffmpeg'), 'ffmpeg'].filter(Boolean);
  for (const c of cands) { const r = spawnSync(c, ['-version'], { stdio: 'ignore' }); if (r.status === 0) return c; }
  throw new Error('ffmpeg not found (set FFMPEG=/path/to/ffmpeg)');
}
function fontArg() {
  const f = ['/System/Library/Fonts/Supplemental/Arial Bold.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'].find(p => fs.existsSync(p));
  return f ? `fontfile='${f}':` : '';
}
/** Two short vertical reels (720×1280, 8 s, colour + text + sine tone) and distinct poster JPGs. */
export function makeMedia() {
  const dir = path.join(OUT, '.media');
  fs.mkdirSync(dir, { recursive: true });
  const ff = ffmpegBin(), font = fontArg();
  const reels = [
    { file: 's1-spain-rail-signalling', color: '0x2f47c4', label: 'S1  SPAIN RAIL', tone: 440 },
    { file: 's2-delhi-truck-ban', color: '0xb5541a', label: 'S2  DELHI SMOG', tone: 523 },
  ];
  for (const r of reels) {
    const mp4 = path.join(dir, r.file + '.mp4'), jpg = path.join(dir, r.file + '.jpg');
    if (!fs.existsSync(mp4)) {
      const vf = [
        `drawtext=${font}text='${r.label}':fontsize=78:fontcolor=white:x=(w-tw)/2:y=h*0.26`,
        `drawtext=${font}text='%{eif\\:t\\:d} s':fontsize=120:fontcolor=white@0.85:x=(w-tw)/2:y=h*0.36`,
        `drawtext=${font}text='Burned-in caption':fontsize=46:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=18:x=(w-tw)/2:y=h*0.5`,
      ].join(',');
      const a = spawnSync(ff, ['-y', '-loglevel', 'error', '-f', 'lavfi', '-i', `color=c=${r.color}:s=720x1280:d=8:r=30`,
        '-f', 'lavfi', '-i', `sine=frequency=${r.tone}:sample_rate=44100:duration=8`, '-vf', vf,
        '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '96k', '-shortest', '-movflags', '+faststart', mp4]);
      if (a.status !== 0) throw new Error('ffmpeg failed: ' + a.stderr);
    }
    if (!fs.existsSync(jpg)) {
      const vf = `drawtext=${font}text='POSTER':fontsize=110:fontcolor=white:x=(w-tw)/2:y=h*0.3,drawtext=${font}text='${r.label}':fontsize=60:fontcolor=white@0.8:x=(w-tw)/2:y=h*0.42`;
      const b = spawnSync(ff, ['-y', '-loglevel', 'error', '-f', 'lavfi', '-i', `color=c=${r.color}:s=720x1280:d=1`, '-vf', vf, '-frames:v', '1', '-q:v', '4', jpg]);
      if (b.status !== 0) throw new Error('ffmpeg poster failed: ' + b.stderr);
    }
  }
  return dir;
}

/* ------------------------------------------------------------------ throwaway site + server + browser */
export function buildSite({ index, edition, videos } = {}) {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'briefing-ui-'));
  const dash = path.join(tmp, 'dashboard');
  // Only the parts the app reads: the app itself and the real old-digest archive.
  fs.cpSync(path.join(ROOT, 'dashboard', 'reels'), path.join(dash, 'reels'), { recursive: true });
  fs.cpSync(path.join(ROOT, 'dashboard', 'digest'), path.join(dash, 'digest'), { recursive: true });
  fs.mkdirSync(path.join(dash, 'briefing', 'videos'), { recursive: true });
  fs.writeFileSync(path.join(dash, 'briefing', `${DATE}.json`), edition ? JSON.stringify(edition) : fs.readFileSync(path.join(FIX, `${DATE}.json`)));
  fs.writeFileSync(path.join(dash, 'briefing', 'index.json'), index ? JSON.stringify(index) : fs.readFileSync(path.join(FIX, 'index.json')));
  fs.writeFileSync(path.join(dash, 'briefing', 'videos', `${DATE}.json`), videos ? JSON.stringify(videos) : fs.readFileSync(path.join(FIX, `videos-${DATE}.json`)));
  const media = makeMedia(), mdir = path.join(dash, 'media', DATE);
  fs.mkdirSync(mdir, { recursive: true });
  for (const f of fs.readdirSync(media)) fs.copyFileSync(path.join(media, f), path.join(mdir, f));
  return tmp;
}
async function freePort() {
  return new Promise((res, rej) => { const s = net.createServer(); s.unref(); s.on('error', rej); s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); }); });
}
export async function serve(dir) {
  const port = await freePort();
  const proc = spawn('python3', ['-m', 'http.server', String(port), '--bind', '127.0.0.1', '--directory', dir], { stdio: 'ignore' });
  for (let i = 0; i < 60; i++) {
    try { const r = await fetch(`http://127.0.0.1:${port}/dashboard/reels/index.html`); if (r.ok) break; } catch (e) { /* not up yet */ }
    await new Promise(r => setTimeout(r, 100));
  }
  return { port, proc, base: `http://127.0.0.1:${port}`, local: `http://localhost:${port}` };
}
export async function setup(opts = {}) {
  const dir = buildSite(opts);
  const server = await serve(dir);
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  return { dir, server, browser };
}
export async function teardown(h) {
  try { await h.browser.close(); } catch (e) { /* already closed */ }
  try { h.server.proc.kill(); } catch (e) { /* gone */ }
  try { fs.rmSync(h.dir, { recursive: true, force: true }); } catch (e) { /* tmp */ }
}

/** A phone-like context. theme: 'dark' | 'light' (emulated colour scheme + the app's own prefs override). */
export async function phone(browser, { width = 390, height = 664, theme = 'dark' } = {}) {
  const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, colorScheme: theme });
  await ctx.addInitScript(t => { try { localStorage.setItem('briefing_prefs', JSON.stringify({ theme: t })); } catch (e) { /* ignore */ } }, theme);
  const page = await ctx.newPage();
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  return { ctx, page, errors };
}
export async function openApp(page, base, { now = NOW, hash = DATE, query = '' } = {}) {
  await page.goto(`${base}/dashboard/reels/?now=${encodeURIComponent(now)}${query}#${hash}`);
  await page.waitForFunction(() => window.Briefing && window.Briefing.ready, null, { timeout: 20000 });
  await page.waitForTimeout(250);
}
export async function goSlot(page, id, settle = 250) {
  await page.evaluate(id => { const s = document.querySelector(`.slot[data-id="${CSS.escape(id)}"]`); if (s) document.getElementById('deck').scrollTop = s.offsetTop; }, id);
  await page.waitForTimeout(settle);
}

/* ------------------------------------------------------------------ the overflow check (runs in the page) */
/** For one slot: every text line must be visible (not cut by an ancestor's overflow, the card, or the viewport), and a
 *  card designed to fit (.fit) must not need to scroll. Line-clamped text is reported separately (intended), and so is
 *  intended scrolling (long briefs). Returns {issues[], clamped[], scrolls[], small[]}. */
export function checkSlot(id) {
  const slot = document.querySelector(`.slot[data-id="${CSS.escape(id)}"]`);
  const out = { id, issues: [], clamped: [], scrolls: [], small: [] };
  if (!slot) { out.issues.push('slot missing'); return out; }
  const vh = innerHeight, hdr = document.getElementById('hdr').getBoundingClientRect().bottom;
  const name = el => (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).join('.') : el.tagName.toLowerCase());
  const snippet = t => t.trim().replace(/\s+/g, ' ').slice(0, 48);
  const intendedScroller = a => a.matches('[data-scroll="x"], .hcar, .brief, #deck');
  for (const card of slot.querySelectorAll('.card')) {
    const cr = card.getBoundingClientRect();
    const label = card.matches('.slide') ? `${id}[slide ${card.dataset.slide}]` : id;
    if (card.matches('.fit') && card.scrollHeight > card.clientHeight + 1) out.issues.push(`${label}: card needs to scroll (${card.scrollHeight} > ${card.clientHeight})`);
    if (card.matches('.brief') && card.scrollHeight > card.clientHeight + 1) out.scrolls.push(`${label}: brief scrolls (${card.scrollHeight - card.clientHeight}px more)`);
    if (cr.top < hdr - 1 || cr.bottom > vh + 1) out.issues.push(`${label}: card outside the viewport (${Math.round(cr.top)}–${Math.round(cr.bottom)} vs ${Math.round(hdr)}–${vh})`);
    const seen = new Set();
    const walker = document.createTreeWalker(card, NodeFilter.SHOW_TEXT, { acceptNode: n => (n.nodeValue.trim() ? 1 : 2) });
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const el = n.parentElement;
      if (!el || el.closest('svg, [aria-hidden="true"], .more, .st-media, [hidden]')) continue;
      const cs = getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) continue;
      const range = document.createRange(); range.selectNodeContents(n);
      const rects = [...range.getClientRects()].filter(r => r.width > 0.5 && r.height > 0.5);
      for (const r of rects) {
        let problem = null;
        for (let a = el; a && a !== card.parentElement; a = a.parentElement) {
          const acs = getComputedStyle(a);
          const cx = acs.overflowX !== 'visible', cy = acs.overflowY !== 'visible';
          if (!cx && !cy) continue;
          const ar = a.getBoundingClientRect();
          const tolY = Math.max(2, r.height * 0.25), tolX = 2;   // glyph boxes overhang the line box a little
          const outY = cy && (r.bottom > ar.bottom + tolY || r.top < ar.top - tolY);
          const outX = cx && (r.right > ar.right + tolX || r.left < ar.left - tolX);
          if (!outY && !outX) continue;
          const clamp = a.classList.contains('clamp') || (acs.webkitLineClamp && acs.webkitLineClamp !== 'none') || acs.textOverflow === 'ellipsis';
          if (clamp) { problem = { kind: 'clamped', a }; break; }
          if (intendedScroller(a) && !(outY && a.matches('.hcar'))) { problem = { kind: 'scroll', a }; break; }
          if (a.matches('.card.fit') && outY) { problem = { kind: 'fitscroll', a }; break; }
          problem = { kind: 'cut', a }; break;
        }
        if (!problem && card.matches(':not(.slide)') && (r.bottom > vh + 2 || r.top < hdr - 2)) problem = { kind: 'viewport' };
        if (!problem) continue;
        const key = problem.kind + name(el) + snippet(n.nodeValue);
        if (seen.has(key)) continue;
        seen.add(key);
        if (problem.kind === 'clamped') out.clamped.push(`${label}: ${name(problem.a)} “${snippet(n.nodeValue)}…”`);
        else if (problem.kind === 'cut') out.issues.push(`${label}: text cut by ${name(problem.a)}: “${snippet(n.nodeValue)}”`);
        else if (problem.kind === 'viewport') out.issues.push(`${label}: text outside the viewport: “${snippet(n.nodeValue)}”`);
        // 'scroll' (inside an intended scroller) and 'fitscroll' (already counted at card level) aren't extra issues
      }
    }
    // tap targets inside the card (report only)
    card.querySelectorAll('button, a[href]').forEach(b => {
      const r = b.getBoundingClientRect(), cs = getComputedStyle(b);
      if (!r.width || cs.display === 'none' || b.closest('[hidden], sup')) return;
      if (r.height < 44 && r.width < 44) out.small.push(`${label}: ${name(b)} ${Math.round(r.width)}×${Math.round(r.height)}`);
      else if (Math.min(r.height, r.width) < 32) out.small.push(`${label}: ${name(b)} ${Math.round(r.width)}×${Math.round(r.height)}`);
    });
  }
  return out;
}

/* ------------------------------------------------------------------ main: shoot everything */
const VIEWPORTS = [
  { width: 390, height: 664, target: 0 },     // iPhone 14 in Safari with toolbars
  { width: 375, height: 548, target: 1 },     // iPhone SE in Safari
  { width: 412, height: 780, target: 0 },     // large Android
  { width: 390, height: 844, target: 0 },     // iPhone 14 full screen (standalone)
];
const SHOTS = { cover: 'cover', changes: 'before-you-scroll', s1: 'story-video', s3: 'story-stale-no-video', s4: 'story-no-video',
  'sec-world': 'section-intro', quiet: 'quiet', also: 'also', developing: 'developing', end: 'caught-up' };

async function shootOne(h, vp, theme, report) {
  const tag = `${vp.width}x${vp.height}-${theme}`, dir = path.join(OUT, tag);
  fs.mkdirSync(dir, { recursive: true });
  const { ctx, page, errors } = await phone(h.browser, { ...vp, theme });
  const shot = async name => page.screenshot({ path: path.join(dir, name + '.png') });
  await openApp(page, h.server.base);
  const slots = await page.evaluate(() => Briefing.state().slots);
  const res = { tag, issues: [], clamped: [], scrolls: [], small: [], errors };
  for (const id of slots) {
    const isStory = await page.evaluate(id => !!document.querySelector(`.slot[data-id="${CSS.escape(id)}"][data-story]`), id);
    await goSlot(page, id, isStory ? 300 : 200);
    if (isStory) {
      await page.waitForFunction(id => { const c = document.querySelector(`.card.story[data-story="${id}"]`); return !c.classList.contains('has-video') || c.classList.contains('started') || c.classList.contains('blocked'); }, id, { timeout: 6000 }).catch(() => {});
      await page.waitForTimeout(450);   // let the poster → video cross-fade finish
    }
    const r = await page.evaluate(checkSlot, id);
    for (const k of ['issues', 'clamped', 'scrolls', 'small']) res[k].push(...r[k]);
    if (SHOTS[id]) await shot(SHOTS[id]);
  }
  // a section carousel swiped to its first brief
  await goSlot(page, 'sec-world');
  await page.evaluate(() => { const car = document.querySelector('.slot[data-id="sec-world"] .hcar'); const s = car.querySelector('[data-slide="1"]'); car.scrollLeft = s.offsetLeft - 8; });
  await page.waitForTimeout(250); await shot('section-brief');
  // quiz after answering (a wrong answer shows both colours)
  await goSlot(page, 'quiz');
  await page.click('.slot[data-id="quiz"] .slide[data-slide="0"] .opt[data-j="0"]');
  await page.waitForTimeout(200);
  const q = await page.evaluate(checkSlot, 'quiz');
  res.issues.push(...q.issues.map(x => x + ' (after answering)'));
  await shot('quiz-answered');
  // explainer: top, scrolled, sources
  await goSlot(page, 's1');
  await page.click('.card.story[data-story="s1"] .read');
  await page.waitForTimeout(500); await shot('explainer-top');
  await page.evaluate(() => { const sc = document.getElementById('exScroll'); sc.scrollTop = sc.querySelector('[data-block="why_chain"]').offsetTop - 70; });
  await page.waitForTimeout(250); await shot('explainer-scrolled');
  await page.evaluate(() => { const sc = document.getElementById('exScroll'); sc.scrollTop = sc.querySelector('[data-block="misconception"]').offsetTop - 70; });
  await page.waitForTimeout(250); await shot('explainer-scrolled-2');
  // check yourself (answered), words to know (one opened), reel transcript (expanded)
  await page.evaluate(() => { const sc = document.getElementById('exScroll'); sc.scrollTop = sc.querySelector('.xs.check').offsetTop - 64; });
  await page.click('#ex .check .opt[data-j="1"]');
  await page.click('#ex .term[data-i="0"]');
  await page.evaluate(() => { document.querySelector('#ex details.trans').open = true; });
  await page.waitForTimeout(250); await shot('explainer-extras');
  await page.evaluate(() => { const sc = document.getElementById('exScroll'); sc.scrollTop = document.getElementById('ex-sources').offsetTop - 60; });
  await page.waitForTimeout(250); await shot('explainer-sources');
  const exIssues = await page.evaluate(() => {   // nothing in the reading sheet may stick out sideways
    const sc = document.getElementById('exScroll'); return sc.scrollWidth > sc.clientWidth + 1 ? [`explainer: sideways overflow ${sc.scrollWidth} > ${sc.clientWidth}`] : [];
  });
  res.issues.push(...exIssues);
  await page.click('#ex .ex-bar .ex-x'); await page.waitForTimeout(450);
  // calendar sheet (October has old digests, November the briefing)
  await page.click('#hdr .icb[data-act="calendar"]'); await page.waitForTimeout(600); await shot('calendar');
  await page.click('#sheet .x'); await page.waitForTimeout(400);
  // display sheet
  await page.click('#hdr .icb.aa'); await page.waitForTimeout(450); await shot('display');
  await page.click('#sheet .x'); await page.waitForTimeout(400);
  // play all
  await goSlot(page, 'cover');
  await page.click('.cv-play');
  await page.waitForFunction(() => document.getElementById('pa').classList.contains('started') || document.getElementById('pa').classList.contains('blocked'), null, { timeout: 6000 }).catch(() => {});
  await page.waitForTimeout(700); await shot('play-all');
  await page.click('#pa .pa-x'); await page.waitForTimeout(300);
  await ctx.close();
  report.push(res);
  return res;
}

async function contactSheet(tag, vp) {
  // Optional: tile the key screens into one image per viewport/theme for a quick visual review (needs ffmpeg).
  try {
    const ff = ffmpegBin(), dir = path.join(OUT, tag);
    const files = ['cover', 'before-you-scroll', 'story-video', 'story-no-video', 'section-intro', 'section-brief', 'quiet', 'also',
      'quiz-answered', 'developing', 'caught-up', 'explainer-top', 'explainer-scrolled', 'explainer-sources', 'calendar', 'play-all']
      .map(f => path.join(dir, f + '.png')).filter(f => fs.existsSync(f));
    if (files.length < 2) return;
    const cols = 4, W = vp.width, H = vp.height;            // screenshots are 2x; each tile is scaled back to 1x
    const args = ['-y', '-loglevel', 'error'];
    files.forEach(f => args.push('-i', f));
    const scaled = files.map((_, i) => `[${i}:v]scale=${W}:${H}[s${i}]`).join(';');
    const layout = files.map((_, i) => `${(i % cols) * W}_${Math.floor(i / cols) * H}`).join('|');
    args.push('-filter_complex', `${scaled};${files.map((_, i) => `[s${i}]`).join('')}xstack=inputs=${files.length}:layout=${layout}:fill=0x444444`,
      path.join(OUT, `_sheet-${tag}.png`));
    spawnSync(ff, args);
  } catch (e) { /* contact sheets are a nicety */ }
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const h = await setup();
  const report = [];
  let failed = false;
  try {
    const only = process.env.ONLY, themes = (process.env.THEMES || 'dark,light').split(',');
    for (const vp of VIEWPORTS) {
      if (only && only !== `${vp.width}x${vp.height}`) continue;
      for (const theme of themes) {
        const r = await shootOne(h, vp, theme, report);
        await contactSheet(r.tag, vp);
        const over = r.issues.length, ok = over <= vp.target && !r.errors.length;
        if (!ok) failed = true;
        console.log(`${ok ? 'PASS' : 'FAIL'}  ${r.tag.padEnd(16)} overflows: ${over} (target ≤${vp.target})  console errors: ${r.errors.length}  clamped: ${r.clamped.length}  scrolling briefs: ${r.scrolls.length}  small targets: ${r.small.length}`);
        r.issues.forEach(x => console.log('      ✗ ' + x));
        r.errors.forEach(x => console.log('      ! ' + x));
      }
    }
    // the old digest archive still renders (with its "New: The Briefing" link)
    const { ctx, page, errors } = await phone(h.browser, { width: 390, height: 664, theme: 'dark' });
    await page.goto(`${h.server.base}/dashboard/reels/digest.html#2026-10-30`);
    await page.waitForFunction(() => document.querySelector('#deck .slot'), null, { timeout: 15000 });
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(OUT, 'digest-390x664.png') });
    const hasLink = await page.evaluate(() => !!document.querySelector('a.newapp[href="./"]'));
    console.log(`${hasLink && !errors.length ? 'PASS' : 'FAIL'}  digest.html archive renders, banner link: ${hasLink}, console errors: ${errors.length}`);
    errors.forEach(x => console.log('      ! ' + x));
    if (!hasLink || errors.length) failed = true;
    await ctx.close();
  } finally {
    await teardown(h);
  }
  fs.writeFileSync(path.join(OUT, 'report.json'), JSON.stringify(report, null, 2));
  console.log(`\nScreenshots: ${path.relative(process.cwd(), OUT) || OUT}/<viewport>-<theme>/  ·  details: out/report.json`);
  process.exit(failed ? 1 : 0);
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) main().catch(e => { console.error(e); process.exit(1); });
