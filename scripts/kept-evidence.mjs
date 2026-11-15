// Where images shown in chat are kept: build/evidence/<worktree folder> in the main checkout, or build/evidence/main
// for the main checkout itself. Chat reads an image from disk every time it shows it, so this folder has to outlive the
// worktree. Nothing ever deletes it (see AGENTS.md#images-in-chat).
import { execFileSync } from 'node:child_process';
import { basename, dirname, join, resolve } from 'node:path';

export function keptEvidenceDir() {
  const [common, top] = execFileSync(
    'git',
    ['rev-parse', '--path-format=absolute', '--git-common-dir', '--show-toplevel'],
    { encoding: 'utf8' },
  )
    .trim()
    .split(/\r?\n/);
  const main = basename(common) === '.git' ? dirname(common) : top;
  const isWorktree = resolve(main).toLowerCase() !== resolve(top).toLowerCase();
  return join(main, 'build', 'evidence', isWorktree ? basename(top) : 'main');
}
