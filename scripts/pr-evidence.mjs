// PR evidence: screenshots, recordings and any other files that show what a branch changes. They're stored in git
// under refs/pr-evidence/, outside every branch, and .github/workflows/pr-evidence.yml embeds them in the PR's Preview
// section. See CONTRIBUTING.md.
//
//   npm run pr-evidence         uploads build/pr-evidence (PREVIEW.md plus its files) as this branch's evidence
//   npm run pr-evidence:fetch   downloads this branch's current evidence into build/pr-evidence
//
// --branch <name> uploads or fetches another branch's evidence instead of the checked-out one's, for testing.
import { execFileSync, spawnSync } from 'node:child_process';
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, relative } from 'node:path';
import { keptEvidenceDir } from './kept-evidence.mjs';

const PREVIEW = 'PREVIEW.md';
// GitHub rejects larger files in a push, and its drag-and-drop uploads stop at 10 MB on free plans.
const MAX_FILE_BYTES = 100 * 1024 * 1024;
const DROP_WARN_BYTES = 10 * 1024 * 1024;

class Failure extends Error {}

const args = process.argv.slice(2);
const fetchMode = args.includes('--fetch');
const branchArg = args.includes('--branch') ? args[args.indexOf('--branch') + 1] : null;
const unknown = args.filter((a, i) => a !== '--fetch' && a !== '--branch' && args[i - 1] !== '--branch');
if (unknown.length || (args.includes('--branch') && !branchArg)) {
  console.error('Usage: node scripts/pr-evidence.mjs [--fetch] [--branch <name>]');
  process.exit(2);
}

const checkout = execFileSync('git', ['rev-parse', '--show-toplevel'], { encoding: 'utf8' }).trim();
const dir = join(checkout, 'build', 'pr-evidence');

try {
  const branch = branchArg || git(['symbolic-ref', '--quiet', '--short', 'HEAD'], { allowFail: true }).trim();
  if (!branch) throw new Failure('HEAD is detached; check out the PR branch first.');
  const remote = remoteFor(branch);
  const ref = `refs/pr-evidence/branches/${branch}`;
  const current = remoteSha(remote, ref);
  if (fetchMode) download(remote, ref, current, branch);
  else upload(remote, ref, current, branch);
} catch (e) {
  if (!(e instanceof Failure)) throw e;
  console.error(`PR EVIDENCE: ERROR - ${e.message}`);
  process.exit(1);
}

function download(remote, ref, current, branch) {
  if (!current) throw new Failure(`${branch} has no evidence on ${remote} yet.`);
  if (existsSync(dir) && readdirSync(dir).length) {
    throw new Failure(`${dir} already has files. Delete it first, so nothing in it is lost.`);
  }
  git(['fetch', '--no-tags', '--quiet', remote, ref]);
  let count = 0;
  for (const entry of git(['ls-tree', '-r', '-z', '--full-tree', current]).split('\0').filter(Boolean)) {
    const sha = entry.split(/\s+/)[2];
    const path = entry.slice(entry.indexOf('\t') + 1);
    const target = join(dir, path);
    mkdirSync(dirname(target), { recursive: true });
    writeFileSync(target, gitBytes(['cat-file', 'blob', sha]));
    count++;
  }
  console.log(`PR EVIDENCE: FETCHED - ${count} files from ${remote} (${current.slice(0, 10)}) into ${dir}.`);
}

function upload(remote, ref, current, branch) {
  const preview = join(dir, PREVIEW);
  if (!existsSync(preview)) {
    throw new Failure(
      `${preview} is missing. Put the files there with a ${PREVIEW} that embeds them, or run ` +
        `npm run pr-evidence:fetch to start from this branch's current evidence.`,
    );
  }
  const markdown = readFileSync(preview, 'utf8');
  const drops = new Set(matches(markdown, /<!--\s*drop:\s*(.+?)\s*-->/g));
  const referenced = new Set([...localTargets(markdown), ...drops]);
  const kept = keptEvidenceDir();
  for (const path of referenced) {
    const copy = join(dir, path);
    const original = join(kept, path);
    if (!existsSync(copy) && existsSync(original) && statSync(original).isFile()) {
      mkdirSync(dirname(copy), { recursive: true });
      copyFileSync(original, copy);
    }
  }
  const files = new Map(
    listFiles(dir)
      .map(file => [relative(dir, file).replace(/\\/g, '/'), file])
      .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)),
  );

  const missing = [...referenced].filter(path => !files.has(path)).sort();
  if (missing.length) throw new Failure(`${PREVIEW} refers to files that aren't in ${dir}: ${missing.join(', ')}`);
  for (const [path, file] of files) {
    const size = statSync(file).size;
    if (size > MAX_FILE_BYTES)
      throw new Failure(`${path} is over 100 MB, which GitHub won't accept. Shorten or compress it.`);
    if (drops.has(path) && size > DROP_WARN_BYTES) {
      console.warn(`${path} is over 10 MB, so GitHub may refuse it as a drag-and-drop upload on a free plan.`);
    }
    if (path !== PREVIEW && !referenced.has(path)) {
      console.warn(`${path} isn't used in ${PREVIEW}. It's still uploaded, and listed under the Preview's file link.`);
    }
  }

  // Build the commit in a temporary index, so the checkout's own index and working tree are never touched.
  const index = join(tmpdir(), `pr-evidence-${process.pid}-${Date.now()}.index`);
  const env = { GIT_INDEX_FILE: index };
  try {
    const paths = [...files.keys()];
    // --no-filters stores each file's exact bytes, without line-ending conversion.
    const shas = git(['hash-object', '-w', '--no-filters', '--stdin-paths'], {
      env,
      input: paths.map(path => files.get(path)).join('\n') + '\n',
    })
      .trim()
      .split(/\r?\n/);
    const indexInfo = paths.map((path, i) => `100644 ${shas[i]}\t${path}`).join('\n') + '\n';
    git(['update-index', '--add', '--index-info'], { env, input: indexInfo });
    const tree = git(['write-tree'], { env }).trim();
    if (current) {
      git(['fetch', '--no-tags', '--quiet', remote, ref]);
      if (git(['rev-parse', `${current}^{tree}`]).trim() === tree) {
        console.log(`PR EVIDENCE: NO CHANGES - ${remote} already has these files (${current.slice(0, 10)}).`);
        return;
      }
    }
    const commit = git([
      'commit-tree',
      tree,
      '-m',
      `PR evidence for ${branch}`,
      ...(current ? ['-p', current] : []),
    ]).trim();
    git(['push', '--quiet', remote, `${commit}:${ref}`]);
    console.log(`PR EVIDENCE: UPLOADED - ${files.size} files to ${ref} on ${remote} (${commit.slice(0, 10)}).`);
  } finally {
    rmSync(index, { force: true });
  }
  refreshOpenPr(branch);
}

// The workflow fills the Preview when a PR opens or gets new commits. If the PR is already open, ask it to run now.
function refreshOpenPr(branch) {
  const view = run('gh', ['pr', 'view', branch, '--json', 'number,state']);
  const pr = view.status === 0 ? JSON.parse(view.output.toString('utf8')) : null;
  if (pr?.state !== 'OPEN') {
    console.log('The Preview section is filled in when the PR is opened.');
    return;
  }
  const result = run('gh', ['workflow', 'run', 'pr-evidence.yml', '-f', `pr=${pr.number}`]);
  if (result.status === 0) {
    console.log(`PR #${pr.number}'s Preview section updates in a minute.`);
  } else {
    console.log(
      `PR #${pr.number}'s Preview section updates on the branch's next push. The workflow couldn't be started now: ` +
        result.errors.trim(),
    );
  }
}

/** Paths in links, images and HTML src/href attributes that aren't URLs or anchors. */
function localTargets(markdown) {
  const targets = [
    ...matches(markdown, /\]\(\s*<([^>]+)>/g),
    ...matches(markdown, /\]\(\s*([^)\s<]+)/g),
    ...matches(markdown, /\b(?:src|href)\s*=\s*["']([^"']+)["']/g),
  ];
  return targets
    .filter(target => !/^([a-zA-Z][a-zA-Z0-9+.-]*:|#|\/)/.test(target))
    .map(target => {
      const path = target.replace(/^\.\//, '');
      try {
        return decodeURIComponent(path);
      } catch {
        return path;
      }
    });
}

function matches(text, pattern) {
  return [...text.matchAll(pattern)].map(match => match[1]);
}

function listFiles(folder) {
  if (!existsSync(folder)) return [];
  return readdirSync(folder, { withFileTypes: true }).flatMap(entry => {
    const path = join(folder, entry.name);
    return entry.isDirectory() ? listFiles(path) : entry.isFile() ? [path] : [];
  });
}

function remoteFor(branch) {
  for (const key of [`branch.${branch}.pushRemote`, 'remote.pushDefault', `branch.${branch}.remote`]) {
    const value = git(['config', '--get', key], { allowFail: true }).trim();
    if (value && value !== '.') return value;
  }
  return 'origin';
}

function remoteSha(remote, ref) {
  const line = git(['ls-remote', remote, ref])
    .split(/\r?\n/)
    .find(l => l.endsWith(`\t${ref}`));
  return line ? line.split('\t')[0] : null;
}

function git(gitArgs, options = {}) {
  return gitBytes(gitArgs, options).toString('utf8');
}

function gitBytes(gitArgs, { env, input, allowFail } = {}) {
  const result = run('git', gitArgs, { env, input });
  if (result.status !== 0) {
    if (allowFail) return Buffer.alloc(0);
    throw new Failure(`git ${gitArgs[0]} failed: ${result.errors.trim()}`);
  }
  return result.output;
}

/** Runs a command and returns its exit status, output bytes and error text. A missing command counts as a failure. */
function run(command, commandArgs, { env, input } = {}) {
  const result = spawnSync(command, commandArgs, {
    cwd: checkout,
    env: { ...process.env, ...env },
    input,
    maxBuffer: 1024 * 1024 * 1024,
  });
  return {
    status: result.error ? -1 : result.status,
    output: result.stdout ?? Buffer.alloc(0),
    errors: result.error ? result.error.message : (result.stderr?.toString('utf8') ?? ''),
  };
}
