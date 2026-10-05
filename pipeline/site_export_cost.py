"""Calculator inputs for the website: measured pilot token counts per stage + editable assumptions.
Costs are never stored here: the page multiplies tokens x prices live, like cost/calculator.py."""
import csv, json
from .common import ROOT


def build_cost():
    C = ROOT / "cost"
    rates = list(csv.DictReader(open(C / "rates.csv")))
    A = json.loads((C / "assumptions.json").read_text())
    if not (C / "pilot_runs.json").exists():
        return {"available": False, "rates": rates, "assumptions": A}
    runs = json.loads((C / "pilot_runs.json").read_text())
    calls = [json.loads(l) for l in open(C / "pilot_calls.jsonl")]
    long_ids = set(runs.get("long_review_ids", []))
    cold = [c for c in calls if c["pilot_run"] == "cold"]
    mean = lambda xs: sum(xs) / len(xs) if xs else 0
    def tok(f, k):
        return sum((c.get(k) or 0) for c in cold if f(c))
    jev = [c for c in cold if c.get("step") == "jev_classify"]
    jev_ok = [c for c in jev if c["outcome"] == "succeeded"]
    fb = [c for c in cold if c.get("step") == "haiku_fallback"]
    ver = [c for c in cold if c["role"] == "verify"]
    ver_reviews = sum(len(c["review_ids"]) for c in ver if c["outcome"] == "succeeded") or 1
    measured = {
        "texts": runs["unique_texts"],
        "jev": {"model": jev[0]["model"] if jev else "jev-1.13.0",
                "in_short": mean([c["input_tokens"] for c in jev_ok if c["review_ids"][0] not in long_ids]),
                "in_long": mean([c["input_tokens"] for c in jev_ok if c["review_ids"][0] in long_ids]),
                "attempts_per_text": len(jev) / runs["unique_texts"],
                "texts_per_second_1_worker": runs["unique_texts"] / max(runs["cold"]["stage_seconds"].get("enrich", 1), 1e-9)},
        "fallback": {"rate": len({c["review_ids"][0] for c in fb if c["outcome"] == "succeeded"}) / runs["unique_texts"],
                     "in_per_call": mean([c.get("input_tokens") or 0 for c in fb]), "out_per_call": mean([c.get("output_tokens") or 0 for c in fb])},
        "verify": {"in_per_review": tok(lambda c: c["role"] == "verify", "input_tokens") / ver_reviews,
                   "out_per_review": tok(lambda c: c["role"] == "verify", "output_tokens") / ver_reviews},
        "group": {"in": tok(lambda c: c["role"] == "group", "input_tokens"), "out": tok(lambda c: c["role"] == "group", "output_tokens")},
        "models": {k: next((c["model"] for c in cold if (c.get("step") if c["role"] == "enrich" else c["role"]) == k), None)
                   for k in ("haiku_fallback", "verify", "group", "memo")},
        "memo": {"in": tok(lambda c: c["role"] == "memo", "input_tokens"), "out": tok(lambda c: c["role"] == "memo", "output_tokens"),
                 "attempts": sum(1 for c in cold if c["role"] == "memo")},
    }
    steps = {}
    for c in calls:
        k = (c["pilot_run"], c.get("step") if c["role"] == "enrich" else c["role"], c["model"])
        d = steps.setdefault(k, {"run": k[0], "step": k[1], "model": k[2], "attempts": 0, "failed": 0, "input": 0, "output": 0})
        d["attempts"] += 1; d["failed"] += c["outcome"] == "failed"
        d["input"] += c.get("input_tokens") or 0; d["output"] += c.get("output_tokens") or 0
    return {"available": True, "rates": rates, "assumptions": A, "measured": measured, "pilot_steps": list(steps.values()),
            "pilot": {"run_id": runs["run_id"], "ids": runs["ids"], "input_sha256": runs["input_sha256"],
                      "cold_seconds": runs["cold"]["wall_clock_seconds"], "warm_seconds": runs["warm"]["wall_clock_seconds"],
                      "warm_enrich_calls": sum(1 for c in calls if c["pilot_run"] == "warm" and c["role"] == "enrich")},
            "estimates": {"haiku_only_in_per_review": 45, "haiku_only_out_per_review": 35, "haiku_only_reviews_per_second_1_worker": 5,
                          "note": "Haiku only labeling was not run: per review tokens assume 50 reviews per request sharing one prompt. Edit on the page."},
            "check": json.loads((C / "arithmetic_check.json").read_text()) if (C / "arithmetic_check.json").exists() else None}
