# FitFlow — Git workflow for this repository

**FitFlow** is the standard way humans and agents **fetch, branch, commit, push, pull, and merge** work in `wikitionary_to_mdx`. Follow it for every git operation unless the user gives explicit override instructions.

---

## What FitFlow stands for

| Step | Letter | Action |
|------|--------|--------|
| 1 | **F**etch | Sync with remote before starting work and again before push |
| 2 | **I**nspect | Review `status`, `diff`, and recent `log` before staging or committing |
| 3 | **T**arget | Use a short-lived branch with a clear prefix (never commit large binaries) |
| 4 | **F**ormat | Run quality checks when code changed (ruff, mypy, pytest as applicable) |
| 5 | **L**og | Write commits that explain **why**; use HEREDOC for messages |
| 6 | **O**rigin | Push feature branches only; protect `main` / `master` |
| 7 | **W**orkflow | Pull/rebase, push, open PR with `gh`, delete branch after merge |

---

## Branch naming (`Target`)

Create branches from updated `main` or `master`:

| Prefix | Use |
|--------|-----|
| `feat/` | New features (API, extraction, MDX export) |
| `fix/` | Bug fixes |
| `docs/` | Documentation only |
| `chore/` | Tooling, deps, CI, refactors without behavior change |
| `test/` | Test-only changes |

Examples: `feat/mdx-build-api`, `docs/fitflow`, `fix/zim-path-subdirs`.

Do **not** commit:

- `zim/**/*.zim` (local Kiwix archives; see `.gitignore`)
- `.venv/`, secrets (`.env`, keys), large build artifacts under `build/` unless explicitly requested

---

## Daily loop

### Start work

```bash
git fetch origin
git switch main   # or master
git pull --ff-only origin main
git switch -c feat/your-topic
```

Use `git pull --rebase origin main` on long-lived branches if the team prefers a linear history.

### While working

- Commit in **small, logical slices** (docs vs code vs tests when possible).
- **Only create commits when the user asks** (or when completing an explicit “commit this” task).
- Never `git commit --amend` unless user rules allow (hook fixes, unpushed agent commit, etc.).

### Before commit (`Inspect` + `Format`)

When Python/source changed:

```bash
uv sync
uv run ruff check src tests
uv run mypy src
uv run pytest
```

When only docs changed, quality commands are optional unless the user wants them.

**Inspect** (required for every commit):

```bash
git status
git diff
git diff --staged
git log -5 --oneline
```

### Commit (`Log`)

Stage deliberately — not `git add -A` blind if untracked large files might appear.

```bash
git add path/to/files
git commit -m "$(cat <<'EOF'
Short summary in imperative mood.

Optional one line of why or context.
EOF
)"
git status
```

If a **pre-commit hook** fails: fix the issue, **new commit** (do not amend a failed commit).

### Push (`Fetch` + `Origin`)

```bash
git fetch origin
git pull --rebase origin main   # or merge, match team habit
git push -u origin HEAD
```

- First push on a branch: always `-u origin HEAD`.
- **Never** `git push --force` to `main` / `master`.
- Force-push to a **personal feature branch** only when the user explicitly requests it.

### Pull requests (`Workflow`)

After push:

```bash
gh pr create --title "..." --body "$(cat <<'EOF'
## Summary
- ...

## Test plan
- [ ] ...
EOF
)"
```

Do **not** push to remote unless the user asked. Do **not** merge PRs unless asked.

---

## Remote and safety rules

These are **hard constraints** for agents and contributors:

| Rule | Detail |
|------|--------|
| No git config changes | Do not run `git config` locally or globally |
| No destructive history on main | No force-push, hard reset, or rebase of shared default branch |
| No hook bypass | No `--no-verify` unless user explicitly requests |
| No secrets in git | No `.env`, tokens, or credentials |
| Commit on request | Default: implement and leave uncommitted until user says commit |
| Update FitFlow status | After significant git ops, note branch/PR in chat if relevant |

---

## Troubleshooting

| Situation | FitFlow action |
|-----------|----------------|
| Push rejected (non-fast-forward) | `git fetch origin`, then `git pull --rebase` (or merge), fix conflicts, push again |
| Wrong files staged | `git restore --staged <file>`, re-run **Inspect** |
| Accidentally added a `.zim` | `git rm --cached path.zim`, ensure `.gitignore` has `zim/**/*.zim` |
| Need upstream branch | `git push -u origin HEAD` |
| Only docs commit | **Format** step can be skipped; **Inspect** still required |

---

## Agent checklist (copy before commit/push)

- [ ] **Fetch** — `git fetch origin` (and pull if pushing)
- [ ] **Inspect** — status, diff, log
- [ ] **Target** — correct branch name; no ZIM/secrets staged
- [ ] **Format** — ruff/mypy/pytest if code touched
- [ ] **Log** — HEREDOC commit message; user requested commit
- [ ] **Origin** — push to feature branch only; no force on main
- [ ] **Workflow** — `gh pr create` only if user asked for PR

---

## Related docs

- [README.md](../README.md) — project overview
- [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) — phase progress (update after landed work)
- Cursor rule: [.cursor/rules/fitflow-git.mdc](../.cursor/rules/fitflow-git.mdc)
