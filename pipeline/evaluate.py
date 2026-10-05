"""Golden set evaluation (code only, no model). Human labels never reach a model; this only compares.
Declared before seeing results: sentiment agrees when |difference| <= 0.25; also report MAE.
Out: evals/golden_results/<run_id>/{per_case.csv, summary.json, confusion_topic.csv, disagreements.md}
"""
import csv, json
from collections import Counter, defaultdict
from pathlib import Path
from .common import ROOT, TOPICS, INTENTS, read_jsonl, write_json, now

TOL = 0.25


def evaluate(run_dir, log=print):
    run_dir = Path(run_dir)
    gold = {r["review_id"]: r for r in csv.DictReader(open(ROOT / "evals" / "golden_50_labeled.csv", encoding="utf-8", newline=""))}
    pred = {r["review_id"]: r for r in read_jsonl(run_dir / "records" / "enriched.jsonl") if r["review_id"] in gold}
    out = ROOT / "evals" / "golden_results" / run_dir.name; out.mkdir(parents=True, exist_ok=True)
    rows, agg = [], Counter()
    conf = defaultdict(Counter)
    sev_err = sent_err = 0.0
    for rid, g in gold.items():
        p = pred.get(rid)
        if p is None:  # missing or quarantined counts as incorrect
            rows.append({"review_id": rid, "status": "missing", "text": g["review_text"][:160]}); agg["missing"] += 1
            continue
        gs, ps = int(g["severity"]), int(p["severity"])
        gt, pt = float(g["sentiment"]), float(p["sentiment"])
        q_ok = p["evidence_quote"] in g["review_text"]
        ents_unsupported = [e for e in p["entities"] if e.lower() not in g["review_text"].lower()]
        row = {"review_id": rid, "status": "scored", "text": g["review_text"][:160].replace("\n", " "),
               "gold_topic": g["topic"], "pred_topic": p["topic"], "topic_ok": g["topic"] == p["topic"],
               "gold_intent": g["intent"], "pred_intent": p["intent"], "intent_ok": g["intent"] == p["intent"],
               "gold_severity": gs, "pred_severity": ps, "severity_ok": gs == ps, "severity_abs_err": abs(gs - ps),
               "gold_sentiment": gt, "pred_sentiment": pt, "sentiment_ok": abs(gt - pt) <= TOL,
               "quote_exact_substring": q_ok, "pred_quote": p["evidence_quote"][:120],
               "entities_unsupported": ";".join(ents_unsupported),
               "gold_needs_review": g["needs_review"] == "true", "pred_needs_review": bool(p["needs_review"])}
        for k in ("topic_ok", "intent_ok", "severity_ok", "sentiment_ok", "quote_exact_substring"):
            agg[k] += row[k]
        sev_err += abs(gs - ps); sent_err += abs(gt - pt)
        conf[g["topic"]][p["topic"]] += 1
        agg["nr_tp"] += row["gold_needs_review"] and row["pred_needs_review"]
        agg["nr_fp"] += (not row["gold_needs_review"]) and row["pred_needs_review"]
        agg["nr_fn"] += row["gold_needs_review"] and not row["pred_needs_review"]
        rows.append(row)
    n = len(gold)  # denominator includes missing predictions
    scored = n - agg["missing"]
    # macro F1 over topics present in gold or predictions
    f1s = []
    for t in TOPICS:
        tp = conf[t][t]; fp = sum(conf[g][t] for g in conf if g != t); fn = sum(v for k, v in conf[t].items() if k != t)
        if tp + fp + fn:
            f1s.append(2 * tp / (2 * tp + fp + fn))
    summary = {"run_id": run_dir.name, "golden_n": n, "scored": scored, "missing_or_quarantined": agg["missing"],
               "topic_agreement": round(agg["topic_ok"] / n, 4), "topic_macro_f1": round(sum(f1s) / len(f1s), 4) if f1s else None,
               "intent_agreement": round(agg["intent_ok"] / n, 4), "severity_exact": round(agg["severity_ok"] / n, 4),
               "severity_mae": round(sev_err / scored, 4) if scored else None,
               "sentiment_within_0.25": round(agg["sentiment_ok"] / n, 4), "sentiment_mae": round(sent_err / scored, 4) if scored else None,
               "quote_exact_substring_rate": round(agg["quote_exact_substring"] / n, 4),
               "needs_review_precision": round(agg["nr_tp"] / (agg["nr_tp"] + agg["nr_fp"]), 4) if agg["nr_tp"] + agg["nr_fp"] else None,
               "needs_review_recall": round(agg["nr_tp"] / (agg["nr_tp"] + agg["nr_fn"]), 4) if agg["nr_tp"] + agg["nr_fn"] else None,
               "ambiguous_cases_declared": 8, "sentiment_tolerance_declared": TOL, "at": now(),
               "note": "50 cases is a small diagnostic sample, not a population accuracy estimate."}
    write_json(out / "summary.json", summary)
    keys = sorted({k for r in rows for k in r}, key=lambda k: list(rows[0].keys()).index(k) if k in rows[0] else 99)
    with open(out / "per_case.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)
    with open(out / "confusion_topic.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["gold \\ pred"] + list(TOPICS))
        for t in TOPICS:
            w.writerow([t] + [conf[t][p] for p in TOPICS])
    with open(out / "disagreements.md", "w", encoding="utf-8") as f:
        f.write(f"# Golden disagreements for run {run_dir.name}\n\n| review_id | text | field | gold | predicted |\n|---|---|---|---|---|\n")
        for r in rows:
            if r["status"] != "scored":
                f.write(f"| {r['review_id']} | {r['text'][:80]} | all | | missing |\n"); continue
            for fld in ("topic", "intent", "severity"):
                if not r[f"{fld}_ok"]:
                    f.write(f"| {r['review_id'][:8]} | {r['text'][:80]} | {fld} | {r['gold_' + fld]} | {r['pred_' + fld]} |\n")
    log(f"[eval] {summary}")
    return summary
