"""Write the standardized grading/ folder (GRADING_CONTRACT.md) from a saved run. No model calls."""
import csv, gzip, json, shutil
from pathlib import Path
from .common import ROOT, read_jsonl, write_json

KEEP = ("review_id", "source_sha256", "status", "topic", "intent", "sentiment", "severity", "entities",
        "evidence_quote", "needs_review", "label_config", "cache_source_id")
CALL_KEYS = ("request_id", "role", "review_ids", "model", "phase", "outcome", "label_config", "input_tokens", "output_tokens")


def export(run_dir, out=None, log=print):
    run_dir, out = Path(run_dir), Path(out or ROOT / "grading")
    out.mkdir(exist_ok=True)
    ing = json.loads((run_dir / "prepare" / "ingestion_report.json").read_text())
    if not (out / "ingestion.json").exists():
        log("[export] grading/ingestion.json missing: run  python3 check_submission.py profile --full data/spotify_reviews_18months.csv --out grading/ingestion.json")
    # declared scope = the exact CSV this run classified (the full file, or the 100k scope built by `pipeline scope`)
    write_json(out / "run.json", {"version": "a5-audit-v1", "analysis_count": ing["records"],
               "analysis_sha256": ing["input_sha256"], "analysis_file": ing["input_file"], "run_id": run_dir.name,
               "classification_input_fields": ["review_text"], "allow_multi_issue": False})
    n = 0
    with gzip.open(out / "records.jsonl.gz", "wt", encoding="utf-8") as f:
        for r in read_jsonl(run_dir / "records" / "enriched.jsonl"):
            f.write(json.dumps({k: r[k] for k in KEEP if k in r}, ensure_ascii=False) + "\n"); n += 1
        for q in read_jsonl(run_dir / "records" / "quarantine.jsonl"):
            f.write(json.dumps({"review_id": q["review_id"], "source_sha256": q["source_sha256"], "status": "quarantined",
                                "reason": q["reason"]}, ensure_ascii=False) + "\n"); n += 1
    shutil.copy(run_dir / "group" / "membership.csv", out / "membership.csv")
    shutil.copy(run_dir / "rank" / "ranking.csv", out / "ranking.csv")
    shutil.copy(run_dir / "memo" / "claims.csv", out / "claims.csv")
    with gzip.open(out / "calls.jsonl.gz", "wt", encoding="utf-8") as f:
        for c in read_jsonl(run_dir / "calls.jsonl"):
            row = {k: c.get(k) for k in CALL_KEYS}
            # failed attempts that never got a provider response have no usage: kept as null, never invented
            row["usage_available"] = c.get("input_tokens") is not None and not c.get("usage_missing")
            if c.get("error"):
                row["error"] = c["error"][:200]
            if row["role"] != "enrich":
                row["phase"] = c.get("phase", "initial")
            f.write(json.dumps(row) + "\n")
    cps = sorted((run_dir / "enrich" / "checkpoints").glob("*.json"))
    before = [p for p in cps if json.loads(p.read_text())["stop_reason"] != "finished"]
    if before:
        b = json.loads(before[0].read_text()); a = json.loads(cps[-1].read_text())
        write_json(out / "checkpoint_before.json", {"completed_ids": b["completed_ids"]})
        write_json(out / "checkpoint_after.json", {"completed_ids": a["completed_ids"]})
    else:
        log("[export] no interrupted checkpoint found: run the interruption demo before exporting")
    log(f"[export] grading/ written: {n:,} records")
