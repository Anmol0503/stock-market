// Screenshot + overflow check for the OLD text app (dashboard/reels/full.html: explainers, briefs, quiz).
// Run: node full-shoot.mjs. The reel feed (index.html) has its own tests: shoot.mjs and flows.mjs.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { OUT as OUT_ROOT, DATE, NOW, setup, teardown, phone, makeMedia, ffmpegBin } from './harness.mjs';
export { setup, teardown, phone, FIX, DATE, NOW } from './harness.mjs';
const OUT = path.join(OUT_ROOT, 'full');
export { OUT };

export async function openApp(page, base, { now = NOW, hash = DATE, query = '' } = {}) {
  await page.goto(`${base}/dashboard/reels/full.html?now=${encodeURIComponent(now)}${query}#${hash}`);
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
