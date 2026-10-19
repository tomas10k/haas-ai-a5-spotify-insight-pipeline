"""Build the declared analysis scope (code only, no model).

The course allows a final run over at least 100,000 reviews instead of all 660,622. We pick them with the
SAME rule the course used for its samples (manifest.json -> samples.method):
    lowest SHA-256(seed + ':' + review_id) among unique, nonempty, valid-rating records.
So the scope is a uniform deterministic sample that nests the official files: ranks 1-50 are the golden 50,
ranks 51-10,050 are analysis_10000.csv (whose first 500 / 100 are checkpoint_500 / cost_100).
The 13 empty-text rows are appended so the run quarantines them explicitly (they are never classified).
Rows are written in rank order, so any prefix of the file is itself a uniform sample.

    python3 -m pipeline scope --n 100000 --out data/scope_100k.csv
"""
import csv, hashlib, heapq, json
from pathlib import Path
from .common import ROOT, FIELDS, csv_rows, file_sha, write_json, now


def build_scope(full_csv, n, out_csv, log=print):
    man = json.loads((ROOT / "data" / "manifest.json").read_text())
    seed = man["samples"]["seed"]
    heap, empties, seen = [], [], set()
    for r in csv_rows(full_csv):
        rid = r["review_id"]
        dup = rid in seen
        seen.add(rid)
        if not r["review_text"].strip():
            empties.append(r)
            continue
        if dup or not rid or r["review_rating"] not in {"1", "2", "3", "4", "5"}:
            continue
        rank = int.from_bytes(hashlib.sha256((seed + ":" + rid).encode()).digest(), "big")
        entry = (-rank, rid, r)
        if len(heap) < n:
            heapq.heappush(heap, entry)
        elif rank < -heap[0][0]:
            heapq.heapreplace(heap, entry)
    selected = [e[2] for e in sorted(heap, key=lambda x: (-x[0], x[1]))]
    # self check: the scope must nest the official samples exactly
    def ids(name):
        p = ROOT / "data" / name
        return [r["review_id"] for r in csv_rows(p)] if p.exists() else None
    checks = {}
    for name, lo, hi in (("golden_50_to_label.csv", 0, 50), ("analysis_10000.csv", 50, 10050)):
        want = ids(name)
        if want is not None:
            checks[name] = [r["review_id"] for r in selected[lo:hi]] == want
    if not all(checks.values()):
        raise SystemExit(f"[scope] STOP: scope does not reproduce the official samples: {checks}")
    out_csv = Path(out_csv)
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(selected + empties)
    info = {"created_at": now(), "full_input": Path(full_csv).name, "full_sha256": file_sha(full_csv),
            "method": man["samples"]["method"], "seed": seed, "sampled_nonempty": len(selected),
            "empty_text_rows_appended": len(empties), "rows": len(selected) + len(empties),
            "order": "rank order (golden 50, then analysis_10000, then the next lowest hashes), empty texts last",
            "nests_official_samples": checks, "output": str(out_csv.relative_to(ROOT)) if out_csv.is_relative_to(ROOT) else str(out_csv),
            "output_sha256": file_sha(out_csv)}
    write_json(out_csv.with_suffix(".json"), info)
    log(f"[scope] {info['rows']:,} rows ({len(selected):,} sampled + {len(empties)} empty) -> {out_csv} | checks {checks}")
    return info
