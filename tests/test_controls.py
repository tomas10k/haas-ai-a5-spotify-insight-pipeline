"""Retry, spend cap, resume and ranking controls (offline).  Run:  python3 -m pytest -q"""
import csv, json, shutil
import pytest
from pipeline import clients
from pipeline.clients import Ledger, Runtime, SpendCapReached, Transient, _is_transient
from pipeline.common import ROOT, load_config, read_jsonl
from pipeline.rank import mean6, run_rank


@pytest.fixture
def rt(tmp_path, monkeypatch):
    monkeypatch.setattr(clients.time, "sleep", lambda s: None)  # keep backoff logic, skip the wait
    return Runtime(tmp_path / "run", cap_usd=1.0)


def ok(result="r"):
    return lambda: (result, {"input": 100, "output": 0}, "req-ok")


def _call(rt, fn, **kw):
    return rt.call(provider="test", model="jev-1.13.0", role="enrich", review_ids=["R1"], label_config="lc",
                   prompt_version="v", fn=fn, worst_case_usd=0.001, **kw)


def log(rt):
    return list(read_jsonl(rt.calls_path))


def test_transient_errors_are_retried_and_every_attempt_logged(rt):
    seq = iter([Transient("529"), Transient("timeout")])
    def fn():
        e = next(seq, None)
        if e: raise e
        return ok()()
    result, rec = _call(rt, fn)
    assert result == "r" and rec["attempt"] == 3
    assert [c["outcome"] for c in log(rt)] == ["failed", "failed", "succeeded"]
    assert all(c["transient"] for c in log(rt)[:2])


def test_retries_are_bounded(rt):
    def fn(): raise Transient("always overloaded")
    with pytest.raises(Transient):
        _call(rt, fn, max_attempts=4)
    assert len(log(rt)) == 4 and all(c["outcome"] == "failed" for c in log(rt))


def test_non_transient_error_is_not_retried(rt):
    class AuthenticationError(Exception): status_code = 401
    def fn(): raise AuthenticationError("bad key")
    with pytest.raises(AuthenticationError):
        _call(rt, fn)
    assert len(log(rt)) == 1 and log(rt)[0]["transient"] is False


@pytest.mark.parametrize("status,expected", [(429, True), (500, True), (529, True), (408, True), (400, False), (401, False), (404, False)])
def test_transient_classification_by_status(status, expected):
    e = Exception("x"); e.status_code = status
    assert _is_transient(e) is expected


def test_ledger_reserves_worst_case_and_stops_at_cap():
    led = Ledger(cap_usd=0.010)
    led.reserve(0.004); led.reserve(0.004)          # 0.008 reserved in flight
    with pytest.raises(SpendCapReached):
        led.reserve(0.004)                          # 0.012 > cap: not admitted
    led.settle(0.004, 0.001); led.settle(0.004, 0.001)
    assert led.spent == pytest.approx(0.002) and led.reserved == pytest.approx(0.0)
    led.reserve(0.004)                              # admitted again after settling


def test_spend_ledger_survives_restart(tmp_path):
    run_dir = tmp_path / "run"
    rt1 = Runtime(run_dir, cap_usd=1.0)
    rt1.call(provider="t", model="m", role="enrich", review_ids=[], label_config="lc", prompt_version="v",
             fn=lambda: ("x", {"input": 1, "output": 0}, "id"), worst_case_usd=0.0)
    with open(rt1.calls_path, "a") as f:            # pretend an earlier run spent $0.30
        f.write(json.dumps({"cost_usd": 0.30, "role": "enrich", "model": "m", "outcome": "succeeded"}) + "\n")
    rt2 = Runtime(run_dir, cap_usd=0.35)
    assert rt2.ledger.spent == pytest.approx(0.30)
    with pytest.raises(SpendCapReached):
        rt2.ledger.reserve(0.10)


def test_interrupt_then_resume_never_relabels_completed_texts(monkeypatch):
    from pipeline.run import run
    rid = "_pytest_resume"
    shutil.rmtree(ROOT / "runs" / rid, ignore_errors=True)
    try:
        m1 = run(str(ROOT / "data" / "cost_100.csv"), rid, stages=["prepare", "enrich", "records"], stop_after=30, log=lambda *a: None)
        assert m1["stopped"].startswith("stop_after")
        rd = ROOT / "runs" / rid
        first = {r["origin_review_id"] for r in read_jsonl(rd / "enrich" / "enriched_texts.jsonl")}
        n_before = sum(1 for _ in open(rd / "calls.jsonl"))
        run(str(ROOT / "data" / "cost_100.csv"), rid, stages=["prepare", "enrich", "records"], log=lambda *a: None)
        calls = list(read_jsonl(rd / "calls.jsonl"))[n_before:]
        resumed = {i for c in calls if c["role"] == "enrich" for i in c["review_ids"]}
        assert calls and all(c["phase"] == "resume" for c in calls)
        assert not resumed & first                                       # nothing paid for twice
        status = json.loads((rd / "records" / "status.json").read_text())
        assert status["completed"] == 100 and "pending" not in status
        run(str(ROOT / "data" / "cost_100.csv"), rid, stages=["prepare", "enrich"], log=lambda *a: None)
        assert sum(1 for _ in open(rd / "calls.jsonl")) == n_before + len(calls)  # warm rerun: zero new calls
    finally:
        shutil.rmtree(ROOT / "runs" / rid, ignore_errors=True)


def test_changed_label_config_is_not_reused(monkeypatch):
    from pipeline.run import run
    from pipeline.enrich import run_enrich
    rid = "_pytest_config"
    shutil.rmtree(ROOT / "runs" / rid, ignore_errors=True)
    try:
        run(str(ROOT / "data" / "cost_100.csv"), rid, stages=["prepare", "enrich"], limit=5, log=lambda *a: None)
        cfg = load_config(); cfg["enrich"]["fallback_fraction"] = 0.02           # different settings
        msgs = []
        s = run_enrich(ROOT / "runs" / rid, cfg, limit=5, log=msgs.append)
        assert s["completed_now"] == 5 and any("different label_config" in m for m in msgs)
    finally:
        shutil.rmtree(ROOT / "runs" / rid, ignore_errors=True)


def test_mean_uses_decimal_half_up():
    assert mean6(1, 8) == "0.125000" and mean6(2, 3) == "0.666667" and mean6(1, 6) == "0.166667"
    assert mean6(5, 2) == "2.500000"


def test_ranking_regenerates_identically_from_saved_files(tmp_path):
    src = ROOT / "runs" / "dev_500"
    for sub in ("records", "group"):
        shutil.copytree(src / sub, tmp_path / sub)
    run_rank(tmp_path, log=lambda *a: None)
    assert (tmp_path / "rank" / "ranking.csv").read_text() == (src / "rank" / "ranking.csv").read_text()
    rows = list(csv.DictReader(open(tmp_path / "rank" / "ranking.csv")))
    keys = [(-int(r["priority_score"]), r["issue_id"]) for r in rows]
    assert keys == sorted(keys) and all(int(r["priority_score"]) == int(r["severity_sum"]) for r in rows)
