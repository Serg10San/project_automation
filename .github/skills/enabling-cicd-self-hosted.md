---
name: enabling-cicd-self-hosted
description: >
  Use when enabling GitHub Actions CI/CD for an on-prem Intel repo or monorepo
  that deploys to a server (e.g. iredev01), or when moving from direct-on-server
  edits to a PR-based approval pipeline. Covers self-hosted runners, safe
  re-clone + parity verification against the running server, runner-based deploy,
  and gitignoring runtime artifacts. Invoke when "CI/CD", "pipeline", "runner",
  "deploy", "GitHub Actions", or "stop editing on the server" appear.
---

# Enabling CI/CD on Self-Hosted Runners (On-Prem Intel)

Applies when the running code lives on an on-prem server (a checkout of a GitHub
repo) and changes are currently made **directly on the server** with no review.
The goal: make GitHub the source of truth and insert a PR + automated-check gate
between "a change is made" and "the server runs it".

---

## Step 1 — Verify local matches the running server BEFORE changing anything

Never assume a re-clone is safe until you have proven the server has no
uncommitted code you would lose.

1. On the server checkout, run `git status --porcelain` and
   `git rev-list --left-right --count origin/<branch>...HEAD`.
2. If the only differences are **untracked** files (`??`), the committed code
   equals GitHub — safe. If tracked files are **modified/ahead**, STOP: capture
   those changes into a branch/PR first.
3. Clone the repo into a scratch dir and compare **tracked files** (`git ls-files`)
   against the server by hash. Raw-hash diffs with a **clean** server `git status`
   are almost always **CRLF/LF** normalization — confirm by comparing content with
   `\r` stripped; require **0 real content differences**.
4. Run the project's test suite in the clone (install `requirements-dev.txt`) and
   require green before replacing anything.

Only after parity + tests are green: archive the stale local copy and place the
clean clone.

---

## Step 2 — Decide single-app vs multi-repo

CI/CD is simplest against **one repo**. If the running app is already a monorepo
(sub-apps as subdirectories), keep it — do **not** split it. Document the layout
and use **path filters** so each sub-app's job runs only when its files change.
If the app is fragmented across several repos, either consolidate into one repo or
document the multi-repo build order explicitly.

---

## Step 3 — Register a self-hosted runner

GitHub-hosted runners cannot reach an on-prem server and violate zero-egress.
Register a **self-hosted runner on the deploy host** (or a box that can write to it):

1. Repo -> Settings -> Actions -> Runners -> "New self-hosted runner".
2. Run `config.cmd` with the registration token; install as a service
   (`svc.cmd install` / `svc.cmd start`) so it survives reboots.
3. Label it meaningfully (e.g. `self-hosted, windows, iredev01`) and target it in
   workflows with `runs-on: [self-hosted, iredev01]`.

---

## Step 4 — CI workflow (the approval gate)

`.github/workflows/ci.yml`, `on: [pull_request, push]`, `runs-on` the self-hosted
label. Run the project's own checks in order: **Black --check -> Ruff -> mypy ->
pytest** (add a coverage gate if desired). A failing check blocks merge. This is
what replaces "edit on the server and hope".

---

## Step 5 — CD workflow (runner-based deploy)

`.github/workflows/release.yml`, triggered on a version tag (`v*`) or a published
Release, `runs-on` the self-hosted label. Two common models:

- **git-pull deploy** (simplest for a script dir): on the runner,
  `git fetch; git reset --hard <approved-tag>` in the server path, then restart the
  service. The server folder becomes a managed checkout advanced only to approved
  commits.
- **artifact deploy**: `python -m build` -> install the wheel into the server path
  -> restart.

Use the Actions-provided `GITHUB_TOKEN` — no external egress, no stored secret.

---

## Step 6 — Gitignore runtime artifacts

Runtime files found untracked on the server (`*.db-journal`, `*-wal`, `*-shm`,
cache `*.json`, `tmp_*.txt`, scratch scripts) must be added to `.gitignore` so they
never enter the repo and never appear as false "dirty" state on the server.

---

## Result

Edit locally -> PR -> CI proves it -> merge -> CD (on the on-prem runner) advances
the server to the exact approved commit -> restart. You gain review, tests,
history, and one-command rollback (re-deploy an earlier tag).
