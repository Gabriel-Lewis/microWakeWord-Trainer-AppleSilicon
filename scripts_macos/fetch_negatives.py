# scripts_macos/fetch_negatives.py
import shutil
import requests, zipfile, sys
from pathlib import Path
from tqdm import tqdm

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True, write_through=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True, write_through=True)

def download(url: str, out: Path):
    r = requests.get(url, stream=True)
    r.raise_for_status()
    total = int(r.headers.get("content-length", 0))
    tmp = out.with_suffix(out.suffix + ".part")
    with open(tmp, "wb") as f, tqdm(total=total, unit="B", unit_scale=True, desc=out.name) as bar:
        for chunk in r.iter_content(chunk_size=1024):
            f.write(chunk)
            bar.update(len(chunk))
    actual = tmp.stat().st_size
    if total and actual != total:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"Truncated download for {out.name}: got {actual} of {total} bytes")
    tmp.replace(out)


out_dir = Path("datasets/negative_datasets")
out_dir.mkdir(exist_ok=True)

link_root = "https://huggingface.co/datasets/kahrendt/microwakeword/resolve/main/"
files = ["dinner_party.zip", "dinner_party_eval.zip", "no_speech.zip", "speech.zip"]

MARKER = ".extract_complete"

for name in files:
    url = link_root + name
    z = out_dir / name
    extract_dir = out_dir / name.removesuffix(".zip")
    marker = extract_dir / MARKER
    if extract_dir.exists() and marker.exists():
        print(f"✅ {extract_dir.name} already extracted; skipping.")
        continue
    if extract_dir.exists() and not marker.exists():
        print(f"⚠️  {extract_dir.name} exists but is incomplete; re-extracting.")
        shutil.rmtree(extract_dir)
    if not z.exists():
        download(url, z)
    print(f"📦 Extracting {name}…")
    try:
        with zipfile.ZipFile(z, "r") as zf:
            bad = zf.testzip()
            if bad is not None:
                raise RuntimeError(f"Corrupt entry in {name}: {bad}")
            zf.extractall(out_dir)
    except (zipfile.BadZipFile, RuntimeError) as e:
        print(f"❌ Extraction failed for {name}: {e}. Deleting cached zip; rerun to retry.")
        z.unlink(missing_ok=True)
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        sys.exit(1)
    extracted = sum(1 for _ in extract_dir.rglob("*") if _.is_file())
    if extracted == 0:
        shutil.rmtree(extract_dir, ignore_errors=True)
        z.unlink(missing_ok=True)
        raise RuntimeError(f"Extraction of {name} produced 0 files")
    marker.write_text(f"files={extracted}\n")
    print(f"✅ Extracted {extracted} files from {name}.")
print("✅ Negative datasets ready.")
