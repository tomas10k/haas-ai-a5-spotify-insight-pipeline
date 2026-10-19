"""Dashboard backend: reads the processed review data from the SQLite database and serves it as JSON.

Deployed as a Vercel Python function (standard library only). The database file is built from saved pipeline
outputs by `python3 -m pipeline db` and shipped gzipped next to this file; on a cold start it is unpacked to /tmp
and opened read only. No API keys, no model calls: every request is a SQL query over saved results.

Routes (GET):
  /api/health                     database build info and table row counts
  /api/site                       run summaries, cost calculator inputs, system test results (no per review rows)
  /api/metrics?run=KEY            overall metrics computed in SQL: statuses, reuse, topics x intents, monthly complaint share
  /api/ranking?run=KEY            baseline ranking with claim IDs
  /api/issue?run=KEY&id=ISS_...   one issue: numbers, claim IDs and member reviews (highest severity first)
  /api/reviews?run=KEY&...        explorer page: filters diff/topic/intent/severity/issue/q, offset, limit
  /api/review?run=KEY&id=ID       trace one source review ID: record -> labels -> verifier -> issue -> rank -> memo
"""
import gzip, json, os, re, shutil, sqlite3, threading
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

HERE = Path(__file__).resolve().parent
PACKED = HERE / "_db" / "insight.sqlite.gz"
LIVE = Path(os.environ.get("INSIGHT_DB", "/tmp/insight.sqlite"))
_lock = threading.RLock()
_conn = None


def db():
    global _conn
    with _lock:
        if _conn is None:
            if not LIVE.exists() or LIVE.stat().st_mtime < PACKED.stat().st_mtime:
                part = LIVE.with_suffix(".part")
                with gzip.open(PACKED, "rb") as f, open(part, "wb") as g:
                    shutil.copyfileobj(f, g)
                part.replace(LIVE)
            _conn = sqlite3.connect(f"file:{LIVE}?mode=ro", uri=True, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
        return _conn


def q(sql, args=()):
    with _lock:
        return [dict(r) for r in db().execute(sql, args).fetchall()]


def meta():
    return {r["key"]: r["value"] for r in q("SELECT key, value FROM meta")}


def run_key(params):
    k = (params.get("run") or [None])[0]
    if not k:
        k = meta().get("final_run") or q("SELECT key FROM runs WHERE status = 'done' ORDER BY ord DESC LIMIT 1")[0]["key"]
    if not q("SELECT 1 FROM runs WHERE key = ?", (k,)):
        raise LookupError(f"unknown run {k!r}")
    return k


def item(r):
    """Database row -> the review object the dashboard renders."""
    x = json.loads(r["extra"] or "{}")
    return {"id": r["review_id"], "text": r["text"], "stars": r["stars"], "date": r["date"], "copies": r["copies"],
            "topic": r["topic"], "intent": r["intent"], "severity": r["severity"], "sentiment": r["sentiment"],
            "quote": r["quote"] if r["quote"] is not None else r["text"], "entities": x.get("entities") or [],
            "needs_review": bool(r["needs_review"]), "reasons": x.get("reasons") or [], "decided_by": r["decided_by"],
            "jev": x.get("jev") or {}, "verify": x.get("verify"), "human": x.get("human"), "issue": r["issue_id"],
            "issue_name": x.get("issue_name"), "issue_rank": r["issue_rank"], "in_memo": bool(r["in_memo"])}


def r_health(p):
    m = meta()
    tables = {t: q(f"SELECT COUNT(*) AS n FROM {t}")[0]["n"] for t in ("runs", "records", "reviews", "ranking", "claims", "memo")}
    return {"ok": True, "database": "SQLite (read only)", "built_at": m.get("built_at"), "code_commit": m.get("code_commit"),
            "final_run": m.get("final_run"), "row_counts": tables}


def r_site(p):
    m = meta()
    runs = []
    for r in q("SELECT key, block FROM runs ORDER BY ord"):
        b = json.loads(r["block"])
        mm = q("SELECT text, model, check_json FROM memo WHERE run_key = ?", (r["key"],))
        if mm:
            b["memo"], b["memo_model"], b["memo_check"] = mm[0]["text"], mm[0]["model"], json.loads(mm[0]["check_json"] or "null")
        runs.append(b)
    return {"generated_at": m.get("built_at"), "repo": m.get("repo"), "final_run": m.get("final_run"),
            "full_file": json.loads(m.get("full_file") or "null"), "cost": json.loads(m.get("cost") or "null"),
            "system_tests": json.loads(m.get("system_tests") or "null"), "runs": runs,
            "served_by": "/api/site from the SQLite database", "db_built_at": m.get("built_at")}


def r_metrics(p):
    k = run_key(p)
    status = {r["status"]: r["n"] for r in q("SELECT status, COUNT(*) AS n FROM records WHERE run_key = ? GROUP BY status", (k,))}
    reuse = q("SELECT COUNT(*) AS n FROM records WHERE run_key = ? AND cache_source_id IS NOT NULL", (k,))[0]["n"]
    reasons = q("SELECT reason, COUNT(*) AS n FROM records WHERE run_key = ? AND status = 'quarantined' GROUP BY reason", (k,))
    by_intent = {r["intent"]: r["n"] for r in q("SELECT intent, COUNT(*) AS n FROM records WHERE run_key = ? AND status = 'completed' GROUP BY intent", (k,))}
    topics = q("""SELECT topic, COUNT(*) AS completed, SUM(intent IN ('complaint','cancellation')) AS complaints,
                  SUM(intent = 'cancellation') AS cancellations, SUM(CASE WHEN intent IN ('complaint','cancellation') THEN severity END) AS severity_sum,
                  ROUND(AVG(sentiment), 3) AS mean_sentiment, SUM(needs_review) AS needs_review
                  FROM records WHERE run_key = ? AND status = 'completed' GROUP BY topic ORDER BY severity_sum DESC""", (k,))
    months = q("""SELECT month, COUNT(*) AS completed, SUM(intent IN ('complaint','cancellation')) AS complaints,
                  SUM(intent = 'cancellation') AS cancellations FROM records WHERE run_key = ? AND status = 'completed'
                  GROUP BY month ORDER BY month""", (k,))
    for mth in months:
        mth["complaint_share"] = round(mth["complaints"] / mth["completed"], 4) if mth["completed"] else None
    ratings = q("""SELECT rating, COUNT(*) AS n, SUM(intent IN ('complaint','cancellation')) AS complaints
                   FROM records WHERE run_key = ? AND status = 'completed' GROUP BY rating ORDER BY rating""", (k,))
    total = sum(status.values())
    return {"run": k, "rows": total, "status": status, "completed_via_exact_text_reuse": reuse, "quarantine_reasons": reasons,
            "by_intent": by_intent, "topics": topics, "months": months, "ratings": ratings,
            "note": "Computed by SQL over the records table on every request. First and last months are partial; "
                    "complaint share = complaint or cancellation records / completed records in that month."}


def r_ranking(p):
    k = run_key(p)
    rows = q("SELECT * FROM ranking WHERE run_key = ? ORDER BY rank", (k,))
    claims = {}
    for c in q("SELECT claim_id, subject, metric FROM claims WHERE run_key = ? AND kind = 'issue'", (k,)):
        claims.setdefault(c["subject"], {})[c["metric"]] = c["claim_id"]
    for r in rows:
        r["claim_ids"] = claims.get(r["issue_id"], {})
    return {"run": k, "ranking": rows, "rule": "priority_score = complaint_count x mean_severity = severity_sum; "
            "descending score, then ascending issue_id"}


def r_issue(p):
    k = run_key(p)
    iid = (p.get("id") or [""])[0]
    rk = q("SELECT * FROM ranking WHERE run_key = ? AND issue_id = ?", (k, iid))
    if not rk:
        raise LookupError(f"unknown issue {iid!r}")
    lim = min(int((p.get("limit") or [25])[0]), 100)
    members = q("""SELECT v.*, COUNT(r.review_id) AS member_rows, MAX(r.likes) AS likes FROM records r
                   JOIN reviews v ON v.run_key = r.run_key AND v.text_sha = r.text_sha
                   WHERE r.run_key = ? AND r.issue_id = ? GROUP BY v.review_id
                   ORDER BY v.severity DESC, likes DESC, v.review_id LIMIT ?""", (k, iid, lim))
    sev = q("SELECT severity, COUNT(*) AS n FROM records WHERE run_key = ? AND issue_id = ? GROUP BY severity ORDER BY severity", (k, iid))
    claims = q("SELECT claim_id, metric, value FROM claims WHERE run_key = ? AND kind = 'issue' AND subject = ?", (k, iid))
    return {"run": k, "issue": rk[0], "claims": claims, "severity_counts": sev,
            "members": [{**item(m), "member_rows": m["member_rows"]} for m in members]}


def r_reviews(p):
    k = run_key(p)
    g = lambda n: (p.get(n) or [""])[0]
    where, args = ["run_key = ?"], [k]
    diff = g("diff")
    if diff == "verify": where.append("verify_diff = 1")
    elif diff == "verified": where.append("has_verify = 1")
    elif diff == "human": where.append("human_diff = 1")
    elif diff == "flagged": where.append("needs_review = 1")
    for f in ("topic", "intent", "issue_id"):
        if g(f if f != "issue_id" else "issue"):
            where.append(f"{f} = ?"); args.append(g(f if f != "issue_id" else "issue"))
    if g("severity"):
        where.append("severity = ?"); args.append(int(g("severity")))
    if g("q"):
        where.append("text LIKE ?"); args.append("%" + g("q")[:100] + "%")
    off = max(0, int(g("offset") or 0)); lim = min(max(1, int(g("limit") or 100)), 300)
    w = " AND ".join(where)
    total = q(f"SELECT COUNT(*) AS n FROM reviews WHERE {w}", args)[0]["n"]
    rows = q(f"SELECT * FROM reviews WHERE {w} ORDER BY k LIMIT ? OFFSET ?", args + [lim, off])
    avail = q("SELECT MAX(has_verify) AS v, MAX(has_human) AS h FROM reviews WHERE run_key = ?", (k,))[0]
    return {"run": k, "total": total, "offset": off, "has_verify": bool(avail["v"]), "has_human": bool(avail["h"]),
            "reviews": [item(r) for r in rows]}


def r_review(p):
    k = run_key(p)
    rid = (p.get("id") or [""])[0].strip()
    rec = q("SELECT * FROM records WHERE run_key = ? AND review_id = ?", (k, rid))
    if not rec:
        raise LookupError(f"review id {rid!r} is not in run {k}")
    rec = rec[0]
    origin = q("SELECT * FROM reviews WHERE run_key = ? AND text_sha = ?", (k, rec["text_sha"])) if rec["text_sha"] else []
    out = {"run": k, "record": rec, "review": item(origin[0]) if origin else None}
    if rec["issue_id"]:
        out["issue"] = q("SELECT * FROM ranking WHERE run_key = ? AND issue_id = ?", (k, rec["issue_id"]))[0]
        out["claims"] = q("SELECT claim_id, metric, value FROM claims WHERE run_key = ? AND kind = 'issue' AND subject = ?", (k, rec["issue_id"]))
    memo = q("SELECT text FROM memo WHERE run_key = ?", (k,))
    out["cited_in_memo"] = bool(memo and rid in memo[0]["text"])
    return out


ROUTES = {"health": r_health, "site": r_site, "metrics": r_metrics, "ranking": r_ranking, "issue": r_issue,
          "reviews": r_reviews, "review": r_review}


def respond(path, query):
    """Shared by the Vercel handler and the local dev server. Returns (status, body_dict)."""
    p = parse_qs(query)
    route = (p.pop("route", [None])[0] or re.sub(r"^/?api/?", "", path).strip("/")).split("/")[0] or "health"
    fn = ROUTES.get(route)
    if not fn:
        return 404, {"error": f"unknown route {route!r}", "routes": sorted(ROUTES)}
    try:
        return 200, fn(p)
    except LookupError as e:
        return 404, {"error": str(e)}
    except (ValueError, KeyError) as e:
        return 400, {"error": f"bad request: {e}"}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        status, body = respond(u.path, u.query)
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "public, max-age=60")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
