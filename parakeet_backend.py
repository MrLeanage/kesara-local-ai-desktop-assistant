"""Optional local NVIDIA Parakeet TDT 0.6B v3 INT8 speech recognition.

Uses the official sherpa-onnx ONNX conversion. The archive is downloaded only
when the user selects Parakeet. No cloud inference or audio upload is used.
"""
import hashlib
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import threading
import urllib.request

BASE = Path(__file__).resolve().parent
MODEL_DIR = BASE / "speech-model" / "parakeet-tdt-0.6b-v3-int8"
ARCHIVE_NAME = "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2"
ARCHIVE_URL = ("https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
               + ARCHIVE_NAME)
INNER_DIR = ARCHIVE_NAME.removesuffix(".tar.bz2")
REQUIRED = ("encoder.int8.onnx", "decoder.int8.onnx",
            "joiner.int8.onnx", "tokens.txt")
# Published archive digest (2026-11-07). Fail closed if upstream changes it.
ARCHIVE_SHA256 = "1495e91b59d7fc53ddca91f3431758ec99f8fa253fdb0e1e851be0f72b14b0f9"
MAX_ARCHIVE_BYTES = 900 * 1024 * 1024
MAX_EXTRACTED_BYTES = 1400 * 1024 * 1024
_lock = threading.RLock()
_recognizer = None

def is_installed(model_dir=None):
    root = Path(model_dir or MODEL_DIR)
    return all((root / name).is_file() and (root / name).stat().st_size > 100
               for name in REQUIRED)

def unpack_verified_archive(archive_path, destination):
    """Extract only four expected regular files; block tar traversal/link attacks."""
    destination = Path(destination)
    staging = destination.parent / (destination.name + ".installing")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        with tarfile.open(archive_path, "r:bz2") as archive:
            members = {}
            for member in archive:
                path = Path(member.name.replace("\\", "/"))
                if (not member.isfile() or len(path.parts) != 2
                        or path.parts[0] != INNER_DIR or path.parts[1] not in REQUIRED):
                    continue
                if member.size <= 100 or member.size > MAX_EXTRACTED_BYTES:
                    raise RuntimeError("Invalid Parakeet model file size: " + member.name)
                if path.parts[1] in members:
                    raise RuntimeError("Duplicate Parakeet model file")
                members[path.parts[1]] = member
            if set(members) != set(REQUIRED):
                raise RuntimeError("Parakeet archive is missing required ONNX files")
            if sum(m.size for m in members.values()) > MAX_EXTRACTED_BYTES:
                raise RuntimeError("Extracted model exceeds size limit")
            for name, member in members.items():
                source = archive.extractfile(member)
                if source is None:
                    raise RuntimeError("Could not extract " + name)
                with source, (staging / name).open("wb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
        if not is_installed(staging):
            raise RuntimeError("Parakeet model verification failed")
        if destination.exists():
            shutil.rmtree(destination)
        staging.rename(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)

def ensure_model(on_status=None):
    if is_installed():
        return False
    MODEL_DIR.parent.mkdir(parents=True, exist_ok=True)
    # The archive is large: reserve space for download and extraction.
    if shutil.disk_usage(MODEL_DIR.parent).free < 2 * 1024 ** 3:
        raise RuntimeError("Parakeet setup needs at least 2 GB of free disk space")
    if on_status:
        on_status("Downloading free Parakeet V3 model (~500 MB); first run only...")
    with tempfile.TemporaryDirectory(prefix="kesara-parakeet-") as temp:
        archive_file = Path(temp) / ARCHIVE_NAME
        request = urllib.request.Request(ARCHIVE_URL,
                                         headers={"User-Agent": "Kesara-local-ASR/1"})
        sha = hashlib.sha256()
        total = 0
        try:
            with urllib.request.urlopen(request, timeout=90) as response, archive_file.open("wb") as out:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_ARCHIVE_BYTES:
                        raise RuntimeError("Parakeet download exceeded safety limit")
                    sha.update(chunk)
                    out.write(chunk)
                    if on_status and total % (32 * 1024 * 1024) < len(chunk):
                        on_status(f"Downloading Parakeet V3: {total // (1024 * 1024)} MB")
        except Exception as exc:
            raise RuntimeError("Parakeet download failed; internet access required for setup: " + str(exc)) from exc
        if sha.hexdigest().lower() != ARCHIVE_SHA256:
            raise RuntimeError("Parakeet download integrity check failed; archive may have changed upstream")
        if on_status:
            on_status("Verifying and installing Parakeet locally...")
        unpack_verified_archive(archive_file, MODEL_DIR)
    return True

def load_recognizer():
    global _recognizer
    with _lock:
        if _recognizer is not None:
            return _recognizer
        if not is_installed():
            raise RuntimeError("Parakeet model is not installed")
        try:
            import sherpa_onnx
        except ImportError as exc:
            raise RuntimeError("Parakeet needs sherpa-onnx. Run: python -m pip install sherpa-onnx") from exc
        _recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(MODEL_DIR / REQUIRED[0]),
            decoder=str(MODEL_DIR / REQUIRED[1]),
            joiner=str(MODEL_DIR / REQUIRED[2]),
            tokens=str(MODEL_DIR / REQUIRED[3]),
            num_threads=3, sample_rate=16000, feature_dim=80,
            decoding_method="greedy_search", provider="cpu")
        return _recognizer

def transcribe(waveform):
    """waveform: float32 mono numpy array sampled at 16 kHz."""
    recognizer = load_recognizer()
    stream = recognizer.create_stream()
    stream.accept_waveform(16000, waveform)
    recognizer.decode_stream(stream)
    return stream.result.text.strip()
