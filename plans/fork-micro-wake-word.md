# Plan: Fork `micro-wake-word` to Gabriel-Lewis

## Context

`train_microwakeword_macos.sh` clones `https://github.com/TaterTotterson/micro-wake-word.git` into `deps/micro-wake-word` at runtime and installs it editable. We cannot point at `kahrendt/microWakeWord` (the original upstream) directly because TaterTotterson's fork carries Apple Silicon patches we depend on:

- Fix TFLite quantization metadata (affects output model correctness)
- Fallback for `Interpreter` import (Apple Silicon TFLite compatibility)
- `audio_utils` compatibility with `pymicro-features`

This plan moves that fork under `Gabriel-Lewis/` so the trainer no longer pulls from TaterTotterson, while preserving the Apple Silicon patches.

## Affected files

- `train_microwakeword_macos.sh` (line 239): the `git clone` URL
- `CLAUDE.md`: the directory description mentions "Apple Silicon fork, auto-updated"
- `migration-plan.md`: top-level migration tracker (mark item as done)

No other code references the repo URL.

---

## Phase 1 — Manual GitHub steps (user)

These cannot be automated; you must do them in a browser while signed in to GitHub as `Gabriel-Lewis`.

### Step 1: Fork the repo

1. Open https://github.com/TaterTotterson/micro-wake-word
2. Click **Fork** (top-right).
3. Owner: `Gabriel-Lewis`. Repository name: `micro-wake-word`. Leave "Copy the main branch only" **checked**.
4. Click **Create fork**.
5. Confirm the new repo exists at https://github.com/Gabriel-Lewis/micro-wake-word and that the default branch is `main`.

### Step 2: (Optional but recommended) Capture upstream HEAD for the record

So we can prove parity later, note the upstream commit SHA at fork time:

1. Open https://github.com/TaterTotterson/micro-wake-word/commits/main
2. Copy the SHA of the top commit.
3. Paste it into the chat when you return — the LLM will record it in the PR description.

### Step 3: Tell the LLM you're done

Return to Claude Code and say:
> "Fork created at Gabriel-Lewis/micro-wake-word, upstream HEAD was `<sha>`. Proceed with Phase 2."

---

## Phase 2 — Code changes (LLM walkthrough)

> **LLM instructions:** Do not start Phase 2 until the user confirms the fork exists. Verify it first with `gh repo view Gabriel-Lewis/micro-wake-word --json defaultBranchRef,pushedAt`. If the repo does not exist or default branch is not `main`, stop and tell the user.

### Step 2a: Create a feature branch

```bash
git checkout main && git pull --ff-only
git checkout -b fork-micro-wake-word
```

### Step 2b: Update the clone URL in the training script

Edit `train_microwakeword_macos.sh` line 239. Change:

```bash
  git clone https://github.com/TaterTotterson/micro-wake-word.git deps/micro-wake-word >/dev/null
```

to:

```bash
  git clone https://github.com/Gabriel-Lewis/micro-wake-word.git deps/micro-wake-word >/dev/null
```

The `git pull --ff-only` on line 242 does not specify a remote URL (just `origin main`), so existing checkouts will keep working — but new clones go to Gabriel-Lewis.

### Step 2c: Handle existing user checkouts

A user with an existing `deps/micro-wake-word` directory will still be pointing at TaterTotterson via the cloned `origin` remote. Add a one-time remote-URL migration so the next run silently corrects it. Insert this block immediately before the `if [[ ! -d "deps/micro-wake-word" ]]` check on line 237:

```bash
# One-time migration: repoint legacy TaterTotterson clones at Gabriel-Lewis.
if [[ -d "deps/micro-wake-word/.git" ]]; then
  current_url="$(git -C deps/micro-wake-word remote get-url origin 2>/dev/null || true)"
  if [[ "$current_url" == *"TaterTotterson/micro-wake-word"* ]]; then
    git -C deps/micro-wake-word remote set-url origin https://github.com/Gabriel-Lewis/micro-wake-word.git
  fi
fi
```

### Step 2d: Update `CLAUDE.md`

The `deps/micro-wake-word/` row currently says "microWakeWord library (Apple Silicon fork, auto-updated)". Update to reflect the new owner — e.g.:

```
| `deps/micro-wake-word/` | microWakeWord library (Gabriel-Lewis fork with Apple Silicon patches, auto-updated) |
```

### Step 2e: Verify nothing else references the old URL

```bash
grep -rn "TaterTotterson/micro-wake-word" . --exclude-dir=deps --exclude-dir=.venv --exclude-dir=.recorder-venv --exclude-dir=.test-venv --exclude-dir=.git
```

Only `migration-plan.md` and `plans/fork-micro-wake-word.md` should match. Both are tracking docs, not runtime references — leave them.

### Step 2f: Smoke test (optional but recommended)

If you want to verify the clone path locally before merging:

```bash
rm -rf deps/micro-wake-word
bash -c 'PY=.venv/bin/python; mkdir -p deps; git clone https://github.com/Gabriel-Lewis/micro-wake-word.git deps/micro-wake-word'
```

A successful clone is sufficient; no need to re-run the full training.

### Step 2g: Update the migration tracker

Edit `migration-plan.md` and mark the `micro-wake-word` row as ✅ done (or strike through the row).

### Step 2h: Commit and open PR

```bash
git add train_microwakeword_macos.sh CLAUDE.md migration-plan.md
git commit -m "$(cat <<'EOF'
refactor: point micro-wake-word dep at Gabriel-Lewis fork

Replaces the runtime git clone URL with Gabriel-Lewis/micro-wake-word
(a fork of TaterTotterson/micro-wake-word preserving Apple Silicon
patches). Adds a one-time remote-URL migration so existing clones
silently switch over on the next training run.

Upstream HEAD at fork time: <sha from Phase 1 step 2>

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push -u origin fork-micro-wake-word
gh pr create --title "refactor: point micro-wake-word dep at Gabriel-Lewis fork" --body "..."
```

---

## Out of scope

- Syncing the Gabriel-Lewis fork with `kahrendt/microWakeWord` upstream — separate concern, do later.
- Vendoring `micro-wake-word` into this repo the way piper-sample-generator was vendored. The library is large and actively iterated; a fork is the right scope here.
- Bumping the `pymicro-features` / `audio-metadata` git+ URLs on lines 231-232 (different upstreams, not part of the TaterTotterson removal).

## Acceptance criteria

- `grep -rn TaterTotterson/micro-wake-word .` returns matches only in tracking docs (`plans/`, `migration-plan.md`).
- Fresh clone of this repo + `./train_microwakeword_macos.sh ...` clones the fork from Gabriel-Lewis.
- Existing user checkouts pointing at TaterTotterson auto-repoint on next run.
