// PW_DIR=<katalog z node_modules/playwright-core> node build/render-wideo.mjs
// Renderuje wideo.html klatka po klatce (30 fps), miksuje dźwięk i dokleja intro.
import { createRequire } from 'node:module';
import { spawn, execFileSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const require = createRequire(path.join(process.env.PW_DIR || process.cwd(), 'package.json'));
const { chromium } = require('playwright-core');
const B = path.dirname(fileURLToPath(import.meta.url));
const W = path.resolve(B, '..');
const INTRO = path.resolve(W, '../intro/intro.mp4');
const FPS = 30;

const browser = await chromium.launch({ executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', args: ['--force-color-profile=srgb'] });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
await page.goto(pathToFileURL(path.join(W, 'wideo.html')).href + '?capture');
await page.evaluate(() => document.fonts.ready);
const total = await page.evaluate(() => window.__duration);
const segments = await page.evaluate(() => window.__segments);
const imgs = await page.evaluate(() => [...new Set(Object.values(document.querySelectorAll('img')).map(i => i.src))]);

execFileSync('python3', [path.join(B, 'dzwiek.py'), JSON.stringify(segments), String(total)], { stdio: 'inherit' });

const main = path.join(B, 'glowna.mp4');
const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-i', '-',
  '-i', path.join(B, 'glowna.wav'), '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p',
  '-c:a', 'aac', '-b:a', '192k', '-shortest', main], { stdio: ['pipe', 'inherit', 'inherit'] });
const frames = Math.ceil(total * FPS);
for (let i = 0; i < frames; i++) {
  await page.evaluate(t => window.__render(t), i / FPS);
  if (i % 15 === 0) await page.waitForFunction(() => [...document.images].every(im => im.complete));
  const buf = await page.screenshot({ type: 'jpeg', quality: 93 });
  if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
  if (i % (FPS * 5) === 0) process.stdout.write(`\r${(i / FPS).toFixed(0)}/${total.toFixed(0)} s`);
}
ff.stdin.end();
await new Promise(r => ff.on('close', r));
await browser.close();

const out = path.join(W, 'naladuj-mape-polski-wideo.mp4');
execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', INTRO, '-i', main, '-filter_complex',
  '[0:v]fps=30,format=yuv420p,setsar=1[v0];[1:v]format=yuv420p,setsar=1[v1];[0:a]aresample=48000[a0];[1:a]aresample=48000[a1];[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]',
  '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
  '-movflags', '+faststart', out], { stdio: 'inherit' });
console.log('\n->', out);
