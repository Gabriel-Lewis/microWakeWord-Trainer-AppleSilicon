#!/usr/bin/env python3
"""Append one training run record to a per-wake-word JSONL history file."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml as _yaml
except ImportError:
    _yaml = None  # type: ignore[assignment]


def _safe_word(word: str) -> str:
    return re.sub(r'[^a-z0-9_]+', '', re.sub(r'\s+', '_', word.lower()))


def _count_wav(directory: str) -> int:
    d = Path(directory)
    if not d.is_dir():
        return 0
    return sum(1 for _ in d.glob("*.wav"))


def _read_training_config(yaml_path: str) -> dict | None:
    if not yaml_path or _yaml is None:
        return None
    p = Path(yaml_path)
    if not p.exists():
        return None
    try:
        cfg = _yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        result: dict = {}
        for key in ("training_steps", "learning_rates"):
            if key in cfg:
                result[key] = cfg[key]
        for key in ("time_mask_count", "time_mask_max_size", "freq_mask_count", "freq_mask_max_size"):
            if key in cfg:
                result[key] = cfg[key]
        for key in ("positive_class_weight", "negative_class_weight"):
            if key in cfg:
                result[key] = cfg[key]
        if "features" in cfg:
            result["feature_sources"] = [
                {
                    "features_dir": f.get("features_dir", ""),
                    "sampling_weight": f.get("sampling_weight"),
                    "truth": f.get("truth"),
                }
                for f in cfg["features"]
            ]
        return result or None
    except Exception as exc:
        print(f"⚠️  Could not read training YAML: {exc}", file=sys.stderr)
        return None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Record a training run to JSONL history.")
    p.add_argument("--wake-word", required=True)
    p.add_argument("--calibration-json", default="")
    p.add_argument("--training-yaml", default="training_parameters.yaml")
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
    training_config = _read_training_config(args.training_yaml)

    record = {
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
        "training_config": training_config,
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
