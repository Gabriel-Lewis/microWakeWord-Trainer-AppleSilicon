# Training History Design

**Date:** 2026-05-18
**Branch:** tier1-model-quality

## Goal

After each successful training run, append a structured record to a per-wake-word history file. Expose that history through a new API and display it in a "History" tab in the trainer web UI, so users can see whether recall and FAPH are improving across runs.

---

## Storage

**Format:** JSONL — one JSON object per line, appended on each run. Never rewritten in full.

**Location:** `generated/trained_wake_words/<word>_history.jsonl`

This sits alongside the `.tflite` and `.json` artifacts that are already written there.

### Run Record Schema

```json
{
  "run_id": "2026-05-18T14:23:01Z",
  "timestamp": "2026-05-18T14:23:01.234567+00:00",
  "wake_word": "karlyle",
  "recall": 0.9753,
  "false_accepts_per_hour": 0.827,
  "probability_cutoff": 0.88,
  "sliding_window_size": 3,
  "ambient_hours": 4.12,
  "max_tts_samples": 50000,
  "batch_size": 100,
  "piper_models": ["en_US-lessac-high"],
  "personal_sample_count": 42,
  "negative_sample_count": 18,
  "per_window_best": [
    {"sliding_window_size": 3, "probability_cutoff": 0.88, "recall": 0.9753, "false_accepts_per_hour": 0.827},
    {"sliding_window_size": 4, "probability_cutoff": 0.85, "recall": 0.9741, "false_accepts_per_hour": 0.931}
  ]
}
```

All metric fields are `null` if calibration failed (so the run is still recorded).

---

## Recording Script

**File:** `scripts_macos/record_training_run.py`

Called by `train_microwakeword_macos.sh` immediately after the packaging step, whether calibration succeeded or not. Reads the calibration JSON (if present), counts `*.wav` files in the sample dirs, assembles the record, and appends it to the history file.

**CLI invocation (added to shell script):**
```bash
"$PY" scripts_macos/record_training_run.py \
  --wake-word "$TARGET_WORD" \
  --calibration-json "$CALIBRATION_JSON" \
  --max-tts-samples "$MAX_TTS_SAMPLES" \
  --batch-size "$BATCH_SIZE" \
  --piper-models "$PIPER_MODELS_CSV" \
  --personal-samples-dir "personal_samples" \
  --negative-samples-dir "negative_samples" \
  --output-dir "generated/trained_wake_words"
```

`PIPER_MODELS_CSV` is a comma-separated string of the piper model paths/names already collected by the shell script.

**Behavior:**
- Creates `<output-dir>/` if needed (already created by packaging step, but safe to be idempotent).
- Appends one line to `<output-dir>/<safe_word>_history.jsonl` (same sanitization as the packaging step: lowercase, non-alphanumeric stripped).
- Prints a one-line confirmation: `📊 Recorded run to <path>`.
- Exits 0 always — recording failure must not break a successful training run.

---

## API

Two new read-only endpoints added to `trainer_server.py`. No new `STATE` entries — both are pure file I/O.

### `GET /api/training_history`
Returns a list of wake words that have history files.

```json
{"words": ["karlyle", "hey_tater"]}
```

Implementation: scan `generated/trained_wake_words/` for `*_history.jsonl` files, strip the `_history.jsonl` suffix.

### `GET /api/training_history/{word}`
Returns all runs for a given word, newest-first.

```json
{"runs": [...]}
```

Returns `{"runs": []}` (200) when the word has no history file yet. Parses each line of the JSONL; skips malformed lines silently.

---

## Web UI — History Tab

**Location in nav:** Between "Samples" and "Firmware".

**Components:**

1. **Wake word selector** — dropdown populated from `GET /api/training_history`. When changed, fetches runs and re-renders.

2. **Trend charts** — two small inline charts (SVG or Canvas, no external library) drawn above the table:
   - Recall % over time
   - FAPH over time
   - Hidden if fewer than 2 runs exist; replaced with "Train again to see trends."

3. **Runs table** — one row per run, sorted newest-first. Columns:
   | Date | Recall | FAPH | Cutoff | Window | TTS Samples | Personal | Negatives | Piper Model(s) |

4. **Expandable rows** — clicking a row toggles a nested per-window table:
   | Window | Cutoff | Recall | FAPH |
   One row per window size evaluated during calibration.

---

## Error Handling

- Calibration failure: run is still recorded with `null` metric fields.
- History file missing: API returns empty list; UI shows "No runs recorded yet."
- Malformed JSONL lines: silently skipped in the API reader.
- Recording script failure: prints warning, exits 0 (does not abort training).

---

## Out of Scope

- Deleting or editing runs.
- Comparing two wake words side-by-side.
- Exporting history to CSV.
- Showing training loss curves (not captured at this point in the pipeline).
