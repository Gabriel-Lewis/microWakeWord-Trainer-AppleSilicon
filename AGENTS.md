# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## What This Is

A local web UI + CLI training pipeline for custom [microWakeWord](https://github.com/kahrendt/microWakeWord) models on Apple Silicon. Users record/collect wake-word samples via ESPHome devices or manual upload, then train a quantized TFLite model for deployment on ESP32 sats.

## Running the UI

```bash
./run.sh                        # starts FastAPI server on 0.0.0.0:8789
REC_PORT=8790 ./run.sh          # alternate port
REC_ESPHOME_VERSION=2026.4.3 ./run.sh
```

The launcher manages its own venv at `.recorder-venv` (Python 3.11, fastapi + uvicorn + esphome). Do not manually install deps there.

## Running the Training Pipeline Directly

```bash
./train_microwakeword_macos.sh "hey_computer"
./train_microwakeword_macos.sh "hey_computer" 50000 100 --language fr
./train_microwakeword_macos.sh "hey_computer" 50000 100 --piper-model /path/to/voice.pt
```

Training uses a separate venv at `.venv` (Python 3.11, arm64, TF/Keras/Metal pinned stack). Key pinned versions: `tensorflow-macos==2.16.2`, `tensorflow-metal==1.2.0`, `keras==3.3.3`, `torch==2.9.0`. Rebuild `.venv` with `rm -rf .venv` if version drift is detected.

## Architecture

**Two separate Python environments:**
- `.recorder-venv` — UI server only (fastapi, uvicorn, esphome, piper catalog fetching)
- `.venv` — ML training stack (TF/Metal, Keras, PyTorch, microwakeword, piper-tts)

**`trainer_server.py`** — single-file FastAPI app (~2700 lines). All UI state is in a global `STATE` dict protected by `STATE_LOCK`. Long-running jobs (training, firmware flash) run in background threads with streamed log output via SSE-like polling endpoints. Key API surfaces:
- `/api/train` / `/api/train_status` — launch and poll training subprocess
- `/api/firmware/build_flash` / `/api/firmware/flash_status/{session_id}` — ESPHome OTA firmware jobs
- `/api/upload_captured_audio_raw` — ESPHome devices POST raw audio here
- `/api/captured_audio/{name}/approve_personal|mark_negative|discard` — review workflow

**`static/index.html`** — single-page frontend (no build step). Tabs: Trainer, Captured Audio, Samples, Firmware.

**`scripts_macos/`** — Python helper scripts invoked by the training shell script in order:
1. `get_piper_generator.sh` — installs piper-tts deps + downloads default EN voice model to `deps/piper-models/`
2. `run_generator_with_progress.py` — wraps piper TTS generation with progress
3. `prepare_datasets.py` — downloads/resamples MIT RIR, AudioSet, FMA, WHAM, CHiME to 16 kHz
4. `trim_silence.py` — silero-VAD silence trimming on personal samples
5. `make_features.py` — builds augmented spectrogram mmaps for training/validation/testing splits
6. `fetch_negatives.py` — downloads precomputed negative feature datasets
7. `write_training_yaml.py` — writes `training_parameters.yaml`
8. `calibrate_detector.py` — post-training: finds optimal `probability_cutoff` + `sliding_window_size`
9. `package_model.py` — copies `.tflite` + writes `.json` metadata to `trained_wake_words/`

**Cache invalidation:** The training script computes SHA-256 cache keys from wake word, model paths, sample counts, and file mtimes. Cache keys are stored as `.cache_key` files in `generated_samples/`, `generated_augmented_features/`, `personal_augmented_features/`, and `reviewed_negative_features/`. A mismatch or missing key triggers a rebuild of that stage.

## Key Directories

| Directory | Purpose |
|---|---|
| `personal_samples/` | Approved positive wake-word WAVs (16 kHz/mono/16-bit PCM) |
| `negative_samples/` | Reviewed false-wake WAVs used as hard negatives |
| `captured_audio/` | Inbox of ESPHome-uploaded clips awaiting review |
| `generated_samples/` | TTS-generated positive samples (cached) |
| `generated_augmented_features/` | Spectrogram mmaps from generated samples |
| `personal_augmented_features/` | Spectrogram mmaps from personal samples |
| `reviewed_negative_features/` | Spectrogram mmaps from negative samples |
| `negative_datasets/` | Downloaded precomputed negative feature sets |
| `trained_wake_words/` | Final output: `<word>.tflite` + `<word>.json` |
| `trained_models/` | Intermediate checkpoints, cleared each run |
| `deps/piper-models/` | Downloaded piper voice model files (`.pt`, `.onnx`, gitignored) |
| `deps/micro-wake-word/` | microWakeWord library (Gabriel-Lewis fork with Apple Silicon patches, auto-updated) |
| `scripts_macos/generate_samples.py` | Vendored piper sample generator script |
| `scripts_macos/piper_train/` | Vendored piper VITS model code (dependency of generate_samples.py) |
| `.cache/` | Piper voices catalog JSON, firmware flasher working dirs |

## Audio Normalization

All samples must be `16 kHz / mono / 16-bit PCM WAV`. `trainer_server.py` uses `ffmpeg` (installed by Homebrew) to convert uploads. The `CAPTURE_GAIN_PROFILE = "capture_rms_v1"` constant governs how captured audio is gain-normalized before storage.

## Firmware Flashing

The Firmware tab fetches YAML templates from the [microWakeWords](https://github.com/Gabriel-Lewis/microWakeWords) repo on GitHub at runtime (no local fallback). Firmware build state lives under `.cache/firmware_flasher/`. Flash sessions are tracked in `FIRMWARE_SESSIONS` dict by UUID. OTA default port: `3232`. mDNS discovery runs for `ESPHOME_DISCOVERY_SECONDS` (default 2.5s).
