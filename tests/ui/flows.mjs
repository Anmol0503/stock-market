// Interaction flows for the reels-only feed (dashboard/reels/index.html). Run: node flows.mjs
// Same throwaway site + server + Chrome as shoot.mjs (fixtures only). Exit code 1 if any flow fails; every flow also
// fails on a console error. The old text app (full.html) has its own flows: full-flows.mjs.

import fs from 'node:fs';
import path from 'node:path';
import { setup, teardown, phone, RDATE, RFIX, DATE } from './harness.mjs';
import { openFeed, goTo, waitStarted } from './shoot.mjs';

const results = [];
function assert(c, msg) { if (!c) throw new Error(msg); }
async function flow(name, h, fn, { allowErrors = null } = {}) {
  const { ctx, page, errors } = await phone(h.browser, { width: 390, height: 664 });
  try {
    await fn(page, ctx);
    const errs = allowErrors ? errors.filter(e => !allowErrors.test(e)) : errors;
    assert(!errs.length, 'console errors:\n        ' + errs.join('\n        '));
    results.push({ name, ok: true }); console.log(`PASS  ${name}`);
  } catch (e) {
    results.push({ name, ok: false, err: e.message }); console.log(`FAIL  ${name}\n      ${e.message}`);
  } finally { await ctx.close(); }
}
const st = page => page.evaluate(() => window.Feed.state());
const vid = page => page.evaluate(() => { const V = window.Feed._video; return { t: V.currentTime, paused: V.paused, muted: V.muted, rate: V.playbackRate, src: V.currentSrc }; });
const chapLabel = page => page.evaluate(() => document.querySelector('#chap .cl').textContent);
/** Scroll the feed like a swipe (the browser's scroll-snap + IntersectionObserver do the rest). */
async function swipeTo(page, i) {
  await page.evaluate(i => { const f = document.getElementById('feed'), s = f.querySelector(`.slide[data-i="${i}"]`); f.scrollTo({ top: s.offsetTop, behavior: 'smooth' }); }, i);
  await page.waitForFunction(i => window.Feed.state().cur === i, i, { timeout: 5000 });
  await page.waitForTimeout(250);
}

async function main() {
  const h = await setup({ reels: true });
  const base = h.server.base;
  const manPath = path.join(h.dir, 'dashboard', 'briefing', 'videos', `${RDATE}.json`);
  const manifest = JSON.parse(fs.readFileSync(path.join(RFIX, `videos-${RDATE}.json`), 'utf8'));
  const writeManifest = m => fs.writeFileSync(manPath, JSON.stringify(m));
  try {
    await flow('Opens on reel 1 of 10, autoplays muted; a story without a reel script is skipped', h, async page => {
      await openFeed(page, base);
      await waitStarted(page, 0);
      const s = await st(page), v = await vid(page);
      assert(s.n === 10 && s.cur === 0 && s.hostId === 's1', JSON.stringify(s));
      assert(!v.paused && v.muted && /s1-rbi-rate\.mp4$/.test(v.src), JSON.stringify(v));
      assert((await page.textContent('#count')).trim() === '1 / 10', 'counter');
      assert(await page.evaluate(() => getComputedStyle(document.querySelector('.slide[data-i="0"] .sndpill')).display) === 'flex', '“Tap for sound” shows while muted');
    });

    await flow('Swipe to the next reel; when a reel ends the feed moves on by itself', h, async page => {
      await openFeed(page, base);
      await waitStarted(page, 0);
      await swipeTo(page, 1);
      await waitStarted(page, 1);
      let s = await st(page);
      assert(s.hostId === 's2' && /#2026-11-12\/s2$/.test(page.url()), 'swiped to s2: ' + JSON.stringify(s) + ' ' + page.url());
      await swipeTo(page, 0);                     // back to reel 1: it resumes where it was
      await page.evaluate(() => window.Feed._video.dispatchEvent(new Event('ended')));
      await page.waitForFunction(() => window.Feed.state().cur === 1, null, { timeout: 5000 });
      s = await st(page);
      assert(s.cur === 1 && s.hostId === 's2', 'auto-advanced: ' + JSON.stringify(s));
    });

    await flow('Sound: the button and the “Tap for sound” pill unmute; sound stays on for the next reel', h, async page => {
      await openFeed(page, base);
      await waitStarted(page, 0);
      await page.click('.slide[data-i="0"] .sndpill');
      let v = await vid(page);
      assert(!v.muted && await page.evaluate(() => document.documentElement.classList.contains('sound-on')), 'unmuted by the pill');
      await swipeTo(page, 1); await waitStarted(page, 1);
      v = await vid(page);
      assert(!v.muted && !v.paused, 'next reel plays with sound: ' + JSON.stringify(v));
      await page.click('#snd');
      v = await vid(page);
      assert(v.muted && (await page.getAttribute('#snd', 'aria-pressed')) === 'false', 'muted again by the button');
    });

    await flow('Speed: 1× → 1.25× → 1.5×, applied to the reel, kept after reload and on the next reel', h, async page => {
      await openFeed(page, base);
      await waitStarted(page, 0);
      assert((await page.textContent('#spd')).trim() === '1×', 'starts at 1×');
      await page.click('#spd'); await page.click('#spd');
      let v = await vid(page);
      assert(v.rate === 1.5 && (await page.textContent('#spd')).trim() === '1.5×' && await page.evaluate(() => localStorage.getItem('reelSpeed')) === '1.5', 'rate ' + v.rate);
      await page.reload();
      await page.waitForFunction(() => window.Feed && window.Feed.ready, null, { timeout: 20000 });
      await waitStarted(page, 0);
      assert((await page.textContent('#spd')).trim() === '1.5×' && (await vid(page)).rate === 1.5, 'remembered after reload');
      await swipeTo(page, 1); await waitStarted(page, 1);
      assert((await vid(page)).rate === 1.5, 'next reel keeps the speed');
      for (let k = 0; k < 3; k++) await page.click('#spd');
      assert((await page.textContent('#spd')).trim() === '1×' && (await vid(page)).rate === 1, 'wraps back to 1×');
    });

    await flow('Chapters: right edge skips forward, left edge goes back, the sheet jumps; the label follows', h, async page => {
      await openFeed(page, base);
      await waitStarted(page, 0);
      await page.evaluate(() => { window.Feed._video.currentTime = 0.2; });
      await page.waitForTimeout(150);
      assert(await chapLabel(page) === 'The question', 'starts at chapter 1');
      await page.click('.slide[data-i="0"] .zone.r');
      await page.waitForTimeout(250);
      let v = await vid(page);
      assert(v.t >= 1.5 && v.t < 2.6 && await chapLabel(page) === 'What happened', 'skipped to “What happened”: ' + v.t + ' ' + await chapLabel(page));
      assert(/What happened/.test(await page.textContent('.slide[data-i="0"] .ctoast')), 'chapter toast');
      await page.click('.slide[data-i="0"] .zone.l');               // within 3 s of the chapter start: previous chapter
      await page.waitForTimeout(250);
      v = await vid(page);
      assert(v.t < 1.4 && await chapLabel(page) === 'The question', 'back to chapter 1: ' + v.t);
      await page.click('#chap'); await page.waitForTimeout(400);
      const rows = await page.$$eval('#sheet .chs button', b => b.map(x => x.querySelector('.t').textContent));
      assert(rows.length === 7 && rows[4] === 'Worked example', 'chapters listed: ' + rows);
      assert((await st(page)).sheet === 'Chapters' && (await vid(page)).paused, 'sheet open pauses the reel');
      await page.click('#sheet .chs button[data-k="4"]');
      await page.waitForTimeout(450);
      v = await vid(page);
      assert(v.t >= 7 && v.t < 8.2 && !v.paused && (await st(page)).sheet === null && await chapLabel(page) === 'Worked example', 'jumped via the sheet: ' + JSON.stringify(v));
      assert((await page.$$('#track .ticks i')).length === 6, 'six chapter ticks on the progress bar');
    });

    await flow('Chapters without a manifest list are estimated from the script (s2)', h, async page => {
      await openFeed(page, base, { hash: `${RDATE}/s2` });
      await waitStarted(page, 1);
      const r = (await st(page)).reels.find(x => x.id === 's2');
      assert(r.chapters.length === 12 && r.chapters[0][1] === 'The question' && r.chapters[11][1] === 'Remember this', JSON.stringify(r.chapters));
      assert(r.chapters.every((c, k, a) => k === 0 || c[0] > a[k - 1][0]) && r.chapters[11][0] < 12, 'increasing, inside the reel');
    });

    await flow('Progress bar: dragging seeks', h, async page => {
      await openFeed(page, base);
      await waitStarted(page, 0);
      const box = await page.locator('#track .rail').boundingBox();
      await page.mouse.move(box.x + box.width * 0.75, box.y + box.height / 2);
      await page.mouse.down(); await page.mouse.up();
      await page.waitForTimeout(250);
      const v = await vid(page);
      assert(v.t > 8.5 && v.t < 10.5, 'seeked to ~75%: ' + v.t);
    });

    await flow('Tap the middle to pause (big ▶ shows), tap ▶ to play', h, async page => {
      await openFeed(page, base);
      await waitStarted(page, 0);
      await page.click('.slide[data-i="0"] .zone.c');
      await page.waitForTimeout(200);
      assert((await vid(page)).paused && await page.isVisible('.slide[data-i="0"] .bigplay'), 'paused with ▶');
      await page.click('.slide[data-i="0"] .bigplay');
      await page.waitForTimeout(300);
      assert(!(await vid(page)).paused && !(await page.isVisible('.slide[data-i="0"] .bigplay')), 'playing again');
    });

    await flow('Sources sheet: dated sources with excerpts and links, plus the text version', h, async page => {
      await openFeed(page, base);
      await page.click('#src'); await page.waitForTimeout(400);
      const s = await page.evaluate(() => ({
        title: document.getElementById('stitle').textContent,
        rows: [...document.querySelectorAll('#sheet .srcs a')].map(a => ({ href: a.href, target: a.target, rel: a.rel, pub: a.querySelector('.pub').textContent, dt: (a.querySelector('.dt') || {}).textContent })),
        txt: document.querySelector('#sheet a.txt').getAttribute('href') }));
      assert(s.title === 'Sources' && s.rows.length === 3, JSON.stringify(s));
      assert(s.rows.every(r => /^https:/.test(r.href) && r.target === '_blank' && /noopener/.test(r.rel) && r.dt), 'links + dates: ' + JSON.stringify(s.rows));
      assert(s.txt === `full.html#${RDATE}/s1`, 'text version link: ' + s.txt);
      await page.keyboard.press('Escape'); await page.waitForTimeout(350);
      assert((await st(page)).sheet === null, 'Escape closes the sheet');
    });

    await flow('A reel still being made turns into the video when the manifest updates', h, async page => {
      await openFeed(page, base);
      await swipeTo(page, 2);
      let s = await st(page);
      assert(!s.reels[2].video && await page.isVisible('.slide[data-i="2"] .frame.making'), 's3 shows “being made” (its video was for an older script)');
      assert(/being made/i.test(await page.textContent('.slide[data-i="2"] .mk')), 'being made text');
      const m2 = JSON.parse(JSON.stringify(manifest));
      m2.items.find(i => i.story === 's3').reel_hash = 'h03';
      m2.items.find(i => i.story === 's3').src = `../media/${RDATE}/s2-cyclone.mp4`;
      m2.items.find(i => i.story === 's3').poster = `../media/${RDATE}/s2-cyclone.jpg`;
      writeManifest(m2);
      const added = await page.evaluate(() => window.Feed.refresh());
      assert(added.join() === 's3', 'refresh reports s3: ' + added);
      await waitStarted(page, 2);
      s = await st(page);
      assert(s.hostId === 's3' && s.reels[2].video && /1 new reel ready/.test(await page.textContent('#toast')), JSON.stringify(s));
      writeManifest(manifest);
    });

    await flow('Old edition (no chapters, 5 stories) still plays, with parts from its scenes', h, async page => {
      await openFeed(page, base, { hash: DATE });
      await waitStarted(page, 0);
      const s = await st(page);
      assert(s.date === DATE && s.n === 5 && s.hostId === 's1', JSON.stringify(s));
      assert(s.reels[0].chapters.length > 2 && s.reels[0].chapters[0][1] === 'The question', 'parts estimated: ' + JSON.stringify(s.reels[0].chapters));
      assert((await page.textContent('#dateLbl')).trim() === 'Tue 3 Nov', 'date label');
      await page.click('.slide[data-i="0"] .zone.r');
      await page.waitForTimeout(250);
      assert((await vid(page)).t > 0.5, 'skips a part');
    });

    await flow('Pick a day: the date opens a list of days; choosing one loads its reels', h, async page => {
      await openFeed(page, base);
      await page.click('#dateBtn'); await page.waitForTimeout(400);
      const days = await page.$$eval('#sheet .days button', b => b.map(x => x.dataset.date));
      assert(days.join() === `${RDATE},${DATE}`, 'days: ' + days);
      await page.click(`#sheet .days button[data-date="${DATE}"]`);
      await page.waitForFunction(d => window.Feed.state().date === d && window.Feed.state().n === 5, DATE, { timeout: 5000 });
      await page.waitForTimeout(300);
      assert(new URL(page.url()).hash === `#${DATE}`, 'hash ' + page.url());
      // the end slide offers to go back to the first reel
      await goTo(page, 5);
      assert(/caught up/i.test(await page.textContent('.slide.end h2')) && await page.evaluate(() => document.body.classList.contains('at-end')), 'end slide');
      await page.click('.slide.end [data-act="go"]');
      await page.waitForFunction(() => window.Feed.state().cur === 0, null, { timeout: 5000 });
    });

    await flow('Deep link #<date>/<story> opens that reel', h, async page => {
      await openFeed(page, base, { hash: `${RDATE}/s4` });
      await waitStarted(page, 3);
      const s = await st(page);
      assert(s.cur === 3 && s.hostId === 's4' && (await page.textContent('#count')).trim() === '4 / 10', JSON.stringify(s));
    });

    await flow('Broken src falls back to fallback_src; if both fail the slide says so and offers the text', h, async page => {
      const m3 = JSON.parse(JSON.stringify(manifest));
      m3.items[0].src = `../media/${RDATE}/missing-1.mp4`; m3.items[0].fallback_src = `../media/${RDATE}/s1-rbi-rate.mp4`;
      m3.items[1].src = `../media/${RDATE}/missing-2.mp4`; m3.items[1].fallback_src = `../media/${RDATE}/missing-2b.mp4`;
      writeManifest(m3);
      await openFeed(page, base);
      await waitStarted(page, 0);
      assert(/s1-rbi-rate\.mp4$/.test((await vid(page)).src), 'plays the fallback');
      await swipeTo(page, 1);
      await page.waitForFunction(() => !!document.querySelector('.slide[data-i="1"] .frame.making'), null, { timeout: 8000 });
      assert(/couldn’t load/.test(await page.textContent('.slide[data-i="1"] .mk')) && await page.isVisible('.slide[data-i="1"] a.btn'), 'failure slide');
      writeManifest(manifest);
    }, { allowErrors: /404|Failed to load resource/ });

    await flow('Service worker: caches the new shell, never touches video', h, async page => {
      writeManifest(manifest);
      await page.goto(`${h.server.local}/dashboard/reels/?now=2026-11-12T06:20#${RDATE}`);
      await page.waitForFunction(() => window.Feed && window.Feed.ready, null, { timeout: 20000 });
      await page.evaluate(() => navigator.serviceWorker.ready);
      await page.waitForTimeout(600);
      const keys = await page.evaluate(async () => (await (await caches.open('briefing-v2')).keys()).map(r => new URL(r.url).pathname));
      for (const f of ['index.html', 'feed.js', 'feed.css', 'full.html']) assert(keys.some(k => k.endsWith('/reels/' + f)), 'precache missing ' + f);
      const viaSW = {};
      page.on('response', r => { const u = r.url(); if (/\.mp4/.test(u)) viaSW.mp4 = (viaSW.mp4 || false) || r.fromServiceWorker(); if (/briefing\/2026-11-12\.json/.test(u)) viaSW.json = r.fromServiceWorker(); });
      await page.reload();
      await page.waitForFunction(() => window.Feed && window.Feed.ready && navigator.serviceWorker.controller, null, { timeout: 20000 });
      await waitStarted(page, 0);
      assert(viaSW.json === true, 'edition JSON goes through the SW (network-first)');
      assert(viaSW.mp4 === false, 'video must bypass the SW');
    });
  } finally {
    await teardown(h);
  }
  const ok = results.filter(r => r.ok).length;
  console.log(`\n${ok}/${results.length} flows passed`);
  process.exit(ok === results.length ? 0 : 1);
}

main().catch(e => { console.error(e); process.exit(1); });
