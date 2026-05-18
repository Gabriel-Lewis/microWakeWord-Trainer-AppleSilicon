# Training History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After each successful training run, append a structured record to a per-wake-word JSONL history file and display that history in a new "History" tab in the trainer web UI.

**Architecture:** A new `scripts_macos/record_training_run.py` is called by `train_microwakeword_macos.sh` after packaging, reads the calibration JSON and sample dir counts, and appends one JSON line to `generated/trained_wake_words/<word>_history.jsonl`. Two new read-only endpoints in `trainer_server.py` serve the history. A new "History" tab in `static/index.html` renders the data as a table with trend charts.

**Tech Stack:** Python 3.11 stdlib only (recorder script); FastAPI (API); vanilla JS + inline SVG (UI).

---

## File Map

| Action | File | Purpose |
|--------|------|---------|
| Create | `scripts_macos/record_training_run.py` | Assembles and appends one run record to JSONL |
| Create | `tests/scripts_macos/test_record_training_run.py` | Unit tests for the recorder |
| Modify | `train_microwakeword_macos.sh:628` | Call recorder after packaging |
| Modify | `trainer_server.py:2942+` | Add two read-only history endpoints |
| Modify | `static/index.html` | Add History tab (nav, view, CSS, JS) |

---

## Task 1: Recorder Script

**Files:**
- Create: `scripts_macos/record_training_run.py`
- Create: `tests/scripts_macos/test_record_training_run.py`

- [ ] **Step 1: Create the tests directory**

```bash
mkdir -p tests/scripts_macos
touch tests/__init__.py tests/scripts_macos/__init__.py
```

- [ ] **Step 2: Write the failing tests**

Create `tests/scripts_macos/test_record_training_run.py`:

```python
import json
import sys
import textwrap
from pathlib import Path

import pytest

# Allow importing the script as a module
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts_macos"))
import record_training_run as rtr


def test_safe_word_lowercases():
    assert rtr._safe_word("Hey Tater") == "hey_tater"


def test_safe_word_strips_non_alnum():
    assert rtr._safe_word("hello-world!") == "helloworld"


def test_safe_word_empty():
    assert rtr._safe_word("") == ""


def test_count_wav_missing_dir(tmp_path):
    assert rtr._count_wav(str(tmp_path / "nope")) == 0


def test_count_wav_counts_only_wav(tmp_path):
    (tmp_path / "a.wav").write_bytes(b"")
    (tmp_path / "b.wav").write_bytes(b"")
    (tmp_path / "c.txt").write_bytes(b"")
    assert rtr._count_wav(str(tmp_path)) == 2


def test_main_writes_jsonl_with_calibration(tmp_path, monkeypatch):
    cal = {
        "probability_cutoff": 0.88,
        "sliding_window_size": 3,
        "selected_metrics": {"recall": 0.9753, "false_accepts_per_hour": 0.827, "ambient_hours": 4.12},
        "per_window_best": [{"sliding_window_size": 3, "probability_cutoff": 0.88, "recall": 0.9753, "false_accepts_per_hour": 0.827}],
    }
    cal_path = tmp_path / "calibration.json"
    cal_path.write_text(json.dumps(cal))
    personal_dir = tmp_path / "personal"
    personal_dir.mkdir()
    (personal_dir / "a.wav").write_bytes(b"")
    negative_dir = tmp_path / "negative"
    negative_dir.mkdir()
    output_dir = tmp_path / "output"

    monkeypatch.setattr(
        sys, "argv",
        [
            "record_training_run.py",
            "--wake-word", "karlyle",
            "--calibration-json", str(cal_path),
            "--max-tts-samples", "50000",
            "--batch-size", "100",
            "--piper-models", "en_US-lessac-high,en_US-ryan-high",
            "--personal-samples-dir", str(personal_dir),
            "--negative-samples-dir", str(negative_dir),
            "--output-dir", str(output_dir),
        ],
    )

    result = rtr.main()
    assert result == 0

    history_path = output_dir / "karlyle_history.jsonl"
    assert history_path.exists()
    record = json.loads(history_path.read_text().strip())
    assert record["wake_word"] == "karlyle"
    assert record["recall"] == pytest.approx(0.9753)
    assert record["false_accepts_per_hour"] == pytest.approx(0.827)
    assert record["probability_cutoff"] == pytest.approx(0.88)
    assert record["sliding_window_size"] == 3
    assert record["max_tts_samples"] == 50000
    assert record["batch_size"] == 100
    assert record["piper_models"] == ["en_US-lessac-high", "en_US-ryan-high"]
    assert record["personal_sample_count"] == 1
    assert record["negative_sample_count"] == 0
    assert len(record["per_window_best"]) == 1


def test_main_writes_nulls_without_calibration(tmp_path, monkeypatch):
    monkeypatch.setattr(
        sys, "argv",
        [
            "record_training_run.py",
            "--wake-word", "karlyle",
            "--calibration-json", str(tmp_path / "missing.json"),
            "--personal-samples-dir", str(tmp_path),
            "--negative-samples-dir", str(tmp_path),
            "--output-dir", str(tmp_path / "out"),
        ],
    )
    assert rtr.main() == 0
    record = json.loads((tmp_path / "out" / "karlyle_history.jsonl").read_text().strip())
    assert record["recall"] is None
    assert record["false_accepts_per_hour"] is None


def test_main_appends_multiple_runs(tmp_path, monkeypatch):
    def run():
        monkeypatch.setattr(
            sys, "argv",
            [
                "record_training_run.py",
                "--wake-word", "karlyle",
                "--personal-samples-dir", str(tmp_path),
                "--negative-samples-dir", str(tmp_path),
                "--output-dir", str(tmp_path / "out"),
            ],
        )
        rtr.main()

    run()
    run()
    lines = (tmp_path / "out" / "karlyle_history.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        json.loads(line)  # must be valid JSON
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
cd /Users/gabriellewis/Desktop/microWakeWord-Trainer-AppleSilicon
python -m pytest tests/scripts_macos/test_record_training_run.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'record_training_run'`

- [ ] **Step 4: Create `scripts_macos/record_training_run.py`**

```python
#!/usr/bin/env python3
"""Append one training run record to a per-wake-word JSONL history file."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def _safe_word(word: str) -> str:
    return re.sub(r'[^a-z0-9_]+', '', re.sub(r'\s+', '_', word.lower()))


def _count_wav(directory: str) -> int:
    d = Path(directory)
    if not d.is_dir():
        return 0
    return sum(1 for _ in d.glob("*.wav"))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Record a training run to JSONL history.")
    p.add_argument("--wake-word", required=True)
    p.add_argument("--calibration-json", default="")
    p.add_argument("--max-tts-samples", type=int, default=0)
    p.add_argument("--batch-size", type=int, default=0)
    p.add_argument("--piper-models", default="")
    p.add_argument("--personal-samples-dir", default="personal_samples")
    p.add_argument("--negative-samples-dir", default="negative_samples")
    p.add_argument("--output-dir", default="generated/trained_wake_words")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    recall = None
    faph = None
    cutoff = None
    window = None
    ambient_hours = None
    per_window_best: list = []

    cal_path = Path(args.calibration_json) if args.calibration_json else None
    if cal_path and cal_path.exists():
        try:
            cal = json.loads(cal_path.read_text(encoding="utf-8"))
            metrics = cal.get("selected_metrics") or {}
            recall = metrics.get("recall")
            faph = metrics.get("false_accepts_per_hour")
            ambient_hours = metrics.get("ambient_hours")
            cutoff = cal.get("probability_cutoff")
            window = cal.get("sliding_window_size")
            per_window_best = cal.get("per_window_best") or []
        except Exception as exc:
            print(f"⚠️  Could not read calibration JSON: {exc}", file=sys.stderr)

    piper_models = [m.strip() for m in args.piper_models.split(",") if m.strip()]

    record = {
        "run_id": run_id,
        "timestamp": now.isoformat(),
        "wake_word": args.wake_word,
        "recall": recall,
        "false_accepts_per_hour": faph,
        "probability_cutoff": cutoff,
        "sliding_window_size": window,
        "ambient_hours": ambient_hours,
        "max_tts_samples": args.max_tts_samples,
        "batch_size": args.batch_size,
        "piper_models": piper_models,
        "personal_sample_count": _count_wav(args.personal_samples_dir),
        "negative_sample_count": _count_wav(args.negative_samples_dir),
        "per_window_best": per_window_best,
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    safe = _safe_word(args.wake_word) or "wakeword"
    history_path = output_dir / f"{safe}_history.jsonl"

    with history_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    print(f"📊 Recorded run to {history_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run tests — confirm they pass**

```bash
python -m pytest tests/scripts_macos/test_record_training_run.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts_macos/record_training_run.py tests/
git commit -m "feat: add training run recorder script with tests"
```

---

## Task 2: Shell Script Integration

**Files:**
- Modify: `train_microwakeword_macos.sh:628` (after packaging inline block, before `echo "🎉 Done."`)

- [ ] **Step 1: Locate the insertion point**

The packaging inline block ends at line 628 with:
```
PY
```
And line 630 is `echo "🎉 Done."`. Insert the recorder call between them.

- [ ] **Step 2: Add the recorder call**

In `train_microwakeword_macos.sh`, replace the line:
```bash
echo "🎉 Done."
```
with:
```bash
# ── (K) record training run ─────────────────────────────────────────────────
echo "📊 Recording training run to history…"
"$PY" scripts_macos/record_training_run.py \
  --wake-word "$TARGET_WORD" \
  --calibration-json "$CALIBRATION_JSON" \
  --max-tts-samples "$MAX_TTS_SAMPLES" \
  --batch-size "$BATCH_SIZE" \
  --piper-models "$PIPER_MODELS_CSV" \
  --personal-samples-dir "personal_samples" \
  --negative-samples-dir "negative_samples" \
  --output-dir "${TRAINED_WAKE_WORDS_DIR:-generated/trained_wake_words}" \
  || echo "⚠️  Training run recording failed (non-fatal)."

echo "🎉 Done."
```

- [ ] **Step 3: Smoke test the shell addition (dry-run syntax check)**

```bash
bash -n train_microwakeword_macos.sh
```

Expected: no output (syntax OK).

- [ ] **Step 4: Commit**

```bash
git add train_microwakeword_macos.sh
git commit -m "feat: call run recorder after training completes"
```

---

## Task 3: API Endpoints

**Files:**
- Modify: `trainer_server.py` (append after line 2945, the last line of `reset_negative_samples`)

- [ ] **Step 1: Add the two endpoints to `trainer_server.py`**

Append at the end of `trainer_server.py` (after the `reset_negative_samples` endpoint):

```python
@app.get("/api/training_history")
def training_history_words():
    TRAINED_WAKE_WORDS_DIR.mkdir(parents=True, exist_ok=True)
    words = sorted(
        p.name[: -len("_history.jsonl")]
        for p in TRAINED_WAKE_WORDS_DIR.glob("*_history.jsonl")
    )
    return {"words": words}


@app.get("/api/training_history/{word}")
def training_history_for_word(word: str):
    safe = re.sub(r"[^a-z0-9_]+", "", re.sub(r"\s+", "_", word.lower()))
    if not safe:
        return {"runs": []}
    history_path = TRAINED_WAKE_WORDS_DIR / f"{safe}_history.jsonl"
    if not history_path.exists():
        return {"runs": []}
    runs = []
    for line in history_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            runs.append(json.loads(line))
        except Exception:
            continue
    runs.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return {"runs": runs}
```

- [ ] **Step 2: Verify the server starts without error**

```bash
cd /Users/gabriellewis/Desktop/microWakeWord-Trainer-AppleSilicon
source .recorder-venv/bin/activate
python -c "import trainer_server; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Test the endpoints with a fixture file**

```bash
mkdir -p generated/trained_wake_words
echo '{"run_id":"2026-05-18T00:00:00Z","timestamp":"2026-05-18T00:00:00+00:00","wake_word":"karlyle","recall":0.9753,"false_accepts_per_hour":0.827,"probability_cutoff":0.88,"sliding_window_size":3,"ambient_hours":4.12,"max_tts_samples":50000,"batch_size":100,"piper_models":["en_US-lessac-high"],"personal_sample_count":42,"negative_sample_count":18,"per_window_best":[]}' \
  > generated/trained_wake_words/karlyle_history.jsonl

# Start server in background, test, then kill
source .recorder-venv/bin/activate
uvicorn trainer_server:app --host 127.0.0.1 --port 8799 &
SERVER_PID=$!
sleep 2
curl -s http://127.0.0.1:8799/api/training_history | python3 -m json.tool
curl -s http://127.0.0.1:8799/api/training_history/karlyle | python3 -m json.tool
kill $SERVER_PID
```

Expected first call: `{"words": ["karlyle"]}`
Expected second call: JSON with `"runs"` array containing 1 record with `"recall": 0.9753`.

- [ ] **Step 4: Commit**

```bash
git add trainer_server.py
git commit -m "feat: add training history API endpoints"
```

---

## Task 4: History Tab — HTML Structure and CSS

**Files:**
- Modify: `static/index.html` (nav bar, view div, CSS)

This task adds the tab button, view container, and styles. No JS yet.

- [ ] **Step 1: Add the CSS for the History tab**

In `static/index.html`, find the closing `</style>` tag. Add these styles just before it:

```css
    /* ── History tab ── */
    #historyView .historyControls { display:flex; gap:12px; align-items:center; flex-wrap:wrap; margin-bottom:14px; }
    #historyView .historyCharts { display:flex; gap:16px; flex-wrap:wrap; margin-bottom:14px; }
    #historyView .historyChart { flex:1; min-width:220px; }
    #historyView .historyChart h4 { margin:0 0 6px; font-size:13px; color:var(--muted); text-transform:uppercase; letter-spacing:0.6px; }
    #historyView .historyChart svg { width:100%; height:80px; display:block; }
    #historyView table { width:100%; border-collapse:collapse; font-size:14px; }
    #historyView th { text-align:left; padding:8px 10px; color:var(--muted); font-weight:500; border-bottom:1px solid var(--line); white-space:nowrap; }
    #historyView td { padding:8px 10px; border-bottom:1px solid rgba(255,255,255,0.05); vertical-align:top; }
    #historyView tr.historyRunRow { cursor:pointer; }
    #historyView tr.historyRunRow:hover td { background:rgba(255,255,255,0.03); }
    #historyView tr.historyWindowRow td { padding:5px 10px 5px 28px; font-size:13px; color:var(--muted); }
    #historyView .emptyState { color:var(--muted); text-align:center; padding:32px 0; }
    #historyView .recallBadge { color:var(--ok); font-weight:600; }
    #historyView .faphBadge { color:var(--orange2); font-weight:600; }
    #historyView .warnBadge { color:var(--warn); font-weight:600; }
```

- [ ] **Step 2: Add the History tab button to the nav**

Find:
```html
      <button id="tabSamples" class="tabBtn" type="button">Samples</button>
    </div>
```

Replace with:
```html
      <button id="tabSamples" class="tabBtn" type="button">Samples</button>
      <button id="tabHistory" class="tabBtn" type="button">History</button>
    </div>
```

- [ ] **Step 3: Add the History view div**

Find (after the closing tag of `samplesView`):
```html
    <div id="firmwareView" class="viewStack stack" hidden>
```

Insert before it:
```html
    <div id="historyView" class="viewStack stack" hidden>
      <div class="card">
        <div class="studioKicker">Training History</div>
        <h3>Model Quality Over Time</h3>
        <p>Each completed training run is recorded. Select a wake word to compare recall and false-accept rate across runs.</p>
        <div class="historyControls">
          <label class="field" style="margin:0">
            <strong>Wake Word</strong>
            <select id="historyWordSelect"><option value="">— select —</option></select>
          </label>
          <span id="historyStatus" class="pill muted">No word selected</span>
        </div>
        <div id="historyChartsArea" hidden>
          <div class="historyCharts">
            <div class="historyChart">
              <h4>Recall %</h4>
              <svg id="historyRecallChart" viewBox="0 0 300 80" preserveAspectRatio="none"></svg>
            </div>
            <div class="historyChart">
              <h4>False Accepts / Hour</h4>
              <svg id="historyFaphChart" viewBox="0 0 300 80" preserveAspectRatio="none"></svg>
            </div>
          </div>
        </div>
        <div id="historyTableWrap">
          <div class="emptyState">Select a wake word above to view its training history.</div>
        </div>
      </div>
    </div>

```

- [ ] **Step 4: Verify the page loads without JS errors**

Start the UI server and open it in a browser:
```bash
./run.sh &
```
Open `http://localhost:8789`. Verify no console errors, the "History" tab button appears, and clicking it shows the placeholder card.

- [ ] **Step 5: Commit**

```bash
git add static/index.html
git commit -m "feat: add History tab HTML structure and CSS"
```

---

## Task 5: History Tab — JavaScript

**Files:**
- Modify: `static/index.html` (JS section)

- [ ] **Step 1: Add history state to `uiState`**

Find:
```javascript
    firmware: { devices: [], templates: [], flashing: null, logLines: [], activeTemplateKey: "" },
```

Replace with:
```javascript
    firmware: { devices: [], templates: [], flashing: null, logLines: [], activeTemplateKey: "" },
    history: { words: [], runs: [], selectedWord: "" },
```

- [ ] **Step 2: Update `setActiveView` to include "history"**

Find:
```javascript
  function setActiveView(view) {
    uiState.activeView = ["captured", "samples", "firmware"].includes(view) ? view : "trainer";
    $("trainerView").hidden = uiState.activeView !== "trainer";
    $("capturedView").hidden = uiState.activeView !== "captured";
    $("samplesView").hidden = uiState.activeView !== "samples";
    $("firmwareView").hidden = uiState.activeView !== "firmware";
    $("tabTrainer").classList.toggle("active", uiState.activeView === "trainer");
    $("tabCaptured").classList.toggle("active", uiState.activeView === "captured");
    $("tabSamples").classList.toggle("active", uiState.activeView === "samples");
    $("tabFirmware").classList.toggle("active", uiState.activeView === "firmware");
  }
```

Replace with:
```javascript
  function setActiveView(view) {
    uiState.activeView = ["captured", "samples", "firmware", "history"].includes(view) ? view : "trainer";
    $("trainerView").hidden = uiState.activeView !== "trainer";
    $("capturedView").hidden = uiState.activeView !== "captured";
    $("samplesView").hidden = uiState.activeView !== "samples";
    $("firmwareView").hidden = uiState.activeView !== "firmware";
    $("historyView").hidden = uiState.activeView !== "history";
    $("tabTrainer").classList.toggle("active", uiState.activeView === "trainer");
    $("tabCaptured").classList.toggle("active", uiState.activeView === "captured");
    $("tabSamples").classList.toggle("active", uiState.activeView === "samples");
    $("tabFirmware").classList.toggle("active", uiState.activeView === "firmware");
    $("tabHistory").classList.toggle("active", uiState.activeView === "history");
  }
```

- [ ] **Step 3: Add the history helper functions**

Find the line:
```javascript
  $("phrase").addEventListener("input", syncButtons);
```

Insert the following block immediately before that line:

```javascript
  // ── History tab ──────────────────────────────────────────────────────────

  function _historySparkline(svgId, values, color, formatTip) {
    const svg = $(svgId);
    if (!svg) return;
    svg.innerHTML = "";
    const W = 300, H = 80, PAD = 6;
    const min = Math.min(...values), max = Math.max(...values);
    const range = max - min || 1;
    const pts = values.map((v, i) => {
      const x = PAD + (i / Math.max(values.length - 1, 1)) * (W - PAD * 2);
      const y = H - PAD - ((v - min) / range) * (H - PAD * 2);
      return [x, y];
    });
    const polyline = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
    polyline.setAttribute("points", pts.map(([x, y]) => `${x},${y}`).join(" "));
    polyline.setAttribute("stroke", color);
    polyline.setAttribute("stroke-width", "2.5");
    polyline.setAttribute("fill", "none");
    polyline.setAttribute("stroke-linejoin", "round");
    polyline.setAttribute("stroke-linecap", "round");
    svg.appendChild(polyline);
    // Dots
    pts.forEach(([x, y], i) => {
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", x); circle.setAttribute("cy", y); circle.setAttribute("r", "3.5");
      circle.setAttribute("fill", color);
      const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
      title.textContent = formatTip(values[i]);
      circle.appendChild(title);
      svg.appendChild(circle);
    });
  }

  function _renderHistoryCharts(runs) {
    const valid = runs.filter(r => r.recall !== null && r.false_accepts_per_hour !== null).slice().reverse();
    if (valid.length < 2) {
      $("historyChartsArea").hidden = true;
      return;
    }
    $("historyChartsArea").hidden = false;
    _historySparkline("historyRecallChart", valid.map(r => r.recall * 100), "var(--ok)", v => `${v.toFixed(2)}%`);
    _historySparkline("historyFaphChart", valid.map(r => r.false_accepts_per_hour), "var(--orange2)", v => `${v.toFixed(3)} /hr`);
  }

  function _renderHistoryTable(runs) {
    const wrap = $("historyTableWrap");
    if (!runs.length) {
      wrap.innerHTML = '<div class="emptyState">No runs recorded yet for this wake word.</div>';
      return;
    }
    const fmtDate = iso => {
      try { return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }); }
      catch { return iso; }
    };
    const fmtRecall = v => v === null || v === undefined ? "—" : `<span class="recallBadge">${(v * 100).toFixed(2)}%</span>`;
    const fmtFaph = v => v === null || v === undefined ? "—" : `<span class="${v < 1 ? "faphBadge" : "warnBadge"}">${v.toFixed(3)}</span>`;
    const fmtNum = v => (v === null || v === undefined || v === 0) ? "—" : v.toLocaleString();
    const fmtModels = arr => (arr && arr.length) ? arr.map(m => m.split("/").pop().replace(/\.(onnx|pt)$/, "")).join(", ") : "—";

    let html = `<table>
<thead><tr>
  <th>Date</th><th>Recall</th><th>FAPH</th><th>Cutoff</th><th>Window</th>
  <th>TTS Samples</th><th>Personal</th><th>Negatives</th><th>Piper Model(s)</th>
</tr></thead><tbody>`;

    runs.forEach((r, idx) => {
      html += `<tr class="historyRunRow" data-idx="${idx}">
  <td>${fmtDate(r.timestamp)}</td>
  <td>${fmtRecall(r.recall)}</td>
  <td>${fmtFaph(r.false_accepts_per_hour)}</td>
  <td>${r.probability_cutoff !== null && r.probability_cutoff !== undefined ? r.probability_cutoff.toFixed(2) : "—"}</td>
  <td>${r.sliding_window_size !== null && r.sliding_window_size !== undefined ? r.sliding_window_size : "—"}</td>
  <td>${fmtNum(r.max_tts_samples)}</td>
  <td>${fmtNum(r.personal_sample_count)}</td>
  <td>${fmtNum(r.negative_sample_count)}</td>
  <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${(r.piper_models||[]).join(', ')}">${fmtModels(r.piper_models)}</td>
</tr>`;
      if (r.per_window_best && r.per_window_best.length) {
        html += `<tr class="historyWindowRow" id="historyWindowRow${idx}" hidden>
  <td colspan="9">
    <table style="width:auto;font-size:12px">
      <thead><tr><th style="padding:2px 8px">Window</th><th style="padding:2px 8px">Cutoff</th><th style="padding:2px 8px">Recall</th><th style="padding:2px 8px">FAPH</th></tr></thead>
      <tbody>
        ${r.per_window_best.map(w => `<tr>
          <td style="padding:2px 8px">${w.sliding_window_size}</td>
          <td style="padding:2px 8px">${(w.probability_cutoff||0).toFixed(2)}</td>
          <td style="padding:2px 8px">${w.recall !== undefined ? (w.recall*100).toFixed(2)+"%" : "—"}</td>
          <td style="padding:2px 8px">${w.false_accepts_per_hour !== undefined ? w.false_accepts_per_hour.toFixed(3) : "—"}</td>
        </tr>`).join("")}
      </tbody>
    </table>
  </td>
</tr>`;
      }
    });
    html += "</tbody></table>";
    wrap.innerHTML = html;

    wrap.querySelectorAll("tr.historyRunRow").forEach(row => {
      row.addEventListener("click", () => {
        const idx = row.dataset.idx;
        const detail = $(`historyWindowRow${idx}`);
        if (detail) detail.hidden = !detail.hidden;
      });
    });
  }

  async function refreshHistory() {
    try {
      const data = await api("/api/training_history");
      uiState.history.words = data.words || [];
      const sel = $("historyWordSelect");
      const prev = sel.value;
      sel.innerHTML = '<option value="">— select —</option>' +
        uiState.history.words.map(w => `<option value="${w}"${w === prev ? " selected" : ""}>${w}</option>`).join("");
      if (uiState.history.words.includes(prev)) {
        await loadHistoryForWord(prev);
      }
    } catch (err) {
      setPill($("historyStatus"), "Load failed", "err");
    }
  }

  async function loadHistoryForWord(word) {
    if (!word) {
      uiState.history.selectedWord = "";
      uiState.history.runs = [];
      $("historyTableWrap").innerHTML = '<div class="emptyState">Select a wake word above to view its training history.</div>';
      $("historyChartsArea").hidden = true;
      setPill($("historyStatus"), "No word selected", "muted");
      return;
    }
    try {
      setPill($("historyStatus"), "Loading…", "warn");
      const data = await api(`/api/training_history/${encodeURIComponent(word)}`);
      uiState.history.selectedWord = word;
      uiState.history.runs = data.runs || [];
      const count = uiState.history.runs.length;
      setPill($("historyStatus"), `${count} run${count !== 1 ? "s" : ""}`, count ? "ok" : "");
      _renderHistoryCharts(uiState.history.runs);
      _renderHistoryTable(uiState.history.runs);
    } catch (err) {
      setPill($("historyStatus"), "Load failed", "err");
    }
  }
```

- [ ] **Step 4: Wire up the tab click and word selector**

Find:
```javascript
  $("tabFirmware").addEventListener("click", () => {
```

Add before it:
```javascript
  $("tabHistory").addEventListener("click", () => {
    setActiveView("history");
    refreshHistory().catch(() => setPill($("historyStatus"), "Load failed", "err"));
  });
  $("historyWordSelect").addEventListener("change", (e) => {
    loadHistoryForWord(e.target.value).catch(() => setPill($("historyStatus"), "Load failed", "err"));
  });
```

- [ ] **Step 5: Manual verification**

With the fixture JSONL written in Task 3 Step 3 still in place, start the server and verify:

1. Click the "History" tab — the word select populates with "karlyle".
2. Select "karlyle" — table row appears with recall 97.53%, FAPH 0.827.
3. Click the row — per-window detail appears.
4. Charts remain hidden (only 1 run, need ≥2).

To test charts: append a second record to the fixture file and reload the tab:
```bash
echo '{"run_id":"2026-05-17T00:00:00Z","timestamp":"2026-05-17T00:00:00+00:00","wake_word":"karlyle","recall":0.96,"false_accepts_per_hour":1.1,"probability_cutoff":0.85,"sliding_window_size":4,"ambient_hours":4.12,"max_tts_samples":50000,"batch_size":100,"piper_models":["en_US-lessac-high"],"personal_sample_count":38,"negative_sample_count":12,"per_window_best":[]}' \
  >> generated/trained_wake_words/karlyle_history.jsonl
```

Reload the History tab — two sparkline charts should appear.

- [ ] **Step 6: Commit**

```bash
git add static/index.html
git commit -m "feat: add History tab with run table and trend charts"
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ Per-word JSONL at `generated/trained_wake_words/<word>_history.jsonl` — Task 1
- ✅ Record schema (all fields) — Task 1
- ✅ Null metrics when calibration missing — Task 1 tests + recorder
- ✅ Shell script call after packaging — Task 2
- ✅ `GET /api/training_history` — Task 3
- ✅ `GET /api/training_history/{word}` — Task 3
- ✅ Wake word selector dropdown — Task 4 (HTML) + Task 5 (JS)
- ✅ Trend charts (hidden < 2 runs) — Task 5
- ✅ Runs table with all specified columns — Task 5
- ✅ Expandable per-window rows — Task 5
- ✅ Exit 0 always on recorder failure — Task 1 (recorder returns 0) + Task 2 (`|| echo`)

**Placeholder scan:** No TBDs, TODOs, or "similar to Task N" references.

**Type consistency:**
- `_safe_word` used identically in recorder (`record_training_run.py`) and API handler (`trainer_server.py`).
- `historyWindowRow${idx}` referenced consistently in render and click handler.
- `uiState.history.runs` set in `loadHistoryForWord` and read in `_renderHistoryCharts`/`_renderHistoryTable`.
- `$("historyStatus")` used with `setPill` consistently throughout.
