"""Large run folders are committed as gzip copies; raw JSONL files are rebuilt from them on demand (no model).

    python3 -m pipeline pack   --run-id final_100k   write <file>.jsonl.gz next to every .jsonl / .txt handoff
    python3 -m pipeline unpack --run-id final_100k   restore missing raw files from the .gz copies
The offline commands (rank, export, db, eval-golden) unpack automatically.
"""
import gzip, shutil
from pathlib import Path

PATTERNS = ("*.jsonl", "*.txt")


def pack(run_dir, log=print):
    run_dir, n = Path(run_dir), 0
    for pat in PATTERNS:
        for p in run_dir.rglob(pat):
            gz = p.with_name(p.name + ".gz")
            if not gz.exists() or gz.stat().st_mtime < p.stat().st_mtime:
                with open(p, "rb") as f, gzip.open(gz, "wb", compresslevel=9) as g:
                    shutil.copyfileobj(f, g)
                n += 1
    log(f"[pack] {n} files compressed in {run_dir.name}")


def unpack(run_dir, log=print):
    run_dir, n = Path(run_dir), 0
    for gz in run_dir.rglob("*.gz"):
        raw = gz.with_name(gz.name[:-3])
        if not raw.exists() and raw.suffix in (".jsonl", ".txt"):
            with gzip.open(gz, "rb") as f, open(raw, "wb") as g:
                shutil.copyfileobj(f, g)
            n += 1
    if n:
        log(f"[unpack] restored {n} files in {run_dir.name}")
