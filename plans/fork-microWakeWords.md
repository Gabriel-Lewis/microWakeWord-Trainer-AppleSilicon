# Plan: Fork `microWakeWords` to Gabriel-Lewis (firmware templates + watcher.sh)

## Context

Two runtime paths still pull from `TaterTotterson/microWakeWords`:

1. **Firmware tab** — `trainer_server.py` fetches `voicePE-TaterTimer.yaml` and `satellite1-TaterTimer.yaml` at runtime from `raw.githubusercontent.com/TaterTotterson/microWakeWords/main/...`
2. **`watcher.sh`** — uses the same repo for issue tracking (`MW_ISSUE_REPO` default) and model lookup (`MW_MODEL_BASE_PATH=microWakeWordsV3`)

Approach: fork the repo wholesale to `Gabriel-Lewis/microWakeWords` rather than bundling the YAMLs locally. This keeps both consumers (firmware fetch + watcher.sh) on one source and lets us pick up upstream YAML updates by syncing the fork.

The `-TaterTimer` suffix in the YAML filenames is cosmetic. We can either keep it (zero code change to filenames) or rename to drop branding. **This plan keeps the filenames as-is** to minimize blast radius; renaming is a follow-up.

## Affected files

- `trainer_server.py` lines 72-74: `FIRMWARE_GITHUB_OWNER` default
- `watcher.sh` lines 17, 59: `MW_ISSUE_REPO` default + docstring
- `CLAUDE.md`: firmware-flashing section mentions the TaterTotterson repo by name
- `README.md`: scan for any references
- `migration-plan.md`: mark items 2 + 3 done

No filename or template-content changes — the YAMLs in the fork stay named `voicePE-TaterTimer.yaml` / `satellite1-TaterTimer.yaml`.

---

## Phase 1 — Manual GitHub steps (user)

### Step 1: Fork the repo

1. Open https://github.com/TaterTotterson/microWakeWords
2. Click **Fork** (top-right).
3. Owner: `Gabriel-Lewis`. Repository name: `microWakeWords`. Leave "Copy the main branch only" **checked**.
4. Click **Create fork**.
5. Confirm the new repo exists at https://github.com/Gabriel-Lewis/microWakeWords with default branch `main`.

### Step 2: Confirm the firmware YAMLs are present in the fork

In the new repo, verify both files exist on `main`:

- `voicePE-TaterTimer.yaml`
- `satellite1-TaterTimer.yaml`

(They should — fork copies all branch contents. If either is missing, stop and report back.)

### Step 3: Capture upstream HEAD SHA

Note the top commit SHA at https://github.com/TaterTotterson/microWakeWords/commits/main for the PR description.

### Step 4: Return to the LLM

> "Forked to Gabriel-Lewis/microWakeWords, both YAMLs present, upstream HEAD was `<sha>`. Proceed with Phase 2."

---

## Phase 2 — Code changes (LLM walkthrough)

> **LLM instructions:** Do not start Phase 2 until the user confirms the fork exists. Verify with:
> ```bash
> gh repo view Gabriel-Lewis/microWakeWords --json defaultBranchRef,pushedAt
> gh api repos/Gabriel-Lewis/microWakeWords/contents/voicePE-TaterTimer.yaml --jq .name
> gh api repos/Gabriel-Lewis/microWakeWords/contents/satellite1-TaterTimer.yaml --jq .name
> ```
> If any check fails, stop and tell the user.

### Step 2a: Branch

```bash
git checkout main && git pull --ff-only
git checkout -b fork-microwakewords
```

### Step 2b: Update firmware default in `trainer_server.py`

Edit line 72:

```python
FIRMWARE_GITHUB_OWNER = os.environ.get("FIRMWARE_GITHUB_OWNER", "TaterTotterson")
```

to:

```python
FIRMWARE_GITHUB_OWNER = os.environ.get("FIRMWARE_GITHUB_OWNER", "Gabriel-Lewis")
```

Leave lines 73 (`FIRMWARE_GITHUB_REPO`) and 74 (`FIRMWARE_GITHUB_REF`) unchanged — repo name and branch are identical in the fork. The env var override remains intact for users who want custom templates.

### Step 2c: Update `watcher.sh`

Edit line 59:

```bash
MW_ISSUE_REPO="${MW_ISSUE_REPO:-TaterTotterson/microWakeWords}"
```

to:

```bash
MW_ISSUE_REPO="${MW_ISSUE_REPO:-Gabriel-Lewis/microWakeWords}"
```

Also update the docstring on line 17 to match:

```bash
# - MW_ISSUE_REPO (default: Gabriel-Lewis/microWakeWords)
```

Leave `MW_MODEL_BASE_PATH=microWakeWordsV3` (line 62) — that's a path inside the repo, not an owner reference.

### Step 2d: Update `CLAUDE.md`

Edit the Firmware Flashing section so the GitHub repo link points at the Gabriel-Lewis fork. Match the wording style of the existing paragraph.

### Step 2e: Check for any other refs

```bash
grep -rn "TaterTotterson" . \
  --exclude-dir=deps --exclude-dir=.venv --exclude-dir=.recorder-venv \
  --exclude-dir=.test-venv --exclude-dir=.git --exclude-dir=plans
```

Only `migration-plan.md` should still match. If `README.md` matches, update it too.

### Step 2f: Smoke test — confirm template fetch works

```bash
curl -sf https://raw.githubusercontent.com/Gabriel-Lewis/microWakeWords/main/voicePE-TaterTimer.yaml | head -5
curl -sf https://raw.githubusercontent.com/Gabriel-Lewis/microWakeWords/main/satellite1-TaterTimer.yaml | head -5
```

Both should return YAML, not 404. If 404, the fork is missing the files — stop and tell the user.

If the UI is currently running, in the Firmware tab pick a template and confirm it loads (no fetch errors in the server log).

### Step 2g: Update migration tracker

Mark items 2 (firmware templates) and 3 (watcher.sh) done in `migration-plan.md`.

### Step 2h: Commit and PR

```bash
git add trainer_server.py watcher.sh CLAUDE.md migration-plan.md
git commit -m "$(cat <<'EOF'
refactor: point microWakeWords runtime deps at Gabriel-Lewis fork

Switches the firmware template fetch default and watcher.sh issue repo
default from TaterTotterson/microWakeWords to Gabriel-Lewis/microWakeWords
(a fork of the same repo). The FIRMWARE_GITHUB_* and MW_ISSUE_REPO env
var overrides remain intact for users who want custom sources. YAML
filenames are unchanged.

Upstream HEAD at fork time: <sha from Phase 1>

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push -u origin fork-microwakewords
gh pr create --title "refactor: point microWakeWords runtime deps at Gabriel-Lewis fork" --body "..."
```

---

## Out of scope

- Renaming `voicePE-TaterTimer.yaml` → `voicePE.yaml` (and the matching `label` strings). Cosmetic-only; do as a follow-up PR after the fork is live and proven.
- Editing YAML content inside the fork (e.g., scrubbing TaterTimer mentions from the firmware itself).
- Bundling the YAMLs locally as a fallback. Migration plan originally suggested this; the fork-only approach is simpler and keeps a single source of truth.

## Acceptance criteria

- `grep -rn TaterTotterson .` (excluding `plans/`, `migration-plan.md`, vendor dirs) returns no matches.
- Fresh checkout + Firmware tab loads both VoicePE and Sat1 templates without a network error.
- `curl` smoke tests in 2f both return 200.
- `watcher.sh --help` (or its docstring) shows `Gabriel-Lewis/microWakeWords` as the default issue repo.
