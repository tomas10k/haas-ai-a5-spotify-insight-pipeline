"""Stage 1 Prepare (code only, no model).

In : any CSV with the six source fields.
Out: runs/<run_id>/prepare/
       source_index.jsonl   one line per source row: review_id, source_sha256, text_sha, metadata
       texts.jsonl          one line per distinct nonempty text: the unit of model work (the queue)
       quarantine.jsonl     rows set aside with a reason (the empty texts)
       pending_ids.txt      every review_id still waiting for classification (the to do list)
       ingestion_report.json, data_manifest.json   (file names as in the brief)
Stop rule: if the input is the official full extract and counts differ from manifest.json, stop.
"""
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from .common import FIELDS, csv_rows, row_sha, text_sha, file_sha, write_json, now, ROOT

EXPECTED_FULL = {"records": 660622, "duplicate_review_ids": 0, "empty_review_text": 13,
                 "missing_app_version": 159701, "distinct_nonempty_texts": 484189}


def prepare(csv_path, run_dir, log=print):
    csv_path, out = Path(csv_path), Path(run_dir) / "prepare"
    if (out / "ingestion_report.json").exists():
        log(f"[prepare] already done in {out}, reusing saved handoff")
        return json.loads((out / "ingestion_report.json").read_text())
    out.mkdir(parents=True, exist_ok=True)
    t0 = datetime.now()
    source_sha = file_sha(csv_path)
    ids, dup_ids, n, empty, missing_ver, bad_ts = set(), 0, 0, 0, 0, 0
    ratings, months, text_count = Counter(), Counter(), Counter()
    texts = {}  # text_sha -> [text, first_review_id]
    tmp = out / "source_index.jsonl.part"
    with open(tmp, "w", encoding="utf-8") as idx_f, open(out / "quarantine.jsonl", "w", encoding="utf-8") as q_f, \
         open(out / "pending_ids.txt", "w", encoding="utf-8") as pend_f:
        for r in csv_rows(csv_path):
            n += 1
            rid, txt = r["review_id"], r["review_text"]
            dup_ids += rid in ids
            ids.add(rid)
            ratings[r["review_rating"]] += 1
            months[r["review_timestamp"][:7]] += 1
            try:
                datetime.strptime(r["review_timestamp"], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                bad_ts += 1
            missing_ver += r["app_version"] == ""
            h = row_sha(r)
            ts = None
            if txt.strip() == "":
                empty += 1
                q_f.write(json.dumps({"review_id": rid, "source_sha256": h, "status": "quarantined",
                                      "reason": "empty_review_text", "attempts": 0, "stage": "prepare"}) + "\n")
            else:
                ts = text_sha(txt)
                text_count[ts] += 1
                texts.setdefault(ts, [txt, rid])
            if ts:
                pend_f.write(rid + "\n")
            idx_f.write(json.dumps({"review_id": rid, "source_sha256": h, "text_sha": ts,
                                    "review_rating": r["review_rating"], "review_likes": r["review_likes"],
                                    "app_version": r["app_version"], "review_timestamp": r["review_timestamp"]},
                                   ensure_ascii=False) + "\n")
    tmp.replace(out / "source_index.jsonl")
    with open(out / "texts.jsonl", "w", encoding="utf-8") as f:
        for ts, (txt, rid) in texts.items():
            f.write(json.dumps({"text_sha": ts, "first_review_id": rid, "n_reviews": text_count[ts],
                                "review_text": txt}, ensure_ascii=False) + "\n")

    lengths = sorted(len(t[0]) for t in texts.values())
    pct = lambda p: lengths[min(len(lengths) - 1, int(len(lengths) * p))] if lengths else 0
    top = sorted(((c, texts[t][0]) for t, c in text_count.items() if c > 1), reverse=True)[:15]
    report = {
        "stage": "prepare", "created_at": now(), "input_file": csv_path.name,
        "input_sha256": source_sha, "input_bytes": csv_path.stat().st_size,
        "records": n, "unique_review_ids": len(ids), "duplicate_review_ids": dup_ids,
        "empty_review_text": empty, "nonempty_review_text": n - empty,
        "distinct_nonempty_texts": len(texts),
        "reviews_covered_by_exact_text_reuse": (n - empty) - len(texts),
        "missing_app_version": missing_ver, "unparseable_timestamps": bad_ts,
        "reviews_by_rating": dict(sorted(ratings.items())), "reviews_by_month": dict(sorted(months.items())),
        "distinct_text_length_chars": {"p50": pct(.5), "p90": pct(.9), "p99": pct(.99),
                                       "max": lengths[-1] if lengths else 0, "total": sum(lengths)},
        "top_duplicate_texts": [{"count": c, "text": t[:80]} for c, t in top],
        "initial_status_counts": {"pending": n - empty, "quarantined": empty, "completed": 0},
        "seconds": round((datetime.now() - t0).total_seconds(), 1),
    }
    man = ROOT / "data" / "manifest.json"
    if man.exists():
        official = {k: v["sha256"] for k, v in json.loads(man.read_text())["files"].items()}
        report["matches_official_file"] = next((k for k, v in official.items() if v == source_sha), None)
        if report["matches_official_file"] == "spotify_reviews_18months.csv":
            checks = {k: {"observed": report[k], "expected": v, "ok": report[k] == v} for k, v in EXPECTED_FULL.items()}
            report["manifest_checks"] = checks
            if not all(c["ok"] for c in checks.values()):
                write_json(out / "ingestion_report.json.FAILED", report)
                raise SystemExit(f"[prepare] STOP: counts differ from manifest: {checks}")
    write_json(out / "data_manifest.json", {"input_file": csv_path.name, "input_sha256": source_sha,
                                            "input_bytes": report["input_bytes"], "records": n,
                                            "fields": list(FIELDS), "created_at": report["created_at"]})
    write_json(out / "ingestion_report.json", report)  # written last = the "done" marker
    log(f"[prepare] {n:,} rows | {empty} empty -> quarantined | {len(texts):,} distinct texts to label | "
        f"{missing_ver:,} missing app_version | {report['seconds']}s")
    return report
