// Screenshots + layout checks for the reels-only feed (dashboard/reels/index.html). Run: node shoot.mjs
//
// Builds the throwaway site (harness.mjs) with the reels fixture day (tests/fixtures/briefing/reels/), opens the feed
// on each phone size and checks:
//  - no text cut off or outside the screen (top bar, bottom bar, the slide on screen, every sheet);
//  - the 9:16 reel is never covered by the app's chrome (it sits in the letterbox) and never cropped;
//  - no console errors.
// Screenshots go to tests/ui/out/feed/<viewport>/. The old text app has its own tests (full-shoot.mjs).
//
// Env: ONLY=390x664 to run one size.

import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { OUT as OUT_ROOT, RDATE, RNOW, setup, teardown, phone } from './harness.mjs';

export const OUT = path.join(OUT_ROOT, 'feed');

export async function openFeed(page, base, { now = RNOW, hash = RDATE } = {}) {
  await page.goto(`${base}/dashboard/reels/?now=${encodeURIComponent(now)}#${hash}`);
  await page.waitForFunction(() => window.Feed && window.Feed.ready, null, { timeout: 20000 });
  await page.waitForTimeout(300);
}
/** Jump the feed to slide i (no smooth scroll) and wait for it to become the current one. */
export async function goTo(page, i) {
  await page.evaluate(i => window.Feed.go(i), i);
  await page.waitForFunction(i => window.Feed.state().cur === i, i, { timeout: 5000 });
  await page.waitForTimeout(250);
}
/** Wait until the reel on slide i has started playing (or was refused and shows the big ▶). */
export async function waitStarted(page, i) {
  await page.waitForFunction(i => { const s = document.querySelector(`.slide[data-i="${i}"]`); return s && (s.classList.contains('started') || s.classList.contains('blocked')); }, i, { timeout: 8000 });
}

/* runs in the page: text that is cut off, outside the screen, or chrome covering the reel */
export function layoutIssues(scope) {
  const out = [], vw = innerWidth, vh = innerHeight;
  const roots = [document.getElementById('top'), document.getElementById('bot'), document.getElementById('toast')];
  const cur = window.Feed.state().cur, slide = document.querySelector(`.slide[data-i="${cur}"]`);
  if (slide) roots.push(slide);
  const sh = document.getElementById('sheet'); if (!sh.hidden) roots.push(sh);
  const name = el => (el.id ? '#' + el.id : '') + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).join('.') : el.tagName.toLowerCase());
  const seen = new Set();
  for (const root of roots) {
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode: n => (n.nodeValue.trim() ? 1 : 2) });
    for (let n = w.nextNode(); n; n = w.nextNode()) {
      const el = n.parentElement;
      if (!el || el.closest('svg,[hidden]')) continue;
      const cs = getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) continue;
      let hiddenAnc = false;
      for (let a = el; a; a = a.parentElement) { const s = getComputedStyle(a); if (+s.opacity === 0 || s.visibility === 'hidden' || s.display === 'none') { hiddenAnc = true; break; } }
      if (hiddenAnc) continue;
      const rg = document.createRange(); rg.selectNodeContents(n);
      for (const r of [...rg.getClientRects()].filter(r => r.width > .5 && r.height > .5)) {
        let bad = null;
        const sc = el.closest('#sbody');                       // scrolled out of a sheet: reachable by scrolling
        if (sc) { const sr = sc.getBoundingClientRect(); if (r.top >= sr.bottom - 1 || r.bottom <= sr.top + 1) continue; }
        if (r.right > vw + 1 || r.left < -1 || r.bottom > vh + 1 || r.top < -1) bad = 'outside the screen';
        for (let a = el; !bad && a && a !== document.body; a = a.parentElement) {
          const acs = getComputedStyle(a);
          if (acs.overflowX === 'visible' && acs.overflowY === 'visible') continue;
          const ar = a.getBoundingClientRect(), tol = Math.max(2, r.height * .25);
          const cut = r.bottom > ar.bottom + tol || r.top < ar.top - tol || r.right > ar.right + 2 || r.left < ar.left - 2;
          if (!cut) continue;
          if (acs.textOverflow === 'ellipsis' || (acs.webkitLineClamp && acs.webkitLineClamp !== 'none')) break;   // intended
          if (a.id === 'sbody' || a.id === 'feed') break;                                                           // scrollers
          bad = `cut by ${name(a)}`;
        }
        const key = name(el) + n.nodeValue.trim().slice(0, 30);
        if (bad && !seen.has(key)) { seen.add(key); out.push(`${scope}: “${n.nodeValue.trim().replace(/\s+/g, ' ').slice(0, 40)}” ${bad}`); }
      }
    }
  }
  // the reel itself: chrome must not cover it; it must not be cropped (9:16, fully on screen)
  const fr = slide && slide.querySelector('.frame');
  if (fr && sh.hidden) {
    const r = fr.getBoundingClientRect();
    const covered = [...document.querySelectorAll('#top .pill:not([hidden]), #count, #bot .row, #track')].filter(e => e.offsetParent && getComputedStyle(e).visibility !== 'hidden').map(e => e.getBoundingClientRect())
      .filter(c => c.bottom > r.top + 1 && c.top < r.bottom - 1 && c.right > r.left + 1 && c.left < r.right - 1);
    if (covered.length) out.push(`${scope}: chrome covers the reel (${covered.length} element(s))`);
    if (r.top < -1 || r.bottom > vh + 1 || r.left < -1 || r.right > vw + 1) out.push(`${scope}: reel frame off screen`);
    if (Math.abs(r.width / r.height - 9 / 16) > 0.01) out.push(`${scope}: reel frame is not 9:16 (${Math.round(r.width)}×${Math.round(r.height)})`);
  }
  return out;
}

const VIEWPORTS = [
  { width: 390, height: 664 },     // iPhone 14 in Safari with toolbars
  { width: 375, height: 548 },     // iPhone SE in Safari
  { width: 412, height: 780 },     // large Android
  { width: 390, height: 844 },     // iPhone 14 full screen (home-screen app)
];

async function shootOne(h, vp) {
  const tag = `${vp.width}x${vp.height}`, dir = path.join(OUT, tag);
  fs.mkdirSync(dir, { recursive: true });
  const { ctx, page, errors } = await phone(h.browser, { ...vp, theme: 'dark' });
  const shot = n => page.screenshot({ path: path.join(dir, n + '.png') });
  const issues = [];
  const check = async scope => issues.push(...await page.evaluate(layoutIssues, scope));
  await openFeed(page, h.server.base);
  await waitStarted(page, 0);
  await page.waitForTimeout(500);
  await check('reel 1'); await shot('1-reel-playing');
  // chapter skip toast
  await page.click('.slide[data-i="0"] .zone.r'); await page.waitForTimeout(250); await shot('2-chapter-skip');
  // chapters sheet
  await page.click('#chap'); await page.waitForTimeout(450); await check('chapters sheet'); await shot('3-chapters');
  await page.click('#sheet .x'); await page.waitForTimeout(350);
  // sources sheet
  await page.click('#src'); await page.waitForTimeout(450); await check('sources sheet'); await shot('4-sources');
  await page.click('#sheet .x'); await page.waitForTimeout(350);
  // reel 2 (chapters estimated from the script)
  await goTo(page, 1); await waitStarted(page, 1).catch(() => {}); await page.waitForTimeout(400);
  await check('reel 2'); await shot('5-reel-2');
  // a reel still being made (s3: its rendered video is stale)
  await goTo(page, 2); await check('being made'); await shot('6-being-made');
  // paused state
  await goTo(page, 3); await waitStarted(page, 3).catch(() => {});
  await page.click('.slide[data-i="3"] .zone.c'); await page.waitForTimeout(700); await check('paused'); await shot('7-paused');
  // end slide
  const n = await page.evaluate(() => window.Feed.state().n);
  await goTo(page, n); await check('end'); await shot('8-caught-up');
  // pick a day
  await page.click('#dateBtn'); await page.waitForTimeout(450); await check('archive sheet'); await shot('9-archive');
  await page.click('#sheet .x'); await page.waitForTimeout(350);
  await ctx.close();
  return { tag, issues, errors };
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const h = await setup({ reels: true });
  let failed = false;
  try {
    for (const vp of VIEWPORTS) {
      if (process.env.ONLY && process.env.ONLY !== `${vp.width}x${vp.height}`) continue;
      const r = await shootOne(h, vp);
      const ok = !r.issues.length && !r.errors.length;
      if (!ok) failed = true;
      console.log(`${ok ? 'PASS' : 'FAIL'}  ${r.tag.padEnd(9)} layout issues: ${r.issues.length}  console errors: ${r.errors.length}`);
      r.issues.forEach(x => console.log('      ✗ ' + x));
      r.errors.forEach(x => console.log('      ! ' + x));
    }
  } finally {
    await teardown(h);
  }
  console.log(`\nScreenshots: ${path.relative(process.cwd(), OUT)}/<viewport>/`);
  process.exit(failed ? 1 : 0);
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) main().catch(e => { console.error(e); process.exit(1); });
