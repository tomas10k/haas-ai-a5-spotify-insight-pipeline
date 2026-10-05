"""Shared helpers: exact row hashing (same recipe as the grader), CSV reading, atomic writes.

State is kept in plain JSONL files (one JSON object per line) so every handoff is human readable
and a crash can lose at most the line being written."""
import csv, hashlib, json, os, tempfile, time
from pathlib import Path

FIELDS = ("review_id", "review_text", "review_rating", "review_likes", "app_version", "review_timestamp")
TOPICS = ("access", "usability", "playback", "downloads", "catalog", "billing", "support", "other")
INTENTS = ("cancellation", "complaint", "request", "praise", "unclear")  # precedence order
ROOT = Path(__file__).resolve().parent.parent
csv.field_size_limit(2**31 - 1)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)


def row_sha(row):
    """SHA-256 of the six original field strings, exactly as check_submission.py computes it."""
    return hashlib.sha256(canonical([row[k] for k in FIELDS]).encode("utf-8")).hexdigest()


def text_sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def csv_rows(path):
    """Stream rows with a real CSV parser (handles quoted multiline text). Values stay as strings."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, strict=True)
        missing = [k for k in FIELDS if k not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"CSV is missing columns: {missing}")
        for row in reader:
            if None in row or any(row.get(k) is None for k in FIELDS):
                raise ValueError("Malformed CSV row")
            yield {k: row[k] for k in FIELDS}


def write_json(path, value):
    """Atomic write: write a temp file, then rename, so a crash never leaves half a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def append_jsonl(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        f.flush(); os.fsync(f.fileno())


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def load_config(path=None):
    return json.loads(Path(path or ROOT / "config" / "settings.json").read_text())


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


