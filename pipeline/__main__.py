"""Command line entry point.  python3 -m pipeline <command> ...

  doctor                                    check keys and one tiny call per provider
  run --input CSV --run-id ID [options]     run the staged pipeline (paid model calls)
  rank --run-id ID                          rebuild ranking from saved outputs (no model)
  eval-golden --run-id ID                   compare a run against evals/golden_50_labeled.csv (no model)
  export --run-id ID                        write grading/ from a full run (no model)
  site                                      alias of db
  db                                        load saved outputs into site/api/_db/insight.sqlite.gz for the dashboard backend (no model)
  pack / unpack --run-id ID                 gzip a large run folder for git / restore it (no model)
  scope --n 100000                          build data/scope_100k.csv, the declared final scope (no model)
  systest                                   injected fault, injection and planted error tests (a few cents)
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
    for name in ("rank", "eval-golden", "export", "pack", "unpack"):
        p = sub.add_parser(name); p.add_argument("--run-id", required=True)
    p = sub.add_parser("site")
    p = sub.add_parser("db")
    p = sub.add_parser("systest"); p.add_argument("--dev-run", default="dev_10000"); p.add_argument("--memo-run", default="dev_500")
    p = sub.add_parser("scope")
    p.add_argument("--full", default=str(ROOT / "data" / "spotify_reviews_18months.csv"))
    p.add_argument("--n", type=int, default=100000); p.add_argument("--out", default=str(ROOT / "data" / "scope_100k.csv"))
    a = ap.parse_args(argv)
    if a.cmd == "doctor":
        from .doctor import main as d; return d()
    if a.cmd == "run" and not FAKE_MODE():
        missing = [m for m in ("typesafe_sdk", "anthropic", "openai", "dotenv") if importlib.util.find_spec(m) is None]
        if missing:
            print(f"Missing packages {missing}. You are probably outside the project environment. Run:\n"
                  f"  source .venv/bin/activate\nthen try again (your prompt should start with (.venv)).")
            return 1
    if a.cmd in ("rank", "eval-golden", "export"):
        from .pack import unpack; unpack(ROOT / "runs" / a.run_id)
    if a.cmd == "db":
        from .pack import unpack
        for d in (ROOT / "runs").iterdir():
            if d.is_dir(): unpack(d, log=lambda *x: None)
    if a.cmd == "run":
        from .run import run
        run(a.input, a.run_id, a.stages.split(",") if a.stages else None, a.workers, a.limit, a.stop_after, a.spend_cap)
    elif a.cmd == "rank":
        from .rank import run_rank; run_rank(ROOT / "runs" / a.run_id)
    elif a.cmd == "eval-golden":
        from .evaluate import evaluate; evaluate(ROOT / "runs" / a.run_id)
    elif a.cmd == "systest":
        from .systest import systest; systest(a.dev_run, a.memo_run)
    elif a.cmd == "scope":
        from .scope import build_scope; build_scope(a.full, a.n, a.out)
    elif a.cmd == "db":
        from .db import build_db; build_db()
    elif a.cmd == "site":  # the dashboard reads only the database now; kept as an alias
        from .db import build_db; build_db()
    elif a.cmd == "pack":
        from .pack import pack; pack(ROOT / "runs" / a.run_id)
    elif a.cmd == "unpack":
        from .pack import unpack; unpack(ROOT / "runs" / a.run_id)
    elif a.cmd == "export":
        from .export import export; export(ROOT / "runs" / a.run_id)


if __name__ == "__main__":
    sys.exit(main())
