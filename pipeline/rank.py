"""Stage 5 Rank (code + SQL, no model). priority(issue) = complaint_count x mean_severity = severity_sum.
Sorted by descending score, then ascending issue_id. Rerun any time from saved files:
    python3 -m pipeline rank --run-id <id>
"""
import csv, json, sqlite3
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from .common import read_jsonl, write_json

SQL = """
SELECT m.issue_id, COUNT(*) AS complaint_count, SUM(l.severity) AS severity_sum,
       SUM(l.intent = 'cancellation') AS cancellations
FROM membership m JOIN labels l USING (review_id)
GROUP BY m.issue_id
ORDER BY severity_sum DESC, m.issue_id ASC
"""


def mean6(total, n):
    return str((Decimal(total) / Decimal(n)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def run_rank(run_dir, log=print):
    run_dir = Path(run_dir); out = run_dir / "rank"; out.mkdir(exist_ok=True)
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE labels(review_id TEXT PRIMARY KEY, topic TEXT, intent TEXT, severity INTEGER)")
    db.execute("CREATE TABLE membership(issue_id TEXT, review_id TEXT, PRIMARY KEY(issue_id, review_id))")
    db.executemany("INSERT INTO labels VALUES (?,?,?,?)",
                   ((r["review_id"], r["topic"], r["intent"], r["severity"]) for r in read_jsonl(run_dir / "records" / "enriched.jsonl")))
    with open(run_dir / "group" / "membership.csv", newline="", encoding="utf-8") as f:
        db.executemany("INSERT INTO membership VALUES (?,?)", ((r["issue_id"], r["review_id"]) for r in csv.DictReader(f)))
    issues = json.loads((run_dir / "group" / "issues.json").read_text())["issues"]
    rows = db.execute(SQL).fetchall()
    with open(out / "ranking.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["rank", "issue_id", "complaint_count", "severity_sum", "mean_severity", "priority_score"])
        for i, (iss, n, s, _) in enumerate(rows, 1):
            w.writerow([i, iss, n, s, mean6(s, n), s])
    total = sum(r[1] for r in rows)
    with open(out / "aggregates.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank", "issue_id", "name", "topic", "complaint_count", "severity_sum", "mean_severity", "priority_score",
                    "cancellations", "share_of_all_complaints"])
        for i, (iss, n, s, c) in enumerate(rows, 1):
            w.writerow([i, iss, issues[iss]["name"], issues[iss]["topic"], n, s, mean6(s, n), s, c,
                        str((Decimal(n) * 100 / Decimal(total)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)) + "%"])
    # topic level view for the client question (access / usability / playback / billing+support)
    topic_rows = db.execute("""SELECT l.topic, COUNT(*), SUM(l.severity), SUM(l.intent='cancellation')
                               FROM membership m JOIN labels l USING (review_id) GROUP BY l.topic ORDER BY SUM(l.severity) DESC""").fetchall()
    all_counts = db.execute("SELECT intent, COUNT(*) FROM labels GROUP BY intent").fetchall()
    write_json(out / "topic_summary.json", {
        "complaint_and_cancellation_records": total,
        "labels_by_intent": dict(all_counts),
        "topics": [{"topic": t, "complaint_count": n, "severity_sum": s, "mean_severity": mean6(s, n), "cancellations": c,
                    "share_of_all_complaints": str((Decimal(n) * 100 / Decimal(total)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)) + "%"}
                   for t, n, s, c in topic_rows]})
    write_trend(run_dir, db)
    log(f"[rank] {len(rows)} issues ranked; top 3: " + ", ".join(f"{r[0]}={r[2]}" for r in rows[:3]))
    return rows


PERIODS = {"2022_jun_oct": ("2022-06", "2022-10"), "2023_jun_oct": ("2023-06", "2023-10")}  # same calendar months, full months only


def pct1(n, d):
    return str((Decimal(n) * 100 / Decimal(d)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)) + "%" if d else None


def write_trend(run_dir, db):
    """Complaint share by area in comparable periods (code only). Denominator = classified records in the period."""
    month = {s["review_id"]: s["review_timestamp"][:7] for s in read_jsonl(run_dir / "prepare" / "source_index.jsonl")}
    db.execute("CREATE TABLE months(review_id TEXT PRIMARY KEY, month TEXT)")
    db.executemany("INSERT INTO months VALUES (?,?)", month.items())
    out = {"rule": "share = complaint or cancellation records with that topic / all classified records in the period; "
                   "same calendar months in both years; first and last calendar months of the window are partial and excluded",
           "periods": {}}
    for name, (a, b) in PERIODS.items():
        tot = db.execute("SELECT COUNT(*) FROM labels l JOIN months m USING (review_id) WHERE m.month BETWEEN ? AND ?", (a, b)).fetchone()[0]
        by = dict(db.execute("""SELECT l.topic, COUNT(*) FROM labels l JOIN months m USING (review_id)
                               WHERE m.month BETWEEN ? AND ? AND l.intent IN ('complaint','cancellation') GROUP BY l.topic""", (a, b)).fetchall())
        out["periods"][name] = {"from": a, "to": b, "classified": tot, "complaints_all_topics": sum(by.values()),
                                "complaint_share_all_topics": pct1(sum(by.values()), tot),
                                "by_topic": {t: {"complaints": by.get(t, 0), "share_of_classified": pct1(by.get(t, 0), tot)}
                                             for t in ("access", "usability", "playback", "downloads", "catalog", "billing", "support", "other")}}
    write_json(run_dir / "rank" / "trend.json", out)
