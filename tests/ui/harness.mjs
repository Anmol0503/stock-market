// Shared harness for The Briefing UI tests (dashboard/reels):
//  - buildSite(): a throwaway copy of the site in the temp folder: the app, the real old-digest archive, the fixtures
//    (tests/fixtures/briefing/, plus reels/ for the reel feed) and short generated test reels (ffmpeg, cached in out/.media/).
//    The real dashboard/briefing/ is never read or written.
//  - serve(): a small static server like GitHub Pages (correct types + Range requests, so video seeking works).
//  - phone(): a phone-sized Chrome context (playwright-core driving the installed Google Chrome).
// Env overrides: CHROME=/path/to/chrome  FFMPEG=/path/to/ffmpeg

import { chromium } from 'playwright-core';
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
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
// The reels-only feed (index.html) is tested on its own fixture day; the old day above stays in its archive.
export const RDATE = '2026-11-12';
export const RNOW = '2026-11-12T06:20';          // IST: the edition is out, some reels are still being made
export const RFIX = path.join(ROOT, 'tests', 'fixtures', 'briefing', 'reels');
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

/* ------------------------------------------------------------------ test media (generated once, cached in out/) */
export function ffmpegBin() {
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
    { file: 's1-spain-rail-signalling', color: '0x2f47c4', label: 'S1  SPAIN RAIL', tone: 440, d: 8 },
    { file: 's2-delhi-truck-ban', color: '0xb5541a', label: 'S2  DELHI SMOG', tone: 523, d: 8 },
    // 9:16 reels for the reels-only feed (12 s, so chapters have room)
    { file: 'r-s1-rbi-rate', color: '0x1f7a55', label: 'RBI RATE CUT', tone: 392, d: 12 },
    { file: 'r-s2-cyclone', color: '0x1d5f86', label: 'CYCLONE', tone: 494, d: 12 },
    { file: 'r-s4-chip-rules', color: '0x5b3fd6', label: 'CHIP RULES', tone: 587, d: 12 },
  ];
  for (const r of reels) {
    const mp4 = path.join(dir, r.file + '.mp4'), jpg = path.join(dir, r.file + '.jpg');
    if (!fs.existsSync(mp4)) {
      const vf = [
        `drawtext=${font}text='${r.label}':fontsize=78:fontcolor=white:x=(w-tw)/2:y=h*0.26`,
        `drawtext=${font}text='%{eif\\:t\\:d} s':fontsize=120:fontcolor=white@0.85:x=(w-tw)/2:y=h*0.36`,
        `drawtext=${font}text='Burned-in caption':fontsize=46:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=18:x=(w-tw)/2:y=h*0.5`,
      ].join(',');
      const a = spawnSync(ff, ['-y', '-loglevel', 'error', '-f', 'lavfi', '-i', `color=c=${r.color}:s=720x1280:d=${r.d}:r=30`,
        '-f', 'lavfi', '-i', `sine=frequency=${r.tone}:sample_rate=44100:duration=${r.d}`, '-vf', vf,
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
export function buildSite({ index, edition, videos, reels = false, rvideos } = {}) {
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
  if (reels) {                     // the reels-only feed: its index (latest = RDATE, older days incl. DATE) + day
    const b = path.join(dash, 'briefing'), rdir = path.join(dash, 'media', RDATE);
    fs.copyFileSync(path.join(RFIX, 'index.json'), path.join(b, 'index.json'));
    fs.copyFileSync(path.join(RFIX, `${RDATE}.json`), path.join(b, `${RDATE}.json`));
    fs.writeFileSync(path.join(b, 'videos', `${RDATE}.json`), rvideos ? JSON.stringify(rvideos) : fs.readFileSync(path.join(RFIX, `videos-${RDATE}.json`)));
    fs.mkdirSync(rdir, { recursive: true });
    for (const f of fs.readdirSync(media)) if (f.startsWith('r-')) fs.copyFileSync(path.join(media, f), path.join(rdir, f.slice(2)));
  }
  return tmp;
}
async function freePort() {
  return new Promise((res, rej) => { const s = net.createServer(); s.unref(); s.on('error', rej); s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); }); });
}
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml', '.mp4': 'video/mp4', '.webmanifest': 'application/manifest+json' };
/** A static server like GitHub Pages: correct types and Range requests (so video seeking works). In-process. */
export async function serve(dir) {
  const port = await freePort();
  const server = http.createServer((req, res) => {
    let rel = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    let file = path.join(dir, rel);
    if (!file.startsWith(dir)) { res.writeHead(403); res.end(); return; }
    try { if (fs.statSync(file).isDirectory()) file = path.join(file, 'index.html'); } catch (e) { /* 404 below */ }
    let st;
    try { st = fs.statSync(file); } catch (e) { res.writeHead(404, { 'Content-Type': 'text/plain' }); res.end('not found'); return; }
    const type = TYPES[path.extname(file).toLowerCase()] || 'application/octet-stream';
    const range = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range || '');
    if (range) {
      let start = range[1] === '' ? st.size - +range[2] : +range[1];
      let end = range[1] !== '' && range[2] !== '' ? Math.min(+range[2], st.size - 1) : st.size - 1;
      if (isNaN(start) || start < 0 || start >= st.size || end < start) { res.writeHead(416, { 'Content-Range': `bytes */${st.size}` }); res.end(); return; }
      res.writeHead(206, { 'Content-Type': type, 'Content-Length': end - start + 1, 'Content-Range': `bytes ${start}-${end}/${st.size}`, 'Accept-Ranges': 'bytes', 'Cache-Control': 'no-cache' });
      if (req.method === 'HEAD') { res.end(); return; }
      fs.createReadStream(file, { start, end }).pipe(res);
      return;
    }
    res.writeHead(200, { 'Content-Type': type, 'Content-Length': st.size, 'Accept-Ranges': 'bytes', 'Cache-Control': 'no-cache' });
    if (req.method === 'HEAD') { res.end(); return; }
    fs.createReadStream(file).pipe(res);
  });
  await new Promise(r => server.listen(port, '127.0.0.1', r));
  const proc = { kill: () => { server.closeAllConnections?.(); server.close(); } };
  return { port, proc, server, base: `http://127.0.0.1:${port}`, local: `http://localhost:${port}` };
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
