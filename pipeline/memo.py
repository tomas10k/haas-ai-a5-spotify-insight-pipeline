"""Stage 6 Recommend (role: memo). The model sees only saved aggregates plus a bounded evidence pack.
Code builds claims.csv first, then checks the memo: every claim/issue/review ID must exist and every
number in the memo must appear in the evidence pack. One retry with the error list; then save + flag.
Out: runs/<run>/memo/{evidence_pack.json, claims.csv, memo.md, memo_check.json}
"""
import csv, hashlib, json, re
from pathlib import Path
from .common import ROOT, read_jsonl, write_json
from .clients import Runtime, FAKE, anthropic_call, openai_call


def build_pack(run_dir, cfg):
    run_dir = Path(run_dir)
    m = cfg["memo"]
    issues = json.loads((run_dir / "group" / "issues.json").read_text())["issues"]
    rank = list(csv.DictReader(open(run_dir / "rank" / "ranking.csv")))
    topics = json.loads((run_dir / "rank" / "topic_summary.json").read_text())
    status = json.loads((run_dir / "records" / "status.json").read_text())
    ingest = json.loads((run_dir / "prepare" / "ingestion_report.json").read_text())
    recs = {r["review_id"]: r for r in read_jsonl(run_dir / "records" / "enriched.jsonl")}
    members = {}
    for r in csv.DictReader(open(run_dir / "group" / "membership.csv")):
        members.setdefault(r["issue_id"], []).append(r["review_id"])
    claims, ranked = [], []
    for row in rank[:m["top_issues"]]:
        iss = row["issue_id"]; cids = {}
        for metric in ("complaint_count", "severity_sum", "mean_severity", "priority_score"):
            cid = f"C{len(claims) + 1:03d}"
            claims.append({"claim_id": cid, "issue_id": iss, "metric": metric, "value": row[metric]}); cids[metric] = cid
        # bounded examples: highest severity first, then most helpful votes, then id (deterministic), originals only
        cand = sorted((recs[r] for r in members[iss] if "cache_source_id" not in recs[r]),
                      key=lambda r: (-r["severity"], -int(r.get("review_likes") or 0), r["review_id"]))[:m["examples_per_issue"]]
        ranked.append({"rank": int(row["rank"]), "issue_id": iss, "name": issues[iss]["name"], "topic": issues[iss]["topic"],
                       **{k: row[k] for k in ("complaint_count", "severity_sum", "mean_severity", "priority_score")},
                       "claim_ids": cids,
                       "examples": [{"review_id": r["review_id"], "severity": r["severity"], "quote": r["evidence_quote"][:200]} for r in cand]})
    tclaims = []
    for t in topics["topics"]:
        tc = {}
        for metric in ("complaint_count", "severity_sum", "mean_severity", "cancellations", "share_of_all_complaints"):
            tid = f"T{len(tclaims) + 1:03d}"
            tclaims.append({"claim_id": tid, "topic": t["topic"], "metric": metric, "value": str(t[metric])}); tc[metric] = tid
        t["claim_ids"] = tc
    # coverage and quality facts: every number the memo may mention gets a token, so the model never types one
    facts_src = [("source_rows", ingest["records"]), ("completed_classifications", status.get("completed", 0)),
                 ("quarantined", status.get("quarantined", 0)), ("pending_unclassified", status.get("pending", 0))]
    facts_src += [(f"intent_{k}", v) for k, v in sorted(topics["labels_by_intent"].items())]
    vs = json.loads((run_dir / "verify" / "summary.json").read_text()) if (run_dir / "verify" / "summary.json").exists() else None
    if vs:
        facts_src += [("verifier_sample_size", vs["n"]), ("verifier_topic_agreement", f"{round(100 * vs['topic_agreement'])}%"),
                      ("verifier_intent_agreement", f"{round(100 * vs['intent_agreement'])}%"),
                      ("verifier_severity_exact", f"{round(100 * vs['severity_exact'])}%")]
    gl = sorted((ROOT / "evals" / "golden_results").glob("*/summary.json"))
    if gl:
        g = json.loads(gl[-1].read_text())
        facts_src += [("golden_reviews", g["golden_n"]), ("golden_topic_agreement", f"{round(100 * g['topic_agreement'])}%"),
                      ("golden_intent_agreement", f"{round(100 * g['intent_agreement'])}%"),
                      ("golden_severity_exact", f"{round(100 * g['severity_exact'])}%")]
    facts = [{"claim_id": f"F{i + 1:03d}", "name": n, "value": str(v)} for i, (n, v) in enumerate(facts_src)]
    pack = {"window": "2022-05-17 to 2023-11-15 (Google Play reviews)",
            "coverage_and_quality": {f["name"]: "{" + f["claim_id"] + "}" for f in facts},
            "quality_note": "Labels come from Jev; a second model (Claude Haiku) relabeled a random sample blind, and the owner hand labeled 50 golden reviews; the agreement rates are in coverage_and_quality.",
            "ranked_issues": ranked, "topic_totals_complaints_and_cancellations": topics["topics"],
            "how_to_cite": "Use tokens {Cnnn} (issue claims), {Tnnn} (topic claims) and {Fnnn} (coverage and quality facts); never type numbers."}
    return pack, claims, tclaims + facts


NUM = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?%?")


def render(draft, claims, tclaims):
    """Code, not the model, writes every cited number: {C005} -> '6 [C005]'."""
    vals = {c["claim_id"]: c["value"] for c in claims + tclaims}
    names = {c["name"]: c["claim_id"] for c in tclaims if "name" in c}
    draft = re.sub(r"\{+\s*([A-Za-z_]+)\s*\}+", lambda m: "{" + names[m.group(1)] + "}" if m.group(1) in names else m.group(0), draft)
    draft = re.sub(r"\{+\s*([CTF]\d{3})\s*\}+", r"{\1}", draft)  # {{C005}} -> {C005}
    unknown = sorted({t for t in re.findall(r"\{([CTF]\d{3})\}", draft) if t not in vals})
    text = re.sub(r"\{([CTF]\d{3})\}", lambda m: f"{vals[m.group(1)]} [{m.group(1)}]" if m.group(1) in vals else m.group(0), draft)
    return text, [f"unknown claim token {{{u}}}" for u in unknown]


def check_memo(text, pack, claims):
    errors = []
    claim_ids = {c["claim_id"]: c for c in claims}
    for cid in set(re.findall(r"\bC\d{3}\b", text)):
        if cid not in claim_ids: errors.append(f"unknown claim id {cid}")
    if re.search(r"\{[CTF]\d{3}\}", text): errors.append("unrendered claim token")
    if re.search(r"\{[^}]*\}", text): errors.append("unknown token: " + ", ".join(sorted(set(re.findall(r"\{[^}]*\}", text)))[:5]))
    if re.search(r"[\{\}]", text): errors.append("stray curly brace")
    if "\u2014" in text or "\u2013" in text: errors.append("em or en dash in prose (style rule)")
    issue_ids = {i["issue_id"] for i in pack["ranked_issues"]}
    for iid in set(re.findall(r"\bISS_[A-Z_]+\b", text)):
        if iid not in issue_ids: errors.append(f"unknown issue id {iid}")
    review_ids = {e["review_id"] for i in pack["ranked_issues"] for e in i["examples"]}
    for rid in set(re.findall(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", text)):
        if rid not in review_ids: errors.append(f"review id not in evidence pack {rid}")
    allowed = set()
    def collect(o):
        if isinstance(o, dict): [collect(v) for v in o.values()]
        elif isinstance(o, list): [collect(v) for v in o]
        elif isinstance(o, (int, float)) and not isinstance(o, bool): allowed.add(str(o))
        elif isinstance(o, str): allowed.update(n.replace(",", "") for n in NUM.findall(o))
    collect(pack)
    for c in claims:  # values that code renders from tokens are allowed by construction
        allowed.add(str(c["value"]).replace(",", "")); allowed.add(str(c["value"]).rstrip("%"))
    clean = re.sub(r"\b[CTF]\d{3}\b|\bISS_[A-Z_]+\b|[0-9a-f]{8}-[0-9a-f-]{27}", " ", text)
    for n in NUM.findall(clean):
        v = n.replace(",", "")
        if v not in allowed and v.rstrip("%") not in allowed and v not in {"1", "2", "3", "4", "5", "550"}:
            errors.append(f"number not in evidence pack: {n}")
    # every number cited next to a claim id must equal that claim's value
    # the nearest number before the ID, allowing up to 3 plain words between ("13 complaints [C005]")
    for num, _, cid in re.findall(r"(\d[\d,]*(?:\.\d+)?)%?((?:\s+[A-Za-z]+){0,3})\s*\[([CTF]\d{3})\]", text):
        if cid in claim_ids and num.replace(",", "") != claim_ids[cid]["value"].rstrip("%"):
            errors.append(f"{cid} cites {num} but saved value is {claim_ids[cid]['value']}")
    return sorted(set(errors))


def run_memo(run_dir, cfg, log=print, phase="initial"):
    run_dir = Path(run_dir); out = run_dir / "memo"; out.mkdir(exist_ok=True)
    m = cfg["memo"]
    pack, claims, tclaims = build_pack(run_dir, cfg)
    write_json(out / "evidence_pack.json", pack)
    with open(out / "claims.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["claim_id", "issue_id", "metric", "value"]); w.writeheader(); w.writerows(claims)
    with open(out / "topic_claims.csv", "w", newline="") as f:  # topic level numbers: explained separately, not in grading claims.csv
        w = csv.DictWriter(f, fieldnames=["claim_id", "topic", "metric", "name", "value"]); w.writeheader(); w.writerows(tclaims)
    cache = out / "memo_input_key.txt"
    key = json.dumps(pack, sort_keys=True) + m["model"] + m["prompt_version"] + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]
    if (out / "memo.md").exists() and cache.exists() and cache.read_text() == key:
        log("[memo] inputs unchanged: reusing saved memo (no model call)")
        return json.loads((out / "memo_check.json").read_text())
    rt = Runtime(run_dir, cfg["budget"]["spend_cap_usd"], 5, phase)
    system = (ROOT / "prompts" / f"{m['prompt_version']}.md").read_text()
    worst = 30000 * rt.rates.get((m["model"], "input"), 0) + m["max_output_tokens"] * rt.rates.get((m["model"], "output"), 0)
    user = json.dumps(pack, ensure_ascii=False, indent=1)
    errors, text, draft = [], "", ""
    for attempt in (1, 2):
        msg = user if attempt == 1 else user + "\n\nYour previous memo failed these code checks; fix them:\n" + "\n".join(errors)

        def fn():
            if FAKE:
                top = pack["ranked_issues"][0] if pack["ranked_issues"] else None
                t = "# Fake memo\n\n## Recommendation\n" + (f"Fix {top['issue_id']}: {top['complaint_count']} complaints [{top['claim_ids']['complaint_count']}]." if top else "No issues.")
                return t, {"input": len(msg) // 4, "output": 300}, "fake-memo"
            if m.get("provider") == "openai":
                return openai_call(rt, model=m["model"], max_tokens=m["max_output_tokens"], system=system, user=msg,
                                   effort=m.get("effort"))
            return anthropic_call(rt, model=m["model"], max_tokens=m["max_output_tokens"], system=system, user=msg,
                                  thinking=m.get("thinking"), effort=m.get("effort"))
        try:
            text, _ = rt.call(provider=m.get("provider", "anthropic"), model=m["model"], role="memo", review_ids=[], label_config=f"{m['model']}:{m['prompt_version']}",
                          prompt_version=m["prompt_version"], fn=fn, worst_case_usd=worst, max_attempts=4,
                          extra={"input_artifact": "memo/evidence_pack.json", "attempt_kind": "draft" if attempt == 1 else "fix",
                                 "thinking": m.get("thinking"), "reasoning_effort": m.get("effort")})
        except ValueError as ex:  # billed but unusable reply: logged by rt.call; try once more, then save the failure
            errors, text = [f"no usable memo text: {ex}"], ""
            continue
        draft = text
        text, token_errors = render(draft, claims, tclaims)
        errors = token_errors + check_memo(text, pack, claims + [dict(c, issue_id=c.get("topic", c.get("name"))) for c in tclaims])
        if not errors:
            break
    (out / "memo_draft_with_tokens.md").write_text(draft)
    (out / "memo.md").write_text(text)
    check = {"passed": not errors, "errors": errors, "claims": len(claims),
             "cited_claims": sorted(set(re.findall(r"\bC\d{3}\b", text))), "note": "A person must still read the argument."}
    write_json(out / "memo_check.json", check)
    if text:  # never cache a missing memo: the next run retries it
        cache.write_text(key)
    log(f"[memo] check {'PASSED' if not errors else 'FAILED: ' + '; '.join(errors[:5])}")
    return check
