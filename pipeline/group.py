"""Stage 4 Group (role: group). Code owns membership; a small model only suggests readable names.

In : runs/<run>/records/enriched.jsonl
Out: runs/<run>/group/membership.csv (issue_id,review_id)  one issue per complaint/cancellation review
     runs/<run>/group/issues.json  stable issue IDs, rule, member count, accepted name/description
Ranking later needs only these saved files, never a model.
"""
import csv, hashlib, json, re
from collections import defaultdict
from pathlib import Path
from .common import ROOT, read_jsonl, write_json
from .clients import Runtime, FAKE, anthropic_call


def assign_issue(topic, text_low, rules):
    for code, pat in rules.get(topic, []):
        if re.search(pat, text_low):
            return f"ISS_{topic.upper()}_{code}"
    return f"ISS_{topic.upper()}_GENERAL"


def run_group(run_dir, cfg, log=print, use_model=True, phase="initial"):
    run_dir = Path(run_dir); out = run_dir / "group"; out.mkdir(exist_ok=True)
    rules = json.loads((ROOT / "config" / "issues.json").read_text())["subtopics"]
    texts = {t["text_sha"]: t["review_text"] for t in read_jsonl(run_dir / "prepare" / "texts.jsonl")}
    idx = {s["review_id"]: s["text_sha"] for s in read_jsonl(run_dir / "prepare" / "source_index.jsonl")}
    members, examples = defaultdict(list), defaultdict(dict)
    for r in read_jsonl(run_dir / "records" / "enriched.jsonl"):
        if r["intent"] not in ("complaint", "cancellation"):
            continue
        iss = assign_issue(r["topic"], texts[idx[r["review_id"]]].lower(), rules)
        members[iss].append(r["review_id"])
        q = r["evidence_quote"]
        examples[iss].setdefault(q, r["review_id"])  # distinct quotes only
    with open(out / "membership.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["issue_id", "review_id"])
        for iss in sorted(members):
            for rid in sorted(members[iss]):
                w.writerow([iss, rid])
    # bounded evidence pack for naming: up to N distinct quotes per issue, deterministic pick
    k = cfg["group"]["examples_per_issue"]
    pack = {}
    for iss in sorted(members):
        qs = sorted(examples[iss].items(), key=lambda kv: hashlib.sha256(kv[1].encode()).hexdigest())[:k]
        pack[iss] = {"rule": iss.split("_", 2)[2], "examples": [q[:200] for q, _ in qs]}
    names = {}
    old = out / "issues.json"
    if old.exists():  # reuse accepted names for unchanged issue IDs (no new call)
        names = {i: {"name": v["name"], "description": v["description"]} for i, v in json.loads(old.read_text())["issues"].items()
                 if v.get("named_by") == "model"}
    need = [i for i in pack if i not in names]
    if use_model and need:
        rt = Runtime(run_dir, cfg["budget"]["spend_cap_usd"], 5, phase)
        g = cfg["group"]
        body = json.dumps({i: pack[i] for i in need}, ensure_ascii=False, indent=1)

        def fn():
            if FAKE:
                return {i: {"name": i.replace("ISS_", "").replace("_", " ").title(), "description": "Fake name."} for i in need}, \
                    {"input": 400 + len(body) // 4, "output": 40 * len(need)}, "fake-group"
            txt, usage, rid = anthropic_call(rt, model=g["model"], max_tokens=g["max_output_tokens"],
                                             system=(ROOT / "prompts" / f"{g['prompt_version']}.md").read_text(), user=body)
            mm = re.search(r"\{.*\}", txt, re.S)
            try:
                return (json.loads(mm.group(0)) if mm else {}), usage, rid
            except json.JSONDecodeError:
                return {}, usage, rid  # names are optional: code falls back to rule based names
        worst = 20000 * rt.rates.get((g["model"], "input"), 0) + g["max_output_tokens"] * rt.rates.get((g["model"], "output"), 0)
        got, _ = rt.call(provider="anthropic", model=g["model"], role="group", review_ids=[], label_config=f"{g['model']}:{g['prompt_version']}",
                         prompt_version=g["prompt_version"], fn=fn, worst_case_usd=worst, max_attempts=4,
                         extra={"input_artifact": "group/membership.csv + bounded examples"})
        for i, v in (got or {}).items():
            if i in pack and isinstance(v, dict) and v.get("name"):  # reject unknown IDs
                names[i] = {"name": str(v["name"])[:60], "description": str(v.get("description", ""))[:200]}
    issues = {}
    for i in sorted(members):
        nm = names.get(i)
        issues[i] = {"topic": i.split("_")[1].lower(), "rule": pack[i]["rule"], "members": len(members[i]),
                     "name": nm["name"] if nm else i.replace("ISS_", "").replace("_", " ").title(),
                     "description": nm["description"] if nm else "", "named_by": "model" if nm else "code",
                     "examples": pack[i]["examples"]}
    write_json(out / "issues.json", {"rules_file": "config/issues.json", "issues": issues})
    log(f"[group] {len(issues)} issues, {sum(len(v) for v in members.values()):,} memberships")
    return issues
