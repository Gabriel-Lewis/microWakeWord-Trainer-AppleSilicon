# Plan: Remove TaterTotterson Runtime Dependencies

## Context

After PR 7 removed cosmetic branding, several runtime paths still point at TaterTotterson's GitHub. This plan eliminates all of them cleanly while keeping upstream-derived assets in forked repositories instead of vendoring them into this repo:

| Dependency | Current | New approach |
|---|---|---|
| `piper-sample-generator` code | TaterTotterson fork | Point to **rhasspy/piper-sample-generator** (original, actively maintained, already has MPS) |
| `piper-sample-generator` model assets | TaterTotterson releases | Point to **rhasspy releases v2.0.0** (same files, already hosted there — no re-hosting needed) |
| `micro-wake-word` | TaterTotterson fork (real Apple Silicon patches) | Fork to **Gabriel-Lewis/micro-wake-word** |
| Firmware YAML templates | Fetched at runtime from TaterTotterson/microWakeWords | Fetch at runtime from forked **Gabriel-Lewis/microWakeWords** |
| `watcher.sh` issue repo | TaterTotterson/microWakeWords | Default to forked **Gabriel-Lewis/microWakeWords** |

---

## Dependency Analysis

### piper-sample-generator → use rhasspy directly
TaterTotterson's fork commits are readme/cleanup only — no Apple Silicon patches. The original `rhasspy/piper-sample-generator` is actively maintained (last push March 2026) and already includes MPS support. Their v2.0.0 GitHub release hosts `en_US-libritts_r-medium.pt` (124k downloads). Zero re-hosting needed.

### micro-wake-word → must fork to Gabriel-Lewis
TaterTotterson's fork has substantive Apple Silicon fixes not in `kahrendt/microWakeWord`:
- `Fix TFLite quantization metadata` — affects output model correctness
- `Implement fallback for Interpreter import` — Apple Silicon TFLite compatibility
- `Enhance audio_utils for compatibility with pymicro-features`
Cannot use the upstream directly without testing. Must fork to Gabriel-Lewis.

### microWakeWords → fork to Gabriel-Lewis
The Firmware tab and `watcher.sh` both consume `TaterTotterson/microWakeWords` today:
- `trainer_server.py` fetches `voicePE-TaterTimer.yaml` and `satellite1-TaterTimer.yaml` from GitHub at runtime.
- `watcher.sh` uses the same repo as its default issue tracker.

Fork the repo wholesale to `Gabriel-Lewis/microWakeWords` and update both consumers to use that fork by default. Do not bundle the YAML files into this repo. Keeping the firmware YAMLs in the fork gives the project one source of truth and makes future upstream syncs straightforward.

The `-TaterTimer` YAML filenames are left unchanged for this migration to minimize blast radius. Renaming those files or editing their contents is a follow-up cleanup after the fork-based path is proven.

---

## Phase 1: Manual GitHub Steps (User Must Do First)

### 1a. Fork micro-wake-word
```
Gabriel-Lewis/micro-wake-word  ← fork of TaterTotterson/micro-wake-word
```

### 1b. Fork microWakeWords
```
Gabriel-Lewis/microWakeWords  ← fork of TaterTotterson/microWakeWords
```
This is used by both `watcher.sh` and the Firmware tab.

Confirm the fork contains these files on `main`:
- `voicePE-TaterTimer.yaml`
- `satellite1-TaterTimer.yaml`

Capture the upstream HEAD SHA for the PR description if possible.

---

## Phase 2: Code Changes (branch `tier4-remove-deps`)

### `trainer_server.py`

**Lines 72-74** — keep env vars but default `FIRMWARE_GITHUB_OWNER` to the fork:
```python
FIRMWARE_GITHUB_OWNER = os.environ.get("FIRMWARE_GITHUB_OWNER", "Gabriel-Lewis")
FIRMWARE_GITHUB_REPO = os.environ.get("FIRMWARE_GITHUB_REPO", "microWakeWords")
FIRMWARE_GITHUB_REF = os.environ.get("FIRMWARE_GITHUB_REF", "main")
```

**Template specs** — leave filenames unchanged:
```python
"label": "VoicePE",
"path": "voicePE-TaterTimer.yaml",
# ...
"label": "Sat1",
"path": "satellite1-TaterTimer.yaml",
```

No local `firmware_templates/` directory is added in this migration. The existing `FIRMWARE_GITHUB_*` env vars remain as overrides for users who want custom templates.

### `scripts_macos/get_piper_generator.sh`

**Line 5** — switch to rhasspy:
```bash
PIPER_REPO_URL="https://github.com/rhasspy/piper-sample-generator.git"
```

**Line 52** — model from rhasspy v2.0.0 release:
```bash
EN_MODEL_URL="https://github.com/rhasspy/piper-sample-generator/releases/download/v2.0.0/${EN_MODEL_NAME}"
```

### `train_microwakeword_macos.sh`

**Line 239** — micro-wake-word from Gabriel-Lewis fork:
```bash
git clone https://github.com/Gabriel-Lewis/micro-wake-word.git deps/micro-wake-word >/dev/null
```

**Line 271** — fallback model download from rhasspy:
```bash
"https://github.com/rhasspy/piper-sample-generator/releases/download/v2.0.0/en_US-libritts_r-medium.pt"
```

### `watcher.sh`

**Docstring and default repo**:
```bash
MW_ISSUE_REPO="${MW_ISSUE_REPO:-Gabriel-Lewis/microWakeWords}"
```

### `README.md` and `CLAUDE.md`
Update `microWakeWords` links to `Gabriel-Lewis/microWakeWords`. Keep TaterTotterson credits.

### `.claude/settings.local.json`
Update two allowlist entries from `TaterTotterson/piper-sample-generator` → `rhasspy/piper-sample-generator`.

---

## What Users Must Do Once (migrate existing local clones)

Anyone with an existing `deps/piper-sample-generator` clone pointing at TaterTotterson will get an origin-mismatch update on next run — `get_piper_generator.sh` already handles this (it checks `current_origin != PIPER_REPO_URL` and runs `git remote set-url`).

Add the same one-time remote migration for `deps/micro-wake-word` in `train_microwakeword_macos.sh` so existing clones silently repoint from `TaterTotterson/micro-wake-word` to `Gabriel-Lewis/micro-wake-word` on the next training run.

---

## Ordering

1. User completes Phase 1:
   - fork `micro-wake-word`
   - fork `microWakeWords`
   - confirm `voicePE-TaterTimer.yaml` and `satellite1-TaterTimer.yaml` exist in the `microWakeWords` fork
2. Branch `tier4-remove-deps`:
   - All code changes above in one commit
3. Open PR against `main`; merge after Phase 1 confirmed
4. Smoke test: `./train_microwakeword_macos.sh "hey_computer"` from clean clone; open Firmware tab

---

## Verification

```bash
# No TaterTotterson references in code (README credits excepted)
grep -r "TaterTotterson" . \
  --include="*.py" --include="*.sh" --include="*.yaml" \
  --include="*.json" --include="*.html" | grep -v README

# Firmware templates come from the fork
curl -sf https://raw.githubusercontent.com/Gabriel-Lewis/microWakeWords/main/voicePE-TaterTimer.yaml | head -5
curl -sf https://raw.githubusercontent.com/Gabriel-Lewis/microWakeWords/main/satellite1-TaterTimer.yaml | head -5
```
- Start server → open Firmware tab → template loads from `Gabriel-Lewis/microWakeWords`
- `./scripts_macos/get_piper_generator.sh` clones from rhasspy, downloads model from rhasspy v2.0.0
