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
    run_id = now.isoformat()

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
