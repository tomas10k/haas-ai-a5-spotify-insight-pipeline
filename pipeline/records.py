"""Code only: expand per text results back to every original review ID (exact text reuse with provenance).

Out: runs/<run>/records/enriched.jsonl    one line per completed review (cache_source_id when reused)
     runs/<run>/records/quarantine.jsonl  empty texts + texts invalid after retry
     runs/<run>/records/status.json       counts: completed / quarantined / pending
"""
import json
from collections import Counter
from pathlib import Path
from .common import read_jsonl, write_json

FIELDS = ("topic", "intent", "sentiment", "severity", "entities", "evidence_quote", "needs_review", "label_config")


def load_texts_results(run_dir):
    run_dir = Path(run_dir)
    res, fail = {}, {}
    for name, d in (("enriched_texts.jsonl", res), ("failures.jsonl", fail)):
        p = run_dir / "enrich" / name
        if p.exists():
            for line in open(p, encoding="utf-8"):
                try:
                    r = json.loads(line); d[r["text_sha"]] = r
                except (json.JSONDecodeError, KeyError):
                    pass
    return res, fail


def build_records(run_dir, log=print):
    run_dir = Path(run_dir)
    res, fail = load_texts_results(run_dir)
    out = run_dir / "records"; out.mkdir(exist_ok=True)
    counts = Counter()
    with open(out / "enriched.jsonl", "w", encoding="utf-8") as ef, open(out / "quarantine.jsonl", "w", encoding="utf-8") as qf:
        for q in read_jsonl(run_dir / "prepare" / "quarantine.jsonl"):
            qf.write(json.dumps(q, ensure_ascii=False) + "\n"); counts["quarantined"] += 1
        for s in read_jsonl(run_dir / "prepare" / "source_index.jsonl"):
            ts = s["text_sha"]
            if ts is None:
                continue
            if ts in res:
                r = res[ts]
                rec = {"review_id": s["review_id"], "source_sha256": s["source_sha256"], "status": "completed",
                       **{k: r[k] for k in FIELDS}}
                if s["review_id"] != r["origin_review_id"]:
                    rec["cache_source_id"] = r["origin_review_id"]
                    counts["completed_via_exact_text_reuse"] += 1
                rec["review_rating"], rec["review_timestamp"], rec["review_likes"] = s["review_rating"], s["review_timestamp"], s["review_likes"]
                ef.write(json.dumps(rec, ensure_ascii=False) + "\n"); counts["completed"] += 1
            elif ts in fail:
                f = fail[ts]
                qf.write(json.dumps({"review_id": s["review_id"], "source_sha256": s["source_sha256"], "status": "quarantined",
                                     "reason": f["reason"], "attempts": f["attempts"]}, ensure_ascii=False) + "\n")
                counts["quarantined"] += 1
            else:
                counts["pending"] += 1
    status = dict(counts)
    write_json(out / "status.json", status)
    log(f"[records] {status}")
    return status


def completed_review_ids(run_dir):
    res, _ = load_texts_results(run_dir)
    return sorted(s["review_id"] for s in read_jsonl(Path(run_dir) / "prepare" / "source_index.jsonl")
                  if s["text_sha"] in res)
