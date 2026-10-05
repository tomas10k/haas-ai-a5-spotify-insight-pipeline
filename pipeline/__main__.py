"""Command line entry point.  python3 -m pipeline <command> ...

  doctor                                    check keys and one tiny call per provider
  run --input CSV --run-id ID [options]     run the staged pipeline (paid model calls)
  rank --run-id ID                          rebuild ranking from saved outputs (no model)
  eval-golden --run-id ID                   compare a run against evals/golden_50_labeled.csv (no model)
  export --run-id ID                        write grading/ from a full run (no model)
  site                                      build site/data/site_data.json for the website (no model)
"""
import argparse, importlib.util, os, sys

FAKE_MODE = lambda: os.environ.get("INSIGHT_FAKE") == "1"
from .common import ROOT


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    r = sub.add_parser("run")
    r.add_argument("--input", required=True); r.add_argument("--run-id", required=True)
    r.add_argument("--stages", default=None, help="comma list, default all: prepare,enrich,records,verify,group,rank,memo")
    r.add_argument("--workers", type=int); r.add_argument("--limit", type=int); r.add_argument("--stop-after", type=int)
    r.add_argument("--spend-cap", type=float)
    for name in ("rank", "eval-golden", "export"):
        p = sub.add_parser(name); p.add_argument("--run-id", required=True)
    p = sub.add_parser("site")
    a = ap.parse_args(argv)
    if a.cmd == "doctor":
        from .doctor import main as d; return d()
    if a.cmd == "run" and not FAKE_MODE():
        missing = [m for m in ("typesafe_sdk", "anthropic", "dotenv") if importlib.util.find_spec(m) is None]
        if missing:
            print(f"Missing packages {missing}. You are probably outside the project environment. Run:\n"
                  f"  source .venv/bin/activate\nthen try again (your prompt should start with (.venv)).")
            return 1
    if a.cmd == "run":
        from .run import run
        run(a.input, a.run_id, a.stages.split(",") if a.stages else None, a.workers, a.limit, a.stop_after, a.spend_cap)
    elif a.cmd == "rank":
        from .rank import run_rank; run_rank(ROOT / "runs" / a.run_id)
    elif a.cmd == "eval-golden":
        from .evaluate import evaluate; evaluate(ROOT / "runs" / a.run_id)
    elif a.cmd == "site":
        from .site_export import build; build()
    elif a.cmd == "export":
        from .export import export; export(ROOT / "runs" / a.run_id)


if __name__ == "__main__":
    sys.exit(main())
