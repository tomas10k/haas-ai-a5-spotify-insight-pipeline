"""Stage 3 Verify (role: verify). Haiku relabels a declared random sample WITHOUT seeing Jev's answer.
Code compares. Out: runs/<run>/verify/{sample_ids.json, verifier_predictions.jsonl, comparison.csv, summary.json}
"""
import csv, hashlib, json, re
from pathlib import Path
from .common import ROOT, TOPICS, INTENTS, read_jsonl, write_json, append_jsonl, now
from .clients import Runtime, FAKE, anthropic_call, ReplyError
from .records import load_texts_results


def _sample(res, cfg):
    v = cfg["verify"]
    n = min(len(res), max(v["min_sample"], min(v["max_sample"], round(v["sample_fraction"] * len(res)))))
    key = lambda ts: hashlib.sha256((v["seed"] + ":" + ts).encode()).hexdigest()
    return sorted(res, key=key)[:n]


def _validate(arr, k):
    if not isinstance(arr, list) or len(arr) != k:
        raise ValueError(f"expected {k} items")
    seen = set()
    for o in arr:
        if o.get("i") not in range(1, k + 1) or o["i"] in seen: raise ValueError("bad or repeated i")
        seen.add(o["i"])
        if o.get("topic") not in TOPICS or o.get("intent") not in INTENTS: raise ValueError("label not allowed")
        if o.get("severity") not in (1, 2, 3, 4, 5): raise ValueError("severity not allowed")
        if not -1 <= float(o.get("sentiment", 9)) <= 1: raise ValueError("sentiment out of range")
    return {o["i"]: o for o in arr}


def run_verify(run_dir, cfg, log=print, phase="initial"):
    run_dir, v = Path(run_dir), cfg["verify"]
    out = run_dir / "verify"; out.mkdir(exist_ok=True)
    res, _ = load_texts_results(run_dir)
    texts = {t["text_sha"]: t["review_text"] for t in read_jsonl(run_dir / "prepare" / "texts.jsonl")}
    sample = _sample(res, cfg)
    write_json(out / "sample_ids.json", {"declared_fraction": v["sample_fraction"], "min": v["min_sample"], "max": v["max_sample"],
                                         "seed": v["seed"], "n": len(sample),
                                         "origin_review_ids": [res[s]["origin_review_id"] for s in sample]})
    pred_path = out / "verifier_predictions.jsonl"
    have = {}
    if pred_path.exists():
        for r in read_jsonl(pred_path):
            have[r["text_sha"]] = r
    todo = [s for s in sample if s not in have]
    rt = Runtime(run_dir, cfg["budget"]["spend_cap_usd"], 5, phase)
    system = (ROOT / "prompts" / f"{v['prompt_version']}.md").read_text()
    worst = 6000 * rt.rates.get((v["model"], "input"), 0) + v["max_output_tokens"] * rt.rates.get((v["model"], "output"), 0)
    k = v["reviews_per_call"]
    for b in range(0, len(todo), k):
        chunk = todo[b:b + k]
        body = "\n".join(f'<review i="{i + 1}">\n{texts[ts]}\n</review>' for i, ts in enumerate(chunk))
        ids = [res[ts]["origin_review_id"] for ts in chunk]

        def fn():
            if FAKE:
                return [{"i": i + 1, "topic": res[ts]["topic"] if i % 4 else "other", "intent": res[ts]["intent"],
                         "severity": res[ts]["severity"], "sentiment": res[ts]["sentiment"]} for i, ts in enumerate(chunk)], \
                    {"input": 900 + 60 * len(chunk), "output": 30 * len(chunk)}, "fake-verify"
            txt, usage, rid = anthropic_call(rt, model=v["model"], max_tokens=v["max_output_tokens"], system=system, user=body)
            mm = re.search(r"\[.*\]", txt, re.S)
            try:
                return (json.loads(mm.group(0)) if mm else None), usage, rid
            except json.JSONDecodeError as ex:
                raise ReplyError(f"unparseable verifier JSON: {ex}", usage, rid)
        got = None
        for attempt in (1, 2):  # one retry on invalid output
            try:
                arr, rec = rt.call(provider="anthropic", model=v["model"], role="verify", review_ids=ids,
                                   label_config=f"{v['model']}:{v['prompt_version']}", prompt_version=v["prompt_version"],
                                   fn=fn, worst_case_usd=worst, max_attempts=4)
                got = _validate(arr, len(chunk))
                break
            except (ValueError, TypeError, AttributeError) as ex:
                log(f"[verify] invalid verifier output ({ex}), attempt {attempt}")
        if got is None:
            continue
        for i, ts in enumerate(chunk):
            o = got[i + 1]
            row = {"text_sha": ts, "origin_review_id": res[ts]["origin_review_id"], "topic": o["topic"], "intent": o["intent"],
                   "severity": int(o["severity"]), "sentiment": float(o["sentiment"]), "request_id": rec["request_id"]}
            append_jsonl(pred_path, row); have[ts] = row
    return compare(run_dir, res, have, texts, log)


def compare(run_dir, res, have, texts, log=print, out_name="comparison.csv", summary_name="summary.json"):
    out = Path(run_dir) / "verify"
    rows, agree = [], {"topic": 0, "intent": 0, "severity": 0}
    sev_err = sent_err = 0.0
    for ts, p in have.items():
        e = res[ts]
        d = {f: e[f] == p[f] for f in ("topic", "intent", "severity")}
        for f in d: agree[f] += d[f]
        sev_err += abs(e["severity"] - p["severity"]); sent_err += abs(e["sentiment"] - p["sentiment"])
        rows.append({"origin_review_id": e["origin_review_id"], "text": texts[ts][:200].replace("\n", " "),
                     "enrich_topic": e["topic"], "verify_topic": p["topic"], "enrich_intent": e["intent"],
                     "verify_intent": p["intent"], "enrich_severity": e["severity"], "verify_severity": p["severity"],
                     "enrich_needs_review": e["needs_review"],
                     "disagree": ";".join(f for f, ok in d.items() if not ok)})
    n = len(rows)
    with open(out / out_name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["origin_review_id"]); w.writeheader(); w.writerows(rows)
    dis = [r for r in rows if r["disagree"]]
    summary = {"n": n, "topic_agreement": round(agree["topic"] / n, 4) if n else None,
               "intent_agreement": round(agree["intent"] / n, 4) if n else None,
               "severity_exact": round(agree["severity"] / n, 4) if n else None,
               "severity_mae": round(sev_err / n, 4) if n else None, "sentiment_mae": round(sent_err / n, 4) if n else None,
               "disagreements": len(dis),
               "disagreements_flagged_needs_review": sum(1 for r in dis if r["enrich_needs_review"]), "at": now()}
    write_json(out / summary_name, summary)
    log(f"[verify] {summary}")
    return summary
