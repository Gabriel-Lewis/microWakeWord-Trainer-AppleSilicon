# scripts_macos/make_features.py

import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True, write_through=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True, write_through=True)


IMPULSE_PATHS = ["datasets/mit_rirs"]
BACKGROUND_PATHS = [
    "datasets/wham_16k",
    "datasets/chime_16k",
    "datasets/fma_16k",
    "datasets/audioset_16k",
]
AUGMENTATION_PROBABILITIES = {
    "SevenBandParametricEQ": 0.1,
    "TanhDistortion": 0.05,
    "PitchShift": 0.15,
    "BandStopFilter": 0.1,
    "AddColorNoise": 0.1,
    "AddBackgroundNoise": 0.7,
    "Gain": 0.8,
    "RIR": 0.7,
}
SPLIT_CFG = {
    "training":   {"name": "train",      "repetition": 2, "slide_frames": 10},
    "validation": {"name": "validation", "repetition": 1, "slide_frames": 1},
    "testing":    {"name": "test",       "repetition": 1, "slide_frames": 1},
}


def validate(paths):
    for p in paths:
        if not os.path.exists(p):
            raise SystemExit(f"❌ Missing directory: {p}. Run dataset prep first.")
    print(f"✅ Validated all {len(paths)} dataset directories")


def _build_features_for_source(label: str, input_directory: str, out_root: str, remove_silence: bool) -> str:
    """Run in worker process. Builds train/val/test mmaps for one source."""
    from mmap_ninja.ragged import RaggedMmap
    from microwakeword.audio.augmentation import Augmentation
    from microwakeword.audio.clips import Clips
    from microwakeword.audio.spectrograms import SpectrogramGeneration

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True, write_through=True)

    clips = Clips(
        input_directory=input_directory,
        file_pattern="*.wav",
        max_clip_duration_s=5,
        remove_silence=remove_silence,
        random_split_seed=10,
        split_count=0.1,
    )
    augmenter = Augmentation(
        augmentation_duration_s=3.2,
        augmentation_probabilities=AUGMENTATION_PROBABILITIES,
        impulse_paths=IMPULSE_PATHS,
        background_paths=BACKGROUND_PATHS,
        background_min_snr_db=3,
        background_max_snr_db=20,
        min_jitter_s=0.2,
        max_jitter_s=0.3,
    )
    out_root_path = Path(out_root)
    out_root_path.mkdir(parents=True, exist_ok=True)
    for split, cfg in SPLIT_CFG.items():
        out_dir = out_root_path / split
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"🧪 [{label}] Processing {split} …", flush=True)
        spectros = SpectrogramGeneration(
            clips=clips,
            augmenter=augmenter,
            slide_frames=cfg["slide_frames"],
            step_ms=10,
        )
        RaggedMmap.from_generator(
            out_dir=str(out_dir / "wakeword_mmap"),
            sample_generator=spectros.spectrogram_generator(
                split=cfg["name"],
                repeat=cfg["repetition"],
            ),
            batch_size=100,
            verbose=True,
        )
    return label


def main():
    validate(IMPULSE_PATHS + BACKGROUND_PATHS)
    print("⏳ Preparing clip indexes and augmentation pipeline (please wait)…")

    tts_wav_count = len(list(Path("./generated/generated_samples").glob("*.wav")))
    print(f"🎤 Generated sample count: {tts_wav_count}")

    sources = [
        ("TTS", "./generated/generated_samples", "generated/generated_augmented_features", True),
    ]
    if os.path.exists("./personal_samples") and any(Path("./personal_samples").glob("*.wav")):
        sources.append(("personal", "./personal_samples", "generated/personal_augmented_features", False))
        print("✅ Found personal samples, will create separate feature set")
    else:
        print("ℹ️ No personal samples found; continuing with generated samples only")

    if os.path.exists("./negative_samples") and any(Path("./negative_samples").glob("*.wav")):
        sources.append(("reviewed negatives", "./negative_samples", "generated/reviewed_negative_features", False))
        print("✅ Found reviewed negative samples, will create a separate negative feature set")
    else:
        print("ℹ️ No reviewed negative samples found; continuing with stock negative datasets only")

    max_workers = max(1, min(int(os.environ.get("MWW_FEATURE_WORKERS", "2")), len(sources)))
    if max_workers == 1 or len(sources) == 1:
        for label, in_dir, out_root, remove_silence in sources:
            _build_features_for_source(label, in_dir, out_root, remove_silence)
    else:
        print(f"⚙️ Building {len(sources)} feature sets in parallel (max_workers={max_workers})")
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_build_features_for_source, label, in_dir, out_root, remove_silence): label
                for label, in_dir, out_root, remove_silence in sources
            }
            for fut in as_completed(futures):
                label = futures[fut]
                fut.result()  # re-raises any exception
                print(f"✅ Finished feature set: {label}", flush=True)

    print("✅ Features ready.")


if __name__ == "__main__":
    main()
