#!/usr/bin/env bash
# Interruption / resume demonstration for the screen recording (about 3 minutes).
#   bash demo/resume_demo.sh
# Part 1 shows the saved evidence of the final run (free). Part 2 runs a fresh, live stop and resume on the
# 100 review file with real model calls (Jev only, less than $0.01). Press Enter to move between steps.
set -e
cd "$(dirname "$0")/.."
PY=.venv/bin/python
pause() { echo; read -r -p "  [Enter] $1 " _; echo; }
title() { printf '\n\033[1;34m=== %s ===\033[0m\n' "$1"; }

title "PART 1 · The final 100,000 review run (saved evidence, no new calls)"
echo "Phase 1 was started with --stop-after 25000 (a deliberate interruption). Its console log says:"
grep -E "^\S*\[(prepare|enrich|checkpoint|run)\]" runs/final_100k/recordings/1_console.log | grep -v "done |" | sed 's/^\^D//' | cut -c1-170
pause "show the resume"
echo "Phase 2 reran the SAME command. It found the saved work and only labeled what was missing:"
grep -E "^\S*\[(prepare|enrich|checkpoint|records)\]" runs/final_100k/recordings/2_console.log | grep -v "done |" | sed 's/^\^D//' | cut -c1-170
pause "show the checkpoint snapshots"
$PY - <<'PY'
import json
b = json.load(open("grading/checkpoint_before.json"))["completed_ids"]
a = json.load(open("grading/checkpoint_after.json"))["completed_ids"]
calls = [json.loads(l) for l in open("runs/final_100k/calls.jsonl")]
resumed = {i for c in calls if c["role"] == "enrich" and c["phase"] == "resume" for i in c["review_ids"]}
print(f"checkpoint_before.json : {len(b):,} completed review IDs (saved before the interruption)")
print(f"checkpoint_after.json  : {len(a):,} completed review IDs (after resuming)")
print(f"before is inside after : {set(b) <= set(a)}")
print(f"new completed IDs      : {len(set(a) - set(b)):,}")
print(f"resume calls that re-sent an already completed ID: {len(resumed & set(b))}")
PY
pause "show the zero-API checker's verdict on the same files"
$PY - <<'PY'
import json
d = json.load(open("grading_check/self-check.json"))
print("checker coverage:", {k: d["coverage"][k] for k in ("expected", "valid_completed", "quarantined", "missing")})
print("resume flags (resume_snapshot_mismatch, reprocessed_checkpoint, resume_call_evidence):",
      {k: d["issue_counts"].get(k, 0) for k in ("resume_snapshot_mismatch", "reprocessed_checkpoint", "resume_call_evidence")})
PY

RUN="demo_resume_$(date +%Y%m%d_%H%M%S)"
title "PART 2 · Live: stop and resume a fresh run ($RUN)"
echo "Step 1: start a new run on data/cost_100.csv and interrupt it after 40 reviews (--stop-after 40)."
pause "run it"
$PY -m pipeline run --input data/cost_100.csv --run-id "$RUN" --stages prepare,enrich,records --stop-after 40 --spend-cap 0.05 | grep -v "done |"
pause "show what was saved"
echo "Saved results: $(wc -l < runs/$RUN/enrich/enriched_texts.jsonl | tr -d ' ') labeled texts in runs/$RUN/enrich/enriched_texts.jsonl"
ls runs/$RUN/enrich/checkpoints/
echo
echo "Step 2: run the SAME command again (no --stop-after). It should resume, not start over."
pause "resume"
$PY -m pipeline run --input data/cost_100.csv --run-id "$RUN" --stages prepare,enrich,records --spend-cap 0.05 | grep -v "done |"
pause "prove nothing was paid for twice"
RUN="$RUN" $PY - <<'PY'
import json, os
rd = "runs/" + os.environ["RUN"]
calls = [json.loads(l) for l in open(rd + "/calls.jsonl")]
init = [c for c in calls if c["phase"] == "initial" and c["outcome"] == "succeeded"]
res = [c for c in calls if c["phase"] == "resume" and c["outcome"] == "succeeded"]
first = {i for c in init for i in c["review_ids"]}
again = {i for c in res for i in c["review_ids"]} & first
status = json.load(open(rd + "/records/status.json"))
print(f"initial phase calls: {len(init)}   resume phase calls: {len(res)}")
print(f"reviews sent again after the interruption: {len(again)}")
print(f"final status: {status}")
print(f"API cost of this demo: ${sum(c.get('cost_usd') or 0 for c in calls):.4f}")
PY
title "Done"
