# scripts_macos/get_piper_generator.sh
#!/usr/bin/env bash
set -euo pipefail

PYTHON="${PY:-python}"
TORCH_VERSION="${TORCH_VERSION:-2.9.0}"
TORCHAUDIO_VERSION="${TORCHAUDIO_VERSION:-${TORCH_VERSION}}"

download_file() {
  local url="$1"
  local out="$2"

  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url" -o "$out"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$out" "$url"
  else
    echo "❌ Need curl or wget to download voice models."
    exit 1
  fi
}

# venv assumed active outside — install only if not already present to avoid
# inadvertently upgrading packages that the TF/Metal training stack requires pinned.
_pip_install_if_missing() {
  local pkg="$1"
  local import_name="${2:-$1}"
  if ! "$PYTHON" -c "import $import_name" 2>/dev/null; then
    echo "📦 Installing ${pkg}…"
    "$PYTHON" -m pip install -q "$pkg"
  fi
}

_pip_install_if_missing "piper-tts>=1.3.0,<2"   piper
_pip_install_if_missing audiomentations           audiomentations
_pip_install_if_missing "torch==${TORCH_VERSION}"    torch
_pip_install_if_missing "torchaudio==${TORCHAUDIO_VERSION}" torchaudio
_pip_install_if_missing piper-phonemize-cross==1.2.1 piper_phonemize

MODELS_DIR="deps/piper-models"
VOICES_DIR="deps/piper-models/voices"
mkdir -p "$MODELS_DIR" "$VOICES_DIR"

# English multi-speaker model (used by --language=en)
EN_MODEL_NAME="en_US-libritts_r-medium.pt"
EN_MODEL_URL="https://github.com/rhasspy/piper-sample-generator/releases/download/v2.0.0/${EN_MODEL_NAME}"
if [[ ! -f "${MODELS_DIR}/${EN_MODEL_NAME}" ]]; then
  echo "⬇️ Downloading ${EN_MODEL_NAME}…"
  download_file "${EN_MODEL_URL}" "${MODELS_DIR}/${EN_MODEL_NAME}"
fi
if [[ ! -f "${MODELS_DIR}/${EN_MODEL_NAME}.json" ]]; then
  echo "⬇️ Downloading ${EN_MODEL_NAME}.json…"
  download_file "${EN_MODEL_URL}.json" "${MODELS_DIR}/${EN_MODEL_NAME}.json"
fi

echo "ℹ️ Non-English Piper voices are downloaded on demand for the selected language."

echo "✅ piper-sample-generator ready."
