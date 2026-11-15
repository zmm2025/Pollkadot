// Screenshots the site before and after this checkout's changes, for chat and PR evidence (see AGENTS.md).
//
//   npm run capture -- --name winner --hash 2024-pres --state '{"shade":"winner"}' --scheme both --keep
//
// "before" is a git ref (main by default), read with git archive and served from memory, so it needs no checkout.
// "after" is this checkout's site/ as it is on disk, saved or not. Both are served on free local ports while it runs.
//
//   --name <base>          file names are <base>-<before|after>-<light|dark>.png (default: shot)
//   --hash <contest>       URL hash, such as 2024-pres or 2022-sen
//   --before <ref>         what "before" serves (default: main)
//   --only before|after    capture one side only
//   --scheme light|dark|both   prefers-color-scheme to emulate (default: light)
//   --state <json>         pollkadot.st fields to set before the shot, such as {"metric":"pop","method":"contig"};
//                          "contest" takes a contest key
//   --eval <js>            page code to run after that, such as "pollkadot.view = { k: 2, x: -300, y: -200 }; pollkadot.draw()"
//   --selector <css>       capture one element, such as #stage or #legcard
//   --clip x,y,w,h         capture a region of the page, in CSS pixels
//   --size WxH             viewport size (default: 1280x900; phones use 640 or less wide)
//   --scale <n>            device pixel ratio (default: 1)
//   --keep                 save into the kept evidence folder for chat, never replacing a file; otherwise build/capture
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, statSync } from 'node:fs';
import http from 'node:http';
import { extname, join, resolve, sep } from 'node:path';
import { chromium } from 'playwright';
import { keptEvidenceDir } from './kept-evidence.mjs';

const OPTIONS = ['name', 'hash', 'before', 'only', 'scheme', 'state', 'eval', 'selector', 'clip', 'size', 'scale'];
const opts = { name: 'shot', before: 'main', scheme: 'light', size: '1280x900', scale: '1', keep: false };
const argv = process.argv.slice(2);
for (let i = 0; i < argv.length; i++) {
  const key = argv[i].replace(/^--/, '');
  if (key === 'keep') opts.keep = true;
  else if (OPTIONS.includes(key) && i + 1 < argv.length) opts[key] = argv[++i];
  else fail(`Unknown option ${argv[i]}. See the top of scripts/capture.mjs for the options.`);
}
const [width, height] = opts.size.split('x').map(Number);
const clip = opts.clip?.split(',').map(Number);
const schemes = opts.scheme === 'both' ? ['light', 'dark'] : [opts.scheme];
const sides = opts.only ? [opts.only] : ['before', 'after'];
const state = opts.state ? JSON.parse(opts.state) : null;
if (!width || !height || (clip && (clip.length !== 4 || clip.some(isNaN)))) fail('--size takes WxH, --clip x,y,w,h.');
if (!sides.every(s => ['before', 'after'].includes(s))) fail('--only takes before or after.');
if (!schemes.every(s => ['light', 'dark'].includes(s))) fail('--scheme takes light, dark or both.');

const checkout = execFileSync('git', ['rev-parse', '--show-toplevel'], { encoding: 'utf8' }).trim();
const out = opts.keep ? keptEvidenceDir() : join(checkout, 'build', 'capture');
mkdirSync(out, { recursive: true });

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.json': 'application/json',
  '.png': 'image/png',
};

const servers = [];
const browser = await chromium.launch();
let errors = 0;
try {
  const sites = {};
  if (sides.includes('before')) sites.before = await serve(refReader(opts.before));
  if (sides.includes('after')) sites.after = await serve(dirReader(join(checkout, 'site')));
  for (const side of sides) {
    for (const scheme of schemes) {
      const file = target(`${opts.name}-${side}-${scheme}.png`);
      const problems = await shoot(sites[side] + (opts.hash ? `/#${opts.hash}` : '/'), scheme, file);
      errors += problems.length;
      for (const problem of problems) console.warn(`  ${side} ${scheme}: ${problem}`);
      console.log(opts.keep ? `![${opts.name}, ${side}, ${scheme}](${file.replace(/\\/g, '/')})` : file);
    }
  }
} finally {
  await browser.close();
  for (const server of servers) server.close();
}
if (errors) console.warn(`${errors} page errors: check the images before using them.`);

async function shoot(url, scheme, file) {
  const context = await browser.newContext({
    viewport: { width, height },
    deviceScaleFactor: Number(opts.scale),
    colorScheme: scheme,
  });
  const page = await context.newPage();
  const problems = [];
  page.on('pageerror', e => problems.push(e.message));
  page.on('console', m => m.type() === 'error' && problems.push(m.text()));
  await page.goto(url);
  await settle(page);
  if (state) {
    await page.evaluate(async s => {
      for (const [key, value] of Object.entries(s)) {
        pollkadot.st[key] = key === 'contest' ? pollkadot.D.contests.find(c => c.key === value) : value;
      }
      await pollkadot.go();
    }, state);
    await settle(page);
  }
  if (opts.eval) {
    await page.evaluate(`(async () => { ${opts.eval}; })()`);
    await settle(page);
  }
  if (opts.selector) await page.locator(opts.selector).screenshot({ path: file });
  else await page.screenshot({ path: file, clip: clip && { x: clip[0], y: clip[1], width: clip[2], height: clip[3] } });
  await context.close();
  return problems;
}

// The same wait the Playwright tests use: data loaded, no animation running and no loading spinner, then a frame.
async function settle(page) {
  await page.waitForFunction(
    () => window.pollkadot?.disp && !pollkadot.animating && document.getElementById('busy')?.style.display !== 'block',
    null,
    { timeout: 30000 },
  );
  await page.waitForTimeout(150);
}

// A file name in the output folder. Kept files never replace an earlier one, since chat may already show it.
function target(name) {
  let file = join(out, name);
  for (let n = 2; opts.keep && existsSync(file); n++) file = join(out, name.replace(/\.png$/, `-${n}.png`));
  return file;
}

function serve(read) {
  const server = http.createServer((req, res) => {
    let path = decodeURIComponent(new URL(req.url, 'http://localhost').pathname).replace(/^\/+/, '');
    if (path === '' || path.endsWith('/')) path += 'index.html';
    const body = read(path);
    res.writeHead(body ? 200 : 404, {
      'Content-Type': TYPES[extname(path)] ?? 'application/octet-stream',
      'Cache-Control': 'no-store',
    });
    res.end(body ?? '');
  });
  servers.push(server);
  return new Promise(done => server.listen(0, '127.0.0.1', () => done(`http://127.0.0.1:${server.address().port}`)));
}

function dirReader(root) {
  return path => {
    const file = resolve(root, path);
    if (!file.startsWith(root + sep) || !existsSync(file) || !statSync(file).isFile()) return null;
    return readFileSync(file);
  };
}

// Reads site/ at a git ref into memory from git archive's tar output, so nothing is checked out or written to disk.
function refReader(ref) {
  let sha;
  try {
    sha = execFileSync('git', ['rev-parse', '--verify', '--quiet', `${ref}^{commit}`], { encoding: 'utf8' }).trim();
  } catch {
    fail(`${ref} isn't a commit in this repository.`);
  }
  const tar = execFileSync('git', ['archive', '--format=tar', sha, '--', 'site'], { maxBuffer: 1024 * 1024 * 1024 });
  const files = new Map();
  let longName = null;
  for (let offset = 0; offset + 512 <= tar.length;) {
    const header = tar.subarray(offset, offset + 512);
    if (header.every(byte => byte === 0)) break;
    const field = (start, length) =>
      header
        .subarray(start, start + length)
        .toString('utf8')
        .replace(/\0[\s\S]*$/, '');
    const size = parseInt(field(124, 12).trim() || '0', 8);
    const type = String.fromCharCode(header[156]);
    const prefix = field(345, 155);
    let name = (prefix ? `${prefix}/` : '') + field(0, 100);
    const data = tar.subarray(offset + 512, offset + 512 + size);
    offset += 512 + Math.ceil(size / 512) * 512;
    // Pax headers: "g" is git archive's commit comment, "x" carries a path too long for the header.
    if (type === 'x') longName = /(?:^|\n)\d+ path=([^\n]*)\n/.exec(data.toString('utf8'))?.[1] ?? null;
    if (type === 'x' || type === 'g') continue;
    if (longName) [name, longName] = [longName, null];
    if (type === '0' || type === '\0') files.set(name.replace(/^site\//, ''), data);
  }
  console.log(`before: ${ref} (${sha.slice(0, 10)})`);
  return path => files.get(path) ?? null;
}

function fail(message) {
  console.error(`CAPTURE: ERROR - ${message}`);
  process.exit(2);
}
