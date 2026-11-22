// node build/render.mjs [--stills 0.5,2.5,...] [--fps 60] [--out intro.mp4] [--audio intro.wav]
// Wymaga playwright-core (np. PW_DIR=/sciezka/do/node_modules/..) i Google Chrome.
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';

const require = createRequire(path.join(process.env.PW_DIR || process.cwd(), 'package.json'));
const { chromium } = require('playwright-core');

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');
const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, all) => (v.startsWith('--') && a.push([v.slice(2), all[i + 1]]), a), []));
const fps = Number(args.fps || 60);
const W = Number(args.width || 1920), H = Number(args.height || 1080);

const browser = await chromium.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  args: ['--force-color-profile=srgb', '--hide-scrollbars']
});
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
await page.goto(pathToFileURL(path.join(root, 'intro.html')).href + '?capture=1');
await page.waitForFunction(() => window.__render);
const duration = await page.evaluate(() => window.__duration);

if (args.stills) {
  const outDir = args.dir || path.join(root, 'build', 'stills');
  fs.mkdirSync(outDir, { recursive: true });
  for (const t of args.stills.split(',').map(Number)) {
    await page.evaluate(t => window.__render(t), t);
    await page.screenshot({ path: path.join(outDir, `t${t.toFixed(2)}.png`) });
  }
  console.log('stills ->', outDir);
} else {
  const out = path.resolve(root, args.out || 'intro.mp4');
  const audio = args.audio === 'none' ? null : path.resolve(root, args.audio || 'intro.wav');
  const ff = spawn('ffmpeg', [
    '-y', '-loglevel', 'error',
    '-f', 'image2pipe', '-framerate', String(fps), '-i', '-',
    ...(audio ? ['-i', audio] : []),
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '14', '-pix_fmt', 'yuv420p', '-tune', 'grain',
    ...(audio ? ['-c:a', 'aac', '-b:a', '192k', '-shortest'] : []),
    '-movflags', '+faststart', out
  ], { stdio: ['pipe', 'inherit', 'inherit'] });
  const frames = Math.ceil(duration * fps);
  for (let i = 0; i <= frames; i++) {
    await page.evaluate(t => window.__render(t), i / fps);
    const buf = await page.screenshot({ type: 'png' });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (i % 60 === 0) process.stdout.write(`\r${i}/${frames}`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  console.log('\n->', out);
}
await browser.close();
