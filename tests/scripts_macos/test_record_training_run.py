import json
import sys
from pathlib import Path

import pytest

# Allow importing the script as a module
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts_macos"))
import record_training_run as rtr


def test_safe_word_lowercases():
    assert rtr._safe_word("Hey Computer") == "hey_computer"


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


def test_training_config_captured(tmp_path, monkeypatch):
    yaml_content = """
training_steps: [20000, 10000, 10000]
learning_rates: [0.001, 0.0005, 0.0001]
time_mask_count: [2]
time_mask_max_size: [5]
freq_mask_count: [2]
freq_mask_max_size: [5]
positive_class_weight: [1]
negative_class_weight: [20]
features:
  - features_dir: generated/generated_augmented_features
    sampling_weight: 2.0
    truth: true
  - features_dir: generated/personal_augmented_features
    sampling_weight: 6.0
    truth: true
"""
    yaml_path = tmp_path / "training_parameters.yaml"
    yaml_path.write_text(yaml_content)
    monkeypatch.setattr(
        sys, "argv",
        [
            "record_training_run.py",
            "--wake-word", "karlyle",
            "--training-yaml", str(yaml_path),
            "--personal-samples-dir", str(tmp_path),
            "--negative-samples-dir", str(tmp_path),
            "--output-dir", str(tmp_path / "out"),
        ],
    )
    rtr.main()
    record = json.loads((tmp_path / "out" / "karlyle_history.jsonl").read_text().strip())
    cfg = record["training_config"]
    assert cfg["training_steps"] == [20000, 10000, 10000]
    assert cfg["learning_rates"] == [0.001, 0.0005, 0.0001]
    assert cfg["time_mask_count"] == [2]
    assert cfg["positive_class_weight"] == [1]
    assert cfg["negative_class_weight"] == [20]
    assert len(cfg["feature_sources"]) == 2
    assert cfg["feature_sources"][0]["sampling_weight"] == 2.0
    assert cfg["feature_sources"][1]["truth"] is True


def test_training_config_null_when_yaml_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        sys, "argv",
        [
            "record_training_run.py",
            "--wake-word", "karlyle",
            "--training-yaml", str(tmp_path / "missing.yaml"),
            "--personal-samples-dir", str(tmp_path),
            "--negative-samples-dir", str(tmp_path),
            "--output-dir", str(tmp_path / "out"),
        ],
    )
    rtr.main()
    record = json.loads((tmp_path / "out" / "karlyle_history.jsonl").read_text().strip())
    assert record["training_config"] is None


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
