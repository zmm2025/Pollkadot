# Agent instructions

How the site, the data pipeline and the tests work is in [DEVELOPMENT.md](DEVELOPMENT.md). How to open a PR is in [CONTRIBUTING.md](CONTRIBUTING.md).

## Capturing the site

`npm run capture` screenshots the site as a visitor sees it, with no browser window and no computer use. It serves `main` (or any ref) and this checkout's `site/` side by side, and saves a **before** and an **after** of the same view:

```bash
npm run capture -- --name winner --hash 2024-pres --state '{"shade":"winner"}' --scheme both --keep
```

- `--hash` picks the contest, `--state` sets `pollkadot.st` fields (`metric`, `method`, `cmp`, `gran`, `shade`, `borders`, `contest`), and `--eval` runs any other page code first, such as `pollkadot.view = { k: 2, x: -300, y: -200 }; pollkadot.draw()`.
- `--scheme light|dark|both` sets the color scheme, `--size 390x844` shows the phone layout, and `--selector '#legcard'` or `--clip x,y,w,h` captures part of the page.
- `--before <ref>` changes what "before" serves. If `main` has moved on since the branch started, use `--before $(git merge-base HEAD main)`, so the before differs from the after only by this branch.
- `--only before|after` captures one side.
- `--keep` saves into the kept evidence folder (see below) and prints Markdown that's ready to paste. Without it, images go to `build/capture/` in this checkout, as scratch.

All the options are listed at the top of [scripts/capture.mjs](scripts/capture.mjs). It warns about page errors, so read its output.

## Images in chat

When a turn changes or reports on anything a visitor can see, the reply embeds before and after images, without being asked. Do this for each change, not one summary image. A text description doesn't replace an image.

- Capture the before from `main` with `npm run capture`, so it can be taken at any point in the turn. If a before image truly can't be captured, say so.
- Show every view the change affects: light and dark when it changes colors, the phone layout when it changes layout, and the shape, size or color settings it touches.
- Add `--keep` only for images you'll embed; everything else stays scratch.
- Chat reads an image from disk every time it's shown, so a deleted file shows up broken. Kept files live in the main checkout's `build/evidence/<worktree folder>/` (`build/evidence/main/` for the main checkout itself), which survives the worktree and is never cleaned up. Never delete them, and embed nothing from `build/capture/`, `build/sweep/`, a scratch folder or anywhere else in a worktree. Copy an image from anywhere else into the kept folder first, under a name no other file there has.
- Open each image before you embed it. A view that misses the change proves nothing.
- Subagents capture the evidence and return the absolute image paths. The parent thread embeds them.

T3 Code reads an embedded image from its file path every time it shows the message, and a deleted file can never be shown again. That's why kept files go to `build/evidence/` in the main checkout, which outlives the worktree, is ignored by git, and is never cleaned up. `--keep` never replaces an earlier file, since chat may already show it: it adds `-2`, `-3` and so on to the name instead.

## PR evidence

The user opens PRs with T3 Code's **Commit, push & PR** button, at any point and without asking you first. The button writes the PR text but can't capture or upload anything. So whenever a branch changes something a visitor can see, keep its evidence uploaded and current, as [CONTRIBUTING.md](CONTRIBUTING.md#pr-evidence) describes. A workflow then puts it in the PR's Preview section.

- Reuse the images you kept for chat (see [Images in chat](#images-in-chat)) instead of capturing them again.
- Pick whatever shows the change best, in any format:
  - before and after screenshots for how something looks, side by side in a table
  - a GIF for short motion, since it plays inline
  - an MP4 or WebM (for example from Playwright's `recordVideo`) for longer or smoother motion, marked `<!-- drop: <file> -->`, since GitHub only plays videos the user drags in
  - links for anything else, such as test output, frame times or changed data files
  - nothing, when there's nothing to see
- Write `build/pr-evidence/PREVIEW.md` and run `npm run pr-evidence` before your final reply. A file it names that isn't in that folder is copied from this worktree's kept images, so use their file names. Rerun it whenever later work changes what the evidence shows, and remove files that no longer apply.
- Evidence is stored under the branch's name. Never rename the branch, since T3 Code tracks the thread by it, and its evidence would be left behind.
- If the evidence has drop files, add a short note before your closing line that lists them, linked to their files in `build/pr-evidence/`, so the user can drag them into the PR once it's open.
