"""Load saved pipeline outputs into the dashboard database (code only, no model calls, no keys).

    python3 -m pipeline db

Writes site/api/_db/insight.sqlite.gz: one SQLite file the deployed backend (site/api/index.py) queries with SQL.
Tables
  meta        key/value: build time, source commit, final run, cost calculator inputs, full file profile
  runs        one row per run shown on the dashboard (summary block as JSON, without per review rows)
  records     one row per source review ID: status, labels, cache provenance, issue, star rating, month (all runs)
  reviews     one row per distinct labeled text: text, labels, evidence quote, verifier / golden labels (explorer)
  ranking     baseline ranking per run, with issue names and cancellation counts
  claims      claims.csv (issue numbers) and topic_claims.csv (topic and coverage facts) per run
  memo        the AI written memo per run, its model and the code check result
The site never reads run folders directly: every number it shows comes from these tables through /api.
"""
import csv, gzip, json, shutil, sqlite3, subprocess
from pathlib import Path
from .common import ROOT, read_jsonl, now
from . import site_export

OUT = ROOT / "site" / "api" / "_db" / "insight.sqlite.gz"

SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE runs(key TEXT PRIMARY KEY, ord INTEGER, run_id TEXT, label TEXT, status TEXT, block TEXT);
CREATE TABLE records(run_key TEXT, review_id TEXT, status TEXT, reason TEXT, text_sha TEXT, cache_source_id TEXT,
  topic TEXT, intent TEXT, severity INTEGER, sentiment REAL, needs_review INTEGER, rating TEXT, month TEXT, likes INTEGER,
  issue_id TEXT, PRIMARY KEY(run_key, review_id));
CREATE TABLE reviews(run_key TEXT, k INTEGER, review_id TEXT, text_sha TEXT, text TEXT, stars TEXT, date TEXT, copies INTEGER,
  topic TEXT, intent TEXT, severity INTEGER, sentiment REAL, quote TEXT, needs_review INTEGER, decided_by TEXT,
  issue_id TEXT, issue_rank INTEGER, in_memo INTEGER, has_verify INTEGER, verify_diff INTEGER, has_human INTEGER, human_diff INTEGER,
  extra TEXT, PRIMARY KEY(run_key, review_id));
CREATE TABLE ranking(run_key TEXT, rank INTEGER, issue_id TEXT, name TEXT, description TEXT, topic TEXT, complaint_count INTEGER,
  severity_sum INTEGER, mean_severity TEXT, priority_score INTEGER, cancellations INTEGER, PRIMARY KEY(run_key, issue_id));
CREATE TABLE claims(run_key TEXT, claim_id TEXT, kind TEXT, subject TEXT, metric TEXT, value TEXT, PRIMARY KEY(run_key, claim_id));
CREATE TABLE memo(run_key TEXT PRIMARY KEY, text TEXT, model TEXT, check_json TEXT);
CREATE INDEX reviews_k ON reviews(run_key, k);
CREATE INDEX reviews_issue ON reviews(run_key, issue_id, severity);
CREATE INDEX records_month ON records(run_key, month);
CREATE INDEX records_text ON records(run_key, text_sha);
"""


def _csv(p):
    p = Path(p)
    return list(csv.DictReader(open(p, encoding="utf-8", newline=""))) if p.exists() else []


def _diff(a, b):
    return int(bool(a and b and any(str(a[f]) != str(b[f]) for f in ("topic", "intent", "severity"))))


def build_db(log=print, out=OUT):
    site_export.MAX_REVIEWS = None  # the database keeps every distinct text; the API pages through them
    specs = json.loads((ROOT / "config" / "site_runs.json").read_text())
    pilot = site_export._j(ROOT / "cost" / "pilot_runs.json")
    golden = {}
    for g in _csv(ROOT / "evals" / "golden_50_labeled.csv"):
        golden[g["review_id"]] = {"topic": g["topic"], "intent": g["intent"], "severity": int(g["severity"]),
                                  "sentiment": float(g["sentiment"]), "quote": g["evidence_quote"]}
    tmp = out.with_suffix("")  # .sqlite
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript(SCHEMA)
    final_key = None
    for ord_, s in enumerate(specs):
        if s["run_id"] == "@pilot":
            s = {**s, "run_id": pilot["run_id"] if pilot else "none"}
        b = site_export.run_block(s, golden)
        items = b.pop("reviews", [])
        b["reviews_total"] = len(items)
        db.execute("INSERT INTO runs VALUES (?,?,?,?,?,?)", (s["key"], ord_, s["run_id"], s["label"], b["status"], json.dumps(b, ensure_ascii=False)))
        if b["status"] != "done":
            continue
        if s.get("final"):
            final_key = s["key"]
        rd = ROOT / "runs" / s["run_id"]
        texts_sha = {}
        for k, i in enumerate(items):
            texts_sha[i["id"]] = None
            extra = {f: i.get(f) for f in ("entities", "reasons", "jev", "verify", "human", "issue_name")}
            db.execute("INSERT INTO reviews VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                s["key"], k, i["id"], None, i["text"], i["stars"], i["date"], i["copies"], i["topic"], i["intent"], i["severity"],
                i["sentiment"], None if i["quote"] == i["text"] else i["quote"], int(bool(i["needs_review"])), i.get("decided_by"),
                i.get("issue"), i.get("issue_rank"), int(bool(i.get("in_memo"))), int(i.get("verify") is not None), _diff(i.get("verify"), i),
                int(i.get("human") is not None), _diff(i.get("human"), i), json.dumps(extra, ensure_ascii=False)))
        # full text of each distinct review (the explorer truncates long texts to 700 characters)
        full = {t["first_review_id"]: (t["text_sha"], t["review_text"]) for t in read_jsonl(rd / "prepare" / "texts.jsonl")}
        db.executemany("UPDATE reviews SET text_sha = ?, text = ? WHERE run_key = ? AND review_id = ?",
                       ((full[rid][0], full[rid][1], s["key"], rid) for rid in texts_sha if rid in full))
        issue_of = {r["review_id"]: r["issue_id"] for r in _csv(rd / "group" / "membership.csv")}
        src = {x["review_id"]: x for x in read_jsonl(rd / "prepare" / "source_index.jsonl")}
        rows = []
        for r in read_jsonl(rd / "records" / "enriched.jsonl"):
            x = src[r["review_id"]]
            rows.append((s["key"], r["review_id"], "completed", None, x["text_sha"], r.get("cache_source_id"), r["topic"], r["intent"],
                         r["severity"], r["sentiment"], int(bool(r["needs_review"])), x["review_rating"], x["review_timestamp"][:7],
                         int(x["review_likes"] or 0), issue_of.get(r["review_id"])))
        for q in read_jsonl(rd / "records" / "quarantine.jsonl"):
            x = src.get(q["review_id"], {})
            rows.append((s["key"], q["review_id"], "quarantined", q.get("reason"), x.get("text_sha"), None, None, None, None, None, None,
                         x.get("review_rating"), (x.get("review_timestamp") or "")[:7], int(x.get("review_likes") or 0), None))
        done = {r[1] for r in rows}
        for rid, x in src.items():  # anything not completed or quarantined is still pending: shown, never hidden
            if rid not in done:
                rows.append((s["key"], rid, "pending", None, x["text_sha"], None, None, None, None, None, None, x["review_rating"],
                             x["review_timestamp"][:7], int(x["review_likes"] or 0), None))
        db.executemany("INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        agg = {r["issue_id"]: r for r in _csv(rd / "rank" / "aggregates.csv")}
        issues = b.get("issues", {})
        for r in b.get("ranking", []):
            iss = r["issue_id"]
            db.execute("INSERT INTO ranking VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                s["key"], int(r["rank"]), iss, issues.get(iss, {}).get("name"), issues.get(iss, {}).get("description"),
                issues.get(iss, {}).get("topic"), int(r["complaint_count"]), int(r["severity_sum"]), r["mean_severity"],
                int(r["priority_score"]), int(agg.get(iss, {}).get("cancellations") or 0)))
        for c in _csv(rd / "memo" / "claims.csv"):
            db.execute("INSERT INTO claims VALUES (?,?,?,?,?,?)", (s["key"], c["claim_id"], "issue", c["issue_id"], c["metric"], c["value"]))
        for c in _csv(rd / "memo" / "topic_claims.csv"):
            kind = "topic" if c.get("topic") else "fact"
            db.execute("INSERT INTO claims VALUES (?,?,?,?,?,?)", (s["key"], c["claim_id"], kind, c.get("topic") or c.get("name"),
                                                                    c.get("metric") or c.get("name"), c["value"]))
        if b.get("memo"):
            db.execute("INSERT INTO memo VALUES (?,?,?,?)", (s["key"], b["memo"], b.get("memo_model"), json.dumps(b.get("memo_check"))))
        log(f"[db] {s['key']}: {len(rows):,} records, {len(items):,} distinct reviews, {len(b.get('ranking', [])):,} ranked issues")
    try:
        commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT).decode().strip()
    except Exception:
        commit = None
    meta = {"built_at": now(), "code_commit": commit, "final_run": final_key, "repo": site_export.REPO,
            "full_file": json.dumps(site_export._j(ROOT / "docs" / "full_file_profile.json")),
            "cost": json.dumps(site_export.cost_block()),
            "system_tests": json.dumps(site_export._j(ROOT / "evals" / "system_tests" / "results.json"))}
    db.executemany("INSERT INTO meta VALUES (?,?)", ((k, v if isinstance(v, str) or v is None else json.dumps(v)) for k, v in meta.items()))
    db.commit(); db.execute("VACUUM"); db.close()
    with open(tmp, "rb") as f, gzip.open(out, "wb", compresslevel=9) as g:
        shutil.copyfileobj(f, g)
    log(f"[db] wrote {out.relative_to(ROOT)} ({out.stat().st_size / 1e6:.1f} MB compressed, {tmp.stat().st_size / 1e6:.1f} MB raw)")
    tmp.unlink()
    return out
