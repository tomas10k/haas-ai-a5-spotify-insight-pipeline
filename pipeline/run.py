"""Orchestrator: code decides what runs next, passes saved files between stages, enforces budgets and logs.

    prepare (code) -> enrich (Jev + capped Haiku) -> records (code) -> verify (Haiku sample)
      -> group (code membership + Haiku names) -> rank (SQL) -> memo (Haiku) with code checks
Each stage reads only the previous stage's saved files, so any stage can be rerun or resumed.
"""
import hashlib, json, subprocess, time
from pathlib import Path
from .common import ROOT, load_config, write_json, append_jsonl, now, file_sha
from .prepare import prepare
from .enrich import run_enrich, label_config
from .records import build_records, completed_review_ids
from .verify import run_verify
from .group import run_group
from .rank import run_rank
from .memo import run_memo

ALL = ["prepare", "enrich", "records", "verify", "group", "rank", "memo"]


def code_version():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        h = hashlib.sha256()
        for p in sorted((ROOT / "pipeline").glob("*.py")):
            h.update(p.read_bytes())
        return "nogit-" + h.hexdigest()[:10]


def run(input_csv, run_id, stages=None, workers=None, limit=None, stop_after=None, spend_cap=None, log=print):
    cfg = load_config()
    if spend_cap is not None:
        cfg["budget"]["spend_cap_usd"] = spend_cap
    workers = workers or cfg["enrich"]["workers"]
    run_dir = ROOT / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    stages = stages or ALL
    prompt = json.loads((ROOT / cfg["enrich"]["prompt_file"]).read_text())
    manifest = {"run_id": run_id, "input_file": str(input_csv), "code_version": code_version(), "started_at": now(),
                "label_config": label_config(cfg, prompt), "settings": cfg, "workers": workers, "limit": limit,
                "prompts": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()[:16] for p in sorted((ROOT / "prompts").glob("*"))}}
    timings, t_all = {}, time.monotonic()
    for st in stages:
        t0 = time.monotonic()
        if st == "prepare":
            rep = prepare(input_csv, run_dir, log); manifest["input_sha256"] = rep["input_sha256"]
        elif st == "enrich":
            s = run_enrich(run_dir, cfg, workers=workers, limit=limit, stop_after=stop_after, log=log)
            snap = {"run_id": run_id, "phase": s["phase"], "stop_reason": s["stop_reason"], "saved_at": now(),
                    "completed_ids": completed_review_ids(run_dir)}
            cp = run_dir / "enrich" / "checkpoints"; cp.mkdir(exist_ok=True)
            write_json(cp / f"{time.strftime('%Y%m%d_%H%M%S')}_{s['phase']}.json", snap)
            log(f"[checkpoint] saved {len(snap['completed_ids']):,} completed review IDs")
            if s["stop_reason"] != "finished":
                manifest["stopped"] = s["stop_reason"]
                timings[st] = round(time.monotonic() - t0, 2)
                log(f"[run] stopped during enrich ({s['stop_reason']}); rerun the same command to resume")
                break
        elif st == "records":
            build_records(run_dir, log)
        elif st == "verify":
            run_verify(run_dir, cfg, log)
        elif st == "group":
            run_group(run_dir, cfg, log)
        elif st == "rank":
            run_rank(run_dir, log)
        elif st == "memo":
            run_memo(run_dir, cfg, log)
        timings[st] = round(time.monotonic() - t0, 2)
        append_jsonl(run_dir / "run_log.jsonl", {"stage": st, "seconds": timings[st], "at": now()})
    manifest.update(finished_at=now(), stage_seconds=timings, wall_clock_seconds=round(time.monotonic() - t_all, 2))
    hist = run_dir / "run_manifests.jsonl"
    append_jsonl(hist, manifest)
    summarize(run_dir)
    return manifest


def summarize(run_dir):
    run_dir = Path(run_dir)
    calls = [json.loads(l) for l in open(run_dir / "calls.jsonl")] if (run_dir / "calls.jsonl").exists() else []
    by = {}
    for c in calls:
        k = (c["role"], c.get("step", c["role"]), c["model"])
        d = by.setdefault(k, {"attempts": 0, "succeeded": 0, "failed": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0})
        d["attempts"] += 1; d[c["outcome"]] += 1
        d["input_tokens"] += c.get("input_tokens") or 0; d["output_tokens"] += c.get("output_tokens") or 0
        d["cost_usd"] += c.get("cost_usd") or 0
    status = json.loads((run_dir / "records" / "status.json").read_text()) if (run_dir / "records" / "status.json").exists() else {}
    write_json(run_dir / "run_summary.json", {"run_id": run_dir.name, "status": status,
               "calls_by_stage": [{"role": k[0], "step": k[1], "model": k[2], **v, "cost_usd": round(v["cost_usd"], 6)} for k, v in by.items()],
               "total_cost_usd": round(sum(v["cost_usd"] for v in by.values()), 6), "at": now()})
