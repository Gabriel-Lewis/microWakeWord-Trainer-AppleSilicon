# scripts_macos/write_training_yaml.py
import yaml, os
from pathlib import Path

config = {
  "window_step_ms": 10,
  "train_dir": "generated/trained_models/wakeword",
  "features": [
    {"features_dir": "generated/generated_augmented_features", "sampling_weight": 2.0, "penalty_weight": 1.0, "truth": True,  "truncation_strategy": "truncate_start", "type": "mmap"},
    {"features_dir": "datasets/negative_datasets/speech",     "sampling_weight": 12.0,"penalty_weight": 1.0, "truth": False, "truncation_strategy": "random",         "type": "mmap"},
    {"features_dir": "datasets/negative_datasets/dinner_party","sampling_weight": 12.0,"penalty_weight": 1.0,"truth": False,"truncation_strategy": "random",         "type": "mmap"},
    {"features_dir": "datasets/negative_datasets/no_speech",  "sampling_weight": 5.0, "penalty_weight": 1.0, "truth": False, "truncation_strategy": "random",         "type": "mmap"},
    {"features_dir": "datasets/negative_datasets/dinner_party_eval","sampling_weight": 0.0,"penalty_weight":1.0,"truth": False,"truncation_strategy":"split","type":"mmap"},
  ],
  "training_steps": [20000, 10000, 10000],
  "positive_class_weight": [1],
  "negative_class_weight": [20],
  "learning_rates": [0.001, 0.0005, 0.0001],
  "batch_size": 128,
  "time_mask_max_size": [5],
  "time_mask_count": [2],
  "freq_mask_max_size": [5],
  "freq_mask_count": [2],
  "eval_step_interval": 500,
  "clip_duration_ms": 1500,
  "target_minimization": 0.9,
  "minimization_metric": None,
  "maximization_metric": "average_viable_recall",
}

# Add personal features if they exist
if os.path.exists("generated/personal_augmented_features/training"):
    personal_weight = float(os.environ.get("MWW_PERSONAL_SAMPLING_WEIGHT", "6.0"))
    config["features"].insert(1, {"features_dir": "generated/personal_augmented_features", "sampling_weight": personal_weight, "penalty_weight": 1.0, "truth": True, "truncation_strategy": "truncate_start", "type": "mmap"})
    print(f"✅ Added personal features with sampling_weight={personal_weight}")

# Add reviewed false-positive features if they exist
if os.path.exists("generated/reviewed_negative_features/training"):
    insert_at = 2 if os.path.exists("generated/personal_augmented_features/training") else 1
    config["features"].insert(insert_at, {"features_dir": "generated/reviewed_negative_features", "sampling_weight": 8.0, "penalty_weight": 1.25, "truth": False, "truncation_strategy": "random", "type": "mmap"})
    print("✅ Added reviewed negative features with stronger negative weighting")

with open("training_parameters.yaml", "w") as f:
    yaml.dump(config, f)
print("📝 Wrote training_parameters.yaml")
