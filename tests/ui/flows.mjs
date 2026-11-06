// Interaction flows for The Briefing (dashboard/reels). Run: cd tests/ui && npm install && node flows.mjs
// Uses the same throwaway site + server + Chrome as shoot.mjs (fixtures only; the real dashboard/briefing/ is untouched).
// Exit code 1 if any flow fails. Every flow also fails on a console error (except the deliberate 404s in the
// fallback flow).

import fs from 'node:fs';
import path from 'node:path';
import { setup, teardown, phone, openApp, goSlot, FIX, DATE, OUT } from './shoot.mjs';

const results = [];
function assert(cond, msg) { if (!cond) throw new Error(msg); }
async function flow(name, h, fn, { allowErrors = null } = {}) {
  const { ctx, page, errors } = await phone(h.browser);
  try {
    await fn(page, ctx);
    const errs = allowErrors ? errors.filter(e => !allowErrors.test(e)) : errors;
    assert(!errs.length, 'console errors:\n        ' + errs.join('\n        '));
    results.push({ name, ok: true }); console.log(`PASS  ${name}`);
  } catch (e) {
    results.push({ name, ok: false, err: e.message }); console.log(`FAIL  ${name}\n      ${e.message}`);
  } finally { await ctx.close(); }
}
const state = page => page.evaluate(() => Briefing.state());
/** Wait until the deck and every carousel have stopped scrolling (smooth scrolls take a moment). */
async function settle(page) {
  let last = '';
  for (let i = 0; i < 40; i++) {
    await page.waitForTimeout(120);
    const pos = await page.evaluate(() => [document.getElementById('deck').scrollTop, ...[...document.querySelectorAll('.hcar')].map(c => c.scrollLeft)].join(','));
    if (pos === last) break;
    last = pos;
  }
  await page.waitForTimeout(150);
}
const exState = page => page.evaluate(() => {
  const ex = document.getElementById('ex');
  return { open: ex.classList.contains('open') && !ex.hidden, hash: location.hash, h: (ex.querySelector('.ex-h') || {}).textContent || '' };
});

async function main() {
  const h = await setup();
  const base = h.server.base;
  const manifestPath = path.join(h.dir, 'dashboard', 'briefing', 'videos', `${DATE}.json`);
  const manifest = JSON.parse(fs.readFileSync(path.join(FIX, `videos-${DATE}.json`), 'utf8'));
  const writeManifest = m => fs.writeFileSync(manifestPath, JSON.stringify(m));
  try {
    // 1 ------------------------------------------------------------------------------------------------
    await flow('“Before you scroll” rows jump to the right story card / brief', h, async page => {
      await openApp(page, base);
      const refs = await page.evaluate(() => [...document.querySelectorAll('.slot[data-list="changes"] [data-act="jump"]')].map(b => b.dataset.ref));
      assert(refs.length === 6, `expected 6 tappable rows, got ${refs.length}`);
      for (const ref of refs) {
        await page.evaluate(ref => { const s = document.querySelector(`[data-act="jump"][data-ref="${ref}"]`).closest('.slot'); document.getElementById('deck').scrollTop = s.offsetTop; }, ref);
        await page.waitForTimeout(200);
        await page.click(`[data-act="jump"][data-ref="${ref}"]`);
        await settle(page);
        const st = await page.evaluate(ref => {
          const cur = Briefing.state().cur, slot = document.querySelector(`.slot[data-id="${cur}"]`);
          const aligned = Math.abs(document.getElementById('deck').scrollTop - slot.offsetTop) < 3;
          const b = document.querySelector(`[data-brief="${ref}"]`), r = b && b.getBoundingClientRect();
          return { cur, aligned, briefOnScreen: r ? r.left >= -1 && r.right <= innerWidth + 1 : null };
        }, ref);
        if (/^s\d/.test(ref)) assert(st.cur === ref && st.aligned, `${ref}: landed on ${st.cur} (aligned ${st.aligned})`);
        else {
          const key = ref.replace(/^b-/, '').replace(/-\d+$/, '');
          assert(st.cur === 'sec-' + key && st.aligned && st.briefOnScreen, `${ref}: landed on ${st.cur}, brief on screen: ${st.briefOnScreen}`);
        }
      }
    });

    // 2 ------------------------------------------------------------------------------------------------
    await flow('Explainer opens from the card button, closes with ✕ and with Back', h, async page => {
      await openApp(page, base);
      await goSlot(page, 's1', 600);
      await page.click('.card.story[data-story="s1"] .read');
      await page.waitForTimeout(500);
      let st = await exState(page);
      assert(st.open && st.hash === `#${DATE}/s1` && /Spain/.test(st.h), `open: ${JSON.stringify(st)}`);
      const held = await page.evaluate(() => ({ held: Player._state().held, paused: Player._video.paused }));
      assert(held.held > 0 && held.paused, `the reel under the sheet should be paused: ${JSON.stringify(held)}`);
      await page.click('#ex .ex-bar .ex-x');
      await page.waitForTimeout(500);
      st = await exState(page);
      assert(!st.open && st.hash === `#${DATE}`, `after ✕: ${JSON.stringify(st)}`);
      await page.click('.card.story[data-story="s1"] .read');
      await page.waitForTimeout(500);
      await page.evaluate(() => history.back());
      await page.waitForTimeout(600);
      st = await exState(page);
      assert(!st.open && st.hash === `#${DATE}` && page.url().includes('/dashboard/reels/'), `after Back: ${JSON.stringify(st)} ${page.url()}`);
      assert((await state(page)).cur === 's1', 'should still be on the s1 card');
    });

    // 3 ------------------------------------------------------------------------------------------------
    await flow('Deep link #<date>/<storyId> opens the explainer over its card', h, async page => {
      await openApp(page, base, { hash: `${DATE}/s2` });
      let st = await exState(page);
      assert(st.open && /Delhi/.test(st.h) && st.hash === `#${DATE}/s2`, `deep link: ${JSON.stringify(st)}`);
      assert((await state(page)).cur === 's2', 'deck should sit on the s2 card behind the sheet');
      await page.click('#ex .ex-bar .ex-x');
      await page.waitForTimeout(500);
      st = await exState(page);
      assert(!st.open && st.hash === `#${DATE}` && page.url().includes('/dashboard/reels/'), `after close: ${JSON.stringify(st)}`);
      // section deep link
      await page.goto(`${base}/dashboard/reels/?now=2026-11-03T07:10#${DATE}/cricket`);
      await page.waitForFunction(() => window.Briefing && window.Briefing.ready);
      await page.waitForTimeout(300);
      assert((await state(page)).cur === 'sec-cricket', `#${DATE}/cricket should land on the cricket card`);
    });

    // 4 ------------------------------------------------------------------------------------------------
    await flow('Quiz: tapping an option reveals right/wrong colours and the explanation', h, async page => {
      await openApp(page, base);
      await goSlot(page, 'quiz');
      const q0 = '.slot[data-id="quiz"] .slide[data-slide="0"]';
      await page.click(`${q0} .opt[data-j="0"]`);           // wrong (answer is B)
      await page.waitForTimeout(200);
      let st = await page.evaluate(q0 => {
        const s = document.querySelector(q0), why = s.querySelector('.why');
        return { answered: s.classList.contains('answered'), wrong: s.querySelector('.opt[data-j="0"]').classList.contains('wrong'),
          right: s.querySelector('.opt[data-j="1"]').classList.contains('right'), whyShown: getComputedStyle(why).display !== 'none', whyText: why.textContent };
      }, q0);
      assert(st.answered && st.wrong && st.right && st.whyShown && /Both drivers/.test(st.whyText), JSON.stringify(st));
      await page.click(`${q0} .opt[data-j="2"]`, { force: true });   // options are disabled now; a second tap changes nothing
      st = await page.evaluate(q0 => document.querySelector(`${q0} .opt[data-j="2"]`).classList.contains('wrong'), q0);
      assert(!st, 'second answer should be ignored');
      await page.click(`${q0} [data-act="slide"]`);         // Next question →
      await page.waitForTimeout(700);
      const onScreen = await page.evaluate(() => { const r = document.querySelector('.slot[data-id="quiz"] .slide[data-slide="1"]').getBoundingClientRect(); return r.left >= -1 && r.right <= innerWidth + 1; });
      assert(onScreen, '“Next question” should bring question 2 on screen');
      const saved = await page.evaluate(() => Object.keys(localStorage).filter(k => k !== 'briefing_prefs'));
      assert(!saved.length, 'nothing but display prefs may be stored: ' + saved.join(','));
    });

    // 5 ------------------------------------------------------------------------------------------------
    await flow('Play all: segmented player auto-advances on ended, Read explainer, closes', h, async page => {
      await openApp(page, base);
      await page.click('.cv-play');
      await page.waitForFunction(() => Player._state().pa, null, { timeout: 5000 });
      let s = await page.evaluate(() => Player._state());
      assert(s.pa.ids.join() === 's1,s2' && s.pa.i === 0 && s.sound === true, JSON.stringify(s));
      assert(await page.evaluate(() => document.querySelectorAll('#pa .pa-bars i').length) === 2, 'two progress segments');
      await page.waitForFunction(() => document.getElementById('pa').classList.contains('started'), null, { timeout: 8000 });
      await page.evaluate(() => Player._video.dispatchEvent(new Event('ended')));
      await page.waitForTimeout(300);
      s = await page.evaluate(() => ({ ...Player._state(), done0: document.querySelector('#pa .pa-bars i').classList.contains('done'), h: document.querySelector('#pa .pa-h').textContent }));
      assert(s.pa && s.pa.i === 1 && s.done0 && /Delhi/.test(s.h), 'should advance to reel 2: ' + JSON.stringify(s));
      await page.evaluate(() => Player._video.dispatchEvent(new Event('ended')));
      await page.waitForTimeout(300);
      s = await page.evaluate(() => ({ ...Player._state(), hidden: document.getElementById('pa').hidden }));
      assert(!s.pa && s.hidden, 'should close after the last reel: ' + JSON.stringify(s));
      // Read explainer from inside the player
      await page.click('.cv-play');
      await page.waitForTimeout(400);
      await page.click('#pa .pa-act .read');
      await page.waitForTimeout(500);
      const ex = await exState(page);
      assert(ex.open && /Spain/.test(ex.h) && await page.evaluate(() => document.getElementById('pa').hidden), 'Read explainer should close the player and open s1');
    });

    // 5b -----------------------------------------------------------------------------------------------
    await flow('Speed button: cycles 1× → 1.25× → 1.5×, applies to the reel, survives reload and Play all', h, async page => {
      await openApp(page, base);
      const card = '.card.story[data-story="s1"]';
      await page.evaluate(c => { const s = document.querySelector(c).closest('.slot'); document.getElementById('deck').scrollTop = s.offsetTop; }, card);
      await settle(page);
      assert((await page.textContent(`${card} .vspd`)).trim() === '1×', 'starts at 1×');
      await page.click(`${card} .vspd`);
      await page.click(`${card} .vspd`);
      let s = await page.evaluate(c => ({ label: document.querySelector(c + ' .vspd').textContent, rate: Player._video.playbackRate,
                                          def: Player._video.defaultPlaybackRate, saved: localStorage.getItem('reelSpeed') }), card);
      assert(s.label === '1.5×' && s.rate === 1.5 && s.def === 1.5 && s.saved === '1.5', JSON.stringify(s));
      await page.reload();
      await page.waitForFunction(() => window.Briefing && window.Briefing.ready && document.querySelector('.card.story .vspd'), null, { timeout: 20000 });
      assert((await page.textContent(`${card} .vspd`)).trim() === '1.5×', 'remembered after reload');
      await page.click('.cv-play');
      await page.waitForFunction(() => Player._state().pa, null, { timeout: 5000 });
      await page.evaluate(() => Player._video.dispatchEvent(new Event('ended')));          // advance: new src
      await page.waitForTimeout(400);
      s = await page.evaluate(() => ({ label: document.querySelector('#pa .vspd').textContent, rate: Player._video.playbackRate, i: Player._state().pa.i }));
      assert(s.i === 1 && s.label === '1.5×' && s.rate === 1.5, 'Play all keeps the speed on the next reel: ' + JSON.stringify(s));
      for (let k = 0; k < 3; k++) await page.click('#pa .vspd');                             // 1.75, 2, back to 1
      s = await page.evaluate(() => ({ label: document.querySelector('#pa .vspd').textContent, rate: Player._video.playbackRate }));
      assert(s.label === '1×' && s.rate === 1, 'wraps back to 1×: ' + JSON.stringify(s));
    });

    // 6 ------------------------------------------------------------------------------------------------
    await flow('Stale reel (reel_hash mismatch) is ignored: s3 shows the gradient hero', h, async page => {
      const urls = [];
      page.on('request', r => urls.push(r.url()));
      await openApp(page, base);
      await goSlot(page, 's3', 900);
      const st = await page.evaluate(() => {
        const c = document.querySelector('.card.story[data-story="s3"]');
        return { hasVideo: c.classList.contains('has-video'), hero: !!c.querySelector('.st-hero .big'), video: !!c.querySelector('video'),
          poster: !!c.querySelector('.st-poster'), dek: !!c.querySelector('.st-d'), list: Player.list() };
      });
      assert(!st.hasVideo && st.hero && !st.video && !st.poster && st.dek, JSON.stringify(st));
      assert(st.list.join() === 's1,s2', 'available reels should be s1,s2: ' + st.list);
      assert(!urls.some(u => /s3-stale/.test(u)), 'the stale reel must never be requested');
    });

    // 7 ------------------------------------------------------------------------------------------------
    await flow('Calendar: briefing days marked, old digest days open digest.html#<date>', h, async page => {
      await openApp(page, base);
      await page.click('#hdr .icb[data-act="calendar"]');
      await page.waitForTimeout(700);
      const marks = await page.evaluate(() => ({
        complete: !!document.querySelector('#sheet button.day.has[data-date="2026-11-03"]:not(.part)'),
        partial: !!document.querySelector('#sheet button.day.has.part[data-date="2026-11-02"]'),
        oldNov1: !!document.querySelector('#sheet a.day.old[href="digest.html#2026-11-01"]'),
      }));
      assert(marks.complete && marks.partial && marks.oldNov1, JSON.stringify(marks));
      await page.click('#sheet [data-act="cal-move"][data-v="-1"]');
      await page.waitForTimeout(200);
      const link = '#sheet a.day.old[href="digest.html#2026-10-30"]';
      assert(await page.$(link), 'October should show the old digest for 30 Oct');
      await Promise.all([page.waitForURL(/digest\.html#2026-10-30/), page.click(link)]);
      await page.waitForFunction(() => typeof DATE !== 'undefined' && DATE === '2026-10-30', null, { timeout: 15000 });
      const d = await page.evaluate(() => ({ sub: document.getElementById('sub').textContent, link: !!document.querySelector('a.newapp[href="./"]') }));
      assert(/30/.test(d.sub) && d.link, 'digest page should show 30 Oct with the “New: The Briefing” link: ' + JSON.stringify(d));
    });

    // 8 ------------------------------------------------------------------------------------------------
    await flow('“Running late” banner after 06:45 IST when the newest edition is from yesterday', h, async page => {
      await openApp(page, base, { now: '2026-11-04T07:00', hash: '' });
      let late = await page.evaluate(() => { const el = document.getElementById('late'); return { shown: !el.hidden, text: el.textContent.trim() }; });
      assert(late.shown && /running late/.test(late.text) && /Tue 3 Nov/.test(late.text), JSON.stringify(late));
      assert((await state(page)).date === '2026-11-03', 'should show the latest edition (3 Nov)');
      await page.click('#late [data-act="late-x"]');
      assert(await page.evaluate(() => document.getElementById('late').hidden), 'banner can be dismissed');
      for (const now of ['2026-11-04T06:30', '2026-11-03T07:10']) {
        await openApp(page, base, { now, hash: '' });
        late = await page.evaluate(() => !document.getElementById('late').hidden);
        assert(!late, `no banner expected at ${now}`);
      }
    });

    // 9 ------------------------------------------------------------------------------------------------
    await flow('Polling: a reel that appears later attaches without disturbing the card being read', h, async page => {
      writeManifest(manifest);
      await openApp(page, base);
      await goSlot(page, 's4', 300);
      const m2 = JSON.parse(JSON.stringify(manifest));
      m2.items.push({ story: 's4', reel_hash: 'hash4', src: `../media/${DATE}/s2-delhi-truck-ban.mp4`, fallback_src: null, poster: `../media/${DATE}/s2-delhi-truck-ban.jpg`, duration_s: 8, narrated: true });
      writeManifest(m2);
      const added = await page.evaluate(() => Player.refresh());
      assert(added.join() === 's4', 'refresh should report s4: ' + added);
      let st = await page.evaluate(() => { const c = document.querySelector('.card.story[data-story="s4"]'); return { hasVideo: c.classList.contains('has-video'), dek: !!c.querySelector('.st-d') }; });
      assert(!st.hasVideo && st.dek, 'the card on screen must not change under the reader: ' + JSON.stringify(st));
      await goSlot(page, 's5', 400);
      st = await page.evaluate(() => ({ hasVideo: document.querySelector('.card.story[data-story="s4"]').classList.contains('has-video'), cover: document.querySelector('.cv-play small').textContent }));
      assert(st.hasVideo && /3 reels/.test(st.cover), 'after leaving, s4 gets its reel and Play all counts 3: ' + JSON.stringify(st));
      const polls = await page.evaluate(() => { const n = Briefing.state().now; return n; });
      assert(polls > 0, 'clock pinned');
      writeManifest(manifest);
    });

    // 10 -----------------------------------------------------------------------------------------------
    await flow('Broken src falls back to fallback_src; if both fail the card shows the gradient hero', h, async page => {
      const m3 = JSON.parse(JSON.stringify(manifest));
      m3.items[0].src = `../media/${DATE}/missing-s1.mp4`; m3.items[0].fallback_src = `../media/${DATE}/s1-spain-rail-signalling.mp4`;
      m3.items[1].src = `../media/${DATE}/missing-s2.mp4`; m3.items[1].fallback_src = `../media/${DATE}/missing-s2b.mp4`;
      writeManifest(m3);
      await openApp(page, base);
      await goSlot(page, 's1', 300);
      await page.waitForFunction(() => document.querySelector('.card.story[data-story="s1"]').classList.contains('started'), null, { timeout: 8000 });
      const src1 = await page.evaluate(() => Player._video.currentSrc);
      assert(/s1-spain-rail-signalling\.mp4$/.test(src1), 's1 should play its fallback: ' + src1);
      await goSlot(page, 's2', 300);
      await page.waitForFunction(() => !document.querySelector('.card.story[data-story="s2"]').classList.contains('has-video'), null, { timeout: 8000 });
      const st = await page.evaluate(() => { const c = document.querySelector('.card.story[data-story="s2"]'); return { hero: !!c.querySelector('.st-hero'), dek: !!c.querySelector('.st-d'), list: Player.list() }; });
      assert(st.hero && st.dek && st.list.join() === 's1', 'both sources failed → gradient hero: ' + JSON.stringify(st));
      writeManifest(manifest);
    }, { allowErrors: /404|Failed to load resource/ });

    // 11 -----------------------------------------------------------------------------------------------
    await flow('Service worker: caches the shell + digest.html, never touches video, works offline', h, async (page, ctx) => {
      writeManifest(manifest);
      const local = h.server.local;              // localhost (not 127.0.0.1): the app only registers the SW on https/localhost
      await page.goto(`${local}/dashboard/reels/?now=2026-11-03T07:10#${DATE}`);
      await page.waitForFunction(() => window.Briefing && window.Briefing.ready, null, { timeout: 20000 });
      await page.evaluate(() => navigator.serviceWorker.ready);
      await page.waitForTimeout(500);
      const cache = await page.evaluate(async () => {
        const names = await caches.keys(), c = await caches.open('briefing-v1'), keys = (await c.keys()).map(r => new URL(r.url).pathname);
        return { names, keys };
      });
      assert(cache.names.join() === 'briefing-v1', 'only briefing-v1 should exist: ' + cache.names);
      for (const f of ['index.html', 'app.css', 'app.js', 'player.js', 'digest.html', 'manifest.json']) assert(cache.keys.some(k => k.endsWith('/reels/' + f)), 'precache missing ' + f);
      const viaSW = {};
      page.on('response', r => { const u = r.url(); if (/\.mp4/.test(u)) viaSW.mp4 = (viaSW.mp4 || false) || r.fromServiceWorker(); if (/briefing\/2026-11-03\.json/.test(u)) viaSW.json = r.fromServiceWorker(); });
      await page.reload();
      await page.waitForFunction(() => window.Briefing && window.Briefing.ready && navigator.serviceWorker.controller, null, { timeout: 20000 });
      await goSlot(page, 's1', 300);
      await page.waitForFunction(() => document.querySelector('.card.story[data-story="s1"]').classList.contains('started'), null, { timeout: 8000 });
      assert(viaSW.json === true, 'edition JSON should go through the SW (network-first)');
      assert(viaSW.mp4 === false, 'video must bypass the SW');
      await ctx.setOffline(true);
      await page.reload();
      await page.waitForFunction(() => window.Briefing && window.Briefing.ready, null, { timeout: 20000 });
      const off = await state(page);
      await ctx.setOffline(false);
      assert(off.date === DATE && off.slots.length > 10, 'offline reload should still show the cached edition: ' + JSON.stringify(off).slice(0, 200));
    }, { allowErrors: /net::ERR_INTERNET_DISCONNECTED|Failed to load resource|Failed to fetch/ });

    // 12 -----------------------------------------------------------------------------------------------
    const pub = path.join(h.dir, 'dashboard', 'briefing');
    const fixIndex = fs.readFileSync(path.join(FIX, 'index.json'), 'utf8');
    const fixEdition = JSON.parse(fs.readFileSync(path.join(FIX, `${DATE}.json`), 'utf8'));
    const shots = path.join(OUT, 'flows');
    fs.mkdirSync(shots, { recursive: true });
    await flow('Refresh loads a newer edition and clears the running-late banner', h, async page => {
      await openApp(page, base, { now: '2026-11-04T07:00', hash: '' });
      assert(await page.evaluate(() => !document.getElementById('late').hidden), 'banner expected before the new edition');
      await page.screenshot({ path: path.join(shots, 'running-late.png') });
      const e2 = { ...JSON.parse(JSON.stringify(fixEdition)), date: '2026-11-04', edition: 'Morning · 4:48 AM' };
      e2.cover.top_line = 'A newer edition, published while the page was open.';
      fs.writeFileSync(path.join(pub, '2026-11-04.json'), JSON.stringify(e2));
      const ix = JSON.parse(fixIndex);
      ix.latest = '2026-11-04';
      ix.days.unshift({ date: '2026-11-04', edition: e2.edition, status: 'complete', stories: 5, briefs: 21, top_line: e2.cover.top_line });
      fs.writeFileSync(path.join(pub, 'index.json'), JSON.stringify(ix));
      await page.click('#refresh');
      await page.waitForFunction(() => Briefing.state().date === '2026-11-04', null, { timeout: 8000 });
      await page.waitForTimeout(300);
      const st = await page.evaluate(() => ({ late: !document.getElementById('late').hidden, top: document.querySelector('.cv-top').textContent, hash: location.hash }));
      assert(!st.late && /newer edition/.test(st.top) && st.hash === '#2026-11-04', JSON.stringify(st));
    }, { allowErrors: /404|Failed to load resource/ });   // no videos manifest for the new day yet
    fs.writeFileSync(path.join(pub, 'index.json'), fixIndex);
    fs.rmSync(path.join(pub, '2026-11-04.json'), { force: true });

    // 13 -----------------------------------------------------------------------------------------------
    await flow('A partial edition shows its status banner and notes on the cover', h, async page => {
      const e3 = { ...JSON.parse(JSON.stringify(fixEdition)), date: '2026-11-02', status: 'partial', edition: 'Morning · 4:49 AM',
        notes: ['Only 3 of 5 big stories passed fact checks before the 05:40 deadline.'] };
      e3.stories = e3.stories.slice(0, 3);
      fs.writeFileSync(path.join(pub, '2026-11-02.json'), JSON.stringify(e3));
      await openApp(page, base, { hash: '2026-11-02' });
      const st = await page.evaluate(() => ({ banner: (document.querySelector('.cv-status') || {}).textContent || '', greet: document.querySelector('.cv-greet').textContent, sub: document.getElementById('sub').textContent, stories: document.querySelectorAll('.card.story').length }));
      assert(/Partial edition/.test(st.banner) && /3 of 5/.test(st.banner) && /Yesterday/.test(st.greet) && /Partial/.test(st.sub) && st.stories === 3, JSON.stringify(st));
      await page.screenshot({ path: path.join(shots, 'partial-edition-cover.png') });
      await page.setViewportSize({ width: 375, height: 548 });
      await page.waitForTimeout(400);
      await page.screenshot({ path: path.join(shots, 'partial-edition-cover-375x548.png') });
    }, { allowErrors: /404|Failed to load resource/ });   // no videos manifest for that day
    fs.rmSync(path.join(pub, '2026-11-02.json'), { force: true });

    // 14 -----------------------------------------------------------------------------------------------
    await flow('No index yet: friendly empty state that links to the old digest', h, async page => {
      fs.renameSync(path.join(pub, 'index.json'), path.join(pub, 'index.off'));
      try {
        await page.goto(`${base}/dashboard/reels/?now=2026-11-03T05:00`);
        await page.waitForFunction(() => window.Briefing && window.Briefing.ready, null, { timeout: 15000 });
        const st = await page.evaluate(() => ({ text: document.getElementById('deck').textContent, link: !!document.querySelector('#deck a[href="digest.html"]') }));
        assert(/5:40 AM/.test(st.text) && st.link, JSON.stringify(st));
      } finally { fs.renameSync(path.join(pub, 'index.off'), path.join(pub, 'index.json')); }
    }, { allowErrors: /404|Failed to load resource/ });

    // 15 -----------------------------------------------------------------------------------------------
    await flow('Watch from the explainer → Read explainer → close: autoplay resumes on the card', h, async page => {
      await openApp(page, base);
      await goSlot(page, 's1', 400);
      await page.click('.card.story[data-story="s1"] .read');
      await page.waitForTimeout(500);
      await page.click('#ex .ex-watch');
      await page.waitForFunction(() => Player._state().pa, null, { timeout: 5000 });
      await page.click('#pa .pa-act .read');
      await page.waitForTimeout(500);
      let st = await page.evaluate(() => ({ held: Player._state().held, open: !document.getElementById('ex').hidden, hash: location.hash }));
      assert(st.held === 1 && st.open && st.hash === `#${DATE}/s1`, 'one hold while the sheet is open: ' + JSON.stringify(st));
      await page.click('#ex .ex-bar .ex-x');
      await page.waitForTimeout(700);
      st = await page.evaluate(() => ({ held: Player._state().held, paused: Player._video.paused, hash: location.hash, url: location.pathname }));
      assert(st.held === 0 && !st.paused && st.hash === `#${DATE}` && /reels/.test(st.url), 'after closing, the s1 reel plays again: ' + JSON.stringify(st));
    });
  } finally {
    writeManifest(manifest);
    await teardown(h);
  }
  const failed = results.filter(r => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} flows passed`);
  process.exit(failed.length ? 1 : 0);
}

main().catch(e => { console.error(e); process.exit(1); });
