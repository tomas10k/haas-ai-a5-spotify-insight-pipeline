"""Build site/data/site_data.json from saved run files (no model calls, no keys).

    python3 -m pipeline site

Reads every run listed in config/site_runs.json that exists. The website only reads this JSON.
"""
import csv, hashlib, json, re
from collections import Counter, defaultdict
from pathlib import Path
from .common import ROOT, read_jsonl, write_json, now

REPO = "https://github.com/tomas10k/haas-ai-a5-spotify-insight-pipeline"
MAX_REVIEWS = 1500


def _j(p, default=None):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else default


def _csv(p):
    p = Path(p)
    return list(csv.DictReader(open(p, encoding="utf-8", newline=""))) if p.exists() else []


def stage_calls(calls):
    by = defaultdict(lambda: {"attempts": 0, "succeeded": 0, "failed": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "seconds": 0.0})
    for c in calls:
        k = c.get("step") if c["role"] == "enrich" else c["role"]
        d = by[k]
        d["attempts"] += 1; d[c["outcome"]] += 1
        d["input_tokens"] += c.get("input_tokens") or 0; d["output_tokens"] += c.get("output_tokens") or 0
        d["cost_usd"] += c.get("cost_usd") or 0; d["seconds"] += c.get("seconds") or 0
        d["model"] = c["model"]
    return {k: {**v, "cost_usd": round(v["cost_usd"], 6), "seconds": round(v["seconds"], 2)} for k, v in by.items()}


def run_block(spec, golden_labels):
    rd = ROOT / "runs" / spec["run_id"]
    if not (rd / "records" / "status.json").exists():
        return {**spec, "status": "pending"}
    ing = _j(rd / "prepare" / "ingestion_report.json", {})
    texts = {t["text_sha"]: t for t in read_jsonl(rd / "prepare" / "texts.jsonl")}
    src = {s["review_id"]: s for s in read_jsonl(rd / "prepare" / "source_index.jsonl")}
    enriched = {r["text_sha"]: r for r in read_jsonl(rd / "enrich" / "enriched_texts.jsonl")}
    recs = {r["review_id"]: r for r in read_jsonl(rd / "records" / "enriched.jsonl")}
    calls = [json.loads(l) for l in open(rd / "calls.jsonl")] if (rd / "calls.jsonl").exists() else []
    mans = [json.loads(l) for l in open(rd / "run_manifests.jsonl")] if (rd / "run_manifests.jsonl").exists() else []
    first = mans[0] if mans else {}
    issues = (_j(rd / "group" / "issues.json") or {}).get("issues", {})
    ranking = _csv(rd / "rank" / "ranking.csv")
    rank_of = {r["issue_id"]: r for r in ranking}
    issue_of = {r["review_id"]: r["issue_id"] for r in _csv(rd / "group" / "membership.csv")}
    vpred = {r["text_sha"]: r for r in read_jsonl(rd / "verify" / "verifier_predictions.jsonl")} if (rd / "verify" / "verifier_predictions.jsonl").exists() else {}
    memo = (rd / "memo" / "memo.md").read_text() if (rd / "memo" / "memo.md").exists() else None
    memo_ids = set(re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", memo or ""))
    gdir = ROOT / "evals" / "golden_results" / spec["run_id"]
    golden = None
    if (gdir / "summary.json").exists():
        golden = {"summary": _j(gdir / "summary.json"), "confusion": list(csv.reader(open(gdir / "confusion_topic.csv")))}
    sc = stage_calls(calls)
    status = _j(rd / "records" / "status.json", {})
    # explorer items: one per distinct text, disagreements first
    items = []
    for ts, r in enriched.items():
        rid = r["origin_review_id"]; s = src[rid]; t = texts[ts]
        human = golden_labels.get(rid) if spec["key"] == "golden" else None
        v = vpred.get(ts)
        iss = issue_of.get(rid)
        items.append({
            "id": rid, "text": t["review_text"][:700], "stars": s["review_rating"], "date": s["review_timestamp"][:10],
            "copies": t["n_reviews"], "topic": r["topic"], "intent": r["intent"], "severity": r["severity"], "sentiment": r["sentiment"],
            "quote": r["evidence_quote"], "entities": r["entities"], "needs_review": r["needs_review"], "reasons": r.get("review_reasons", []),
            "decided_by": r.get("decided_by"), "jev": r.get("jev", {}),
            "verify": {k: v[k] for k in ("topic", "intent", "severity", "sentiment")} if v else None,
            "human": human, "issue": iss, "issue_name": issues.get(iss, {}).get("name"),
            "issue_rank": int(rank_of[iss]["rank"]) if iss in rank_of else None, "in_memo": rid in memo_ids})
    def prio(i):
        vd = i["verify"] and any(str(i["verify"][f]) != str(i[f]) for f in ("topic", "intent", "severity"))
        hd = i["human"] and any(str(i["human"][f]) != str(i[f]) for f in ("topic", "intent", "severity"))
        return (not (vd or hd), i["verify"] is None and i["human"] is None, hashlib.sha256(i["id"].encode()).hexdigest())
    items.sort(key=prio)
    return {**spec, "status": "done", "input_file": Path(first.get("input_file", "")).name,
            "label_config": first.get("label_config"), "workers": first.get("workers"),
            "wall_clock_seconds": first.get("wall_clock_seconds"), "stage_seconds": first.get("stage_seconds", {}),
            "rows_read": ing.get("records"), "distinct": ing.get("distinct_nonempty_texts"), "empty": ing.get("empty_review_text"),
            "reuse": ing.get("reviews_covered_by_exact_text_reuse"), "missing_version": ing.get("missing_app_version"),
            "records_status": status, "calls": sc, "total_cost_usd": round(sum(c.get("cost_usd") or 0 for c in calls), 6),
            "decided_by": dict(Counter(r.get("decided_by") for r in enriched.values())),
            "flagged": sum(1 for r in enriched.values() if r["needs_review"]),
            "distributions": {f: dict(Counter(str(r[f]) for r in recs.values())) for f in ("topic", "intent", "severity")},
            "verify": _j(rd / "verify" / "summary.json"), "golden": golden,
            "issues": {k: {"name": v["name"], "description": v["description"], "topic": v["topic"]} for k, v in issues.items()},
            "ranking": ranking, "topic_summary": _j(rd / "rank" / "topic_summary.json"),
            "memo": memo, "memo_check": _j(rd / "memo" / "memo_check.json"),
            "memo_model": next((c["model"] for c in reversed(calls) if c["role"] == "memo"), None),
            "reviews": items[:MAX_REVIEWS], "reviews_total": len(items)}


def cost_block():
    from .site_export_cost import build_cost
    return build_cost()


def build(log=print, out=None):
    specs = json.loads((ROOT / "config" / "site_runs.json").read_text())
    pilot = _j(ROOT / "cost" / "pilot_runs.json")
    golden_labels = {}
    gp = ROOT / "evals" / "golden_50_labeled.csv"
    for g in _csv(gp):
        golden_labels[g["review_id"]] = {"topic": g["topic"], "intent": g["intent"], "severity": int(g["severity"]),
                                         "sentiment": float(g["sentiment"]), "quote": g["evidence_quote"]}
    runs = []
    for s in specs:
        if s["run_id"] == "@pilot":
            s = {**s, "run_id": pilot["run_id"] if pilot else "none"}
        runs.append(run_block(s, golden_labels))
    data = {"generated_at": now(), "repo": REPO, "full_file": _j(ROOT / "docs" / "full_file_profile.json"),
            "runs": runs, "cost": cost_block()}
    out = Path(out or ROOT / "site" / "data" / "site_data.json")
    write_json(out, data)
    log(f"[site] wrote {out} ({out.stat().st_size // 1024} KB): " + ", ".join(f"{r['label']}={r['status']}" for r in runs))
    return data
