"""Model clients with bounded retries, a shared spend ledger, a rate limiter and a call log.

Every attempt (success or failure) becomes one line in runs/<run_id>/calls.jsonl.
Keys come from .env through environment variables and are never logged.
Set INSIGHT_FAKE=1 to use deterministic stub clients for offline code tests (marked model FAKE, never evidence).
"""
import csv, json, os, random, re, threading, time, uuid
from pathlib import Path
from .common import ROOT, append_jsonl, now

FAKE = os.environ.get("INSIGHT_FAKE") == "1"


def load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass


def load_rates(path=None):
    rates = {}
    with open(path or ROOT / "cost" / "rates.csv", newline="") as f:
        for r in csv.DictReader(f):
            rates[(r["model"], r["item"])] = float(r["price_per_unit_usd"])
    return rates


def call_cost(rates, model, usage):
    """item_cost = billed units x price per unit; input, cached input, cache write and output are separate."""
    total = 0.0
    for item in ("input", "cached_input", "cache_write", "output"):
        units = usage.get(item) or 0
        if units:
            total += units * rates.get((model, item), 0.0)
    return total


class SpendCapReached(Exception):
    pass


class Ledger:
    """One spend ledger shared by all workers. Reserve worst case before a call, settle after."""

    def __init__(self, cap_usd, spent_usd=0.0):
        self.cap, self.spent, self.reserved = cap_usd, spent_usd, 0.0
        self.lock = threading.Lock()

    def reserve(self, amount):
        with self.lock:
            if self.spent + self.reserved + amount > self.cap:
                raise SpendCapReached(f"spent {self.spent:.4f} + reserved {self.reserved:.4f} + next {amount:.4f} > cap {self.cap:.2f}")
            self.reserved += amount

    def settle(self, reserved, actual):
        with self.lock:
            self.reserved -= reserved
            self.spent += actual


class RateLimiter:
    def __init__(self, per_second):
        self.interval, self.next_t, self.lock = 1.0 / max(per_second, 0.001), 0.0, threading.Lock()

    def wait(self):
        with self.lock:
            t = max(time.monotonic(), self.next_t)
            self.next_t = t + self.interval
        time.sleep(max(0.0, t - time.monotonic()))


class ReplyError(ValueError):
    """The provider answered (and billed) but the reply was unusable. Carries usage so cost is still logged."""
    def __init__(self, msg, usage=None, rid=None):
        super().__init__(msg); self._usage, self._rid = usage or {}, rid


def anthropic_call(rt, *, model, max_tokens, system, user, thinking=None, effort=None):
    """One Messages call. Returns (reply_text, usage, request_id). Thinking blocks are skipped; only text is used.
    Usage is captured before any parsing so a bad reply still has its real cost logged."""
    kw = {}
    if thinking:
        kw["thinking"] = {"type": thinking}
    if effort:
        kw["output_config"] = {"effort": effort}
    m = rt.anthropic().messages.create(model=model, max_tokens=max_tokens, system=system,
                                       messages=[{"role": "user", "content": user}], **kw)
    u = m.usage
    usage = {"input": u.input_tokens, "output": u.output_tokens,
             "cached_input": getattr(u, "cache_read_input_tokens", 0) or 0, "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0}
    text = "".join(getattr(b, "text", "") for b in m.content if getattr(b, "type", "") == "text").strip()
    if m.stop_reason not in ("end_turn", "stop_sequence") or not text:
        raise ReplyError(f"unusable reply: stop_reason={m.stop_reason}, text_chars={len(text)}", usage, m.id)
    return text, usage, m.id


class Transient(Exception):
    """Rate limit, timeout, connection or server error: retry with backoff."""


class Runtime:
    """Shared state for one pipeline run: run id, log path, ledger, limiter, rates."""

    def __init__(self, run_dir, cap_usd, rps=20, phase="initial"):
        load_env()
        self.run_dir = Path(run_dir)
        self.run_id = self.run_dir.name
        self.calls_path = self.run_dir / "calls.jsonl"
        self.rates = load_rates()
        spent = 0.0
        if self.calls_path.exists():
            with open(self.calls_path) as f:
                for line in f:
                    try:
                        spent += json.loads(line).get("cost_usd") or 0.0
                    except json.JSONDecodeError:
                        pass
        self.ledger = Ledger(cap_usd, spent)
        self.limiter = RateLimiter(rps)
        self.phase = phase
        self.log_lock = threading.Lock()
        self._jev = self._anthropic = None

    def log(self, rec):
        with self.log_lock:
            append_jsonl(self.calls_path, rec)

    # ---------- providers ----------
    def jev(self):
        if self._jev is None and not FAKE:
            from typesafe_sdk import TypeSafeClient, RetryPolicy
            self._jev = TypeSafeClient(retry=RetryPolicy(max_retries=0), timeout=60.0)  # we retry ourselves so every attempt is logged
        return self._jev

    def anthropic(self):
        if self._anthropic is None and not FAKE:
            import anthropic
            self._anthropic = anthropic.Anthropic(max_retries=0, timeout=60.0)
        return self._anthropic

    def call(self, *, provider, model, role, review_ids, label_config, prompt_version, fn, worst_case_usd,
             max_attempts=4, extra=None):
        """Run fn() with bounded retries. fn returns (result, usage_dict, request_id). Logs every attempt."""
        last = None
        for attempt in range(1, max_attempts + 1):
            self.ledger.reserve(worst_case_usd)
            self.limiter.wait()
            t0, started = time.monotonic(), now()
            rec = {"request_id": None, "run_id": self.run_id, "role": role, "provider": provider, "model": model,
                   "phase": self.phase, "attempt": attempt, "review_ids": review_ids, "label_config": label_config,
                   "prompt_version": prompt_version, "started_at": started}
            if extra:
                rec.update(extra)
            try:
                result, usage, rid = fn()
                cost = call_cost(self.rates, model, usage)
                self.ledger.settle(worst_case_usd, cost)
                rec.update(request_id=rid, outcome="succeeded", seconds=round(time.monotonic() - t0, 3),
                           input_tokens=usage.get("input"), output_tokens=usage.get("output"),
                           cached_input_tokens=usage.get("cached_input", 0), cache_write_tokens=usage.get("cache_write", 0),
                           cost_usd=round(cost, 8), usage_missing=bool(usage.get("usage_missing")))
                self.log(rec)
                return result, rec
            except Exception as e:  # classify the failure
                transient = _is_transient(e)
                usage = getattr(e, "_usage", None) or {}
                cost = call_cost(self.rates, model, usage)
                self.ledger.settle(worst_case_usd, cost)
                rec.update(request_id=getattr(e, "_rid", None) or f"local-{uuid.uuid4().hex[:12]}", outcome="failed",
                           error=f"{type(e).__name__}: {str(e)[:300]}", transient=transient,
                           seconds=round(time.monotonic() - t0, 3), input_tokens=usage.get("input"),
                           output_tokens=usage.get("output"), cost_usd=round(cost, 8))
                self.log(rec)
                last = e
                if not transient:
                    raise
                time.sleep(min(30, 0.5 * 2 ** (attempt - 1)) * (1 - 0.5 * random.random()))  # backoff with jitter
        raise last


def _is_transient(e):
    name = type(e).__name__
    if isinstance(e, Transient):
        return True
    if any(k in name for k in ("RateLimit", "Timeout", "Connection", "InternalServer", "Overloaded", "ServiceUnavailable")):
        return True
    status = getattr(e, "status", None) or getattr(e, "status_code", None)
    return status in (408, 409, 429, 500, 502, 503, 504, 529)


# ---------- fake providers for offline code tests ----------
def fake_jev_answers(text):
    h = sum(map(ord, text)) % 97
    t = text.lower()
    topic = ("billing" if "premium" in t else "usability" if "ad" in t else "playback" if "crash" in t or "play" in t
             else "access" if "login" in t or "password" in t else "other")
    neg = any(w in t for w in ("bad", "worst", "hate", "trash", "can't", "cant", "not", "useless", "annoying"))
    intent = "complaint" if neg else "praise"
    sev = "3" if neg and topic != "other" else "2" if neg else "1"
    leave = 0.9 if any(w in t for w in ("uninstall", "deleting", "bye", "leaving")) else 0.05
    conf = 0.4 if h % 7 == 0 else 0.85
    return {"topic": {"choice": topic, "confidence": conf}, "intent": {"choice": intent, "confidence": conf},
            "severity": {"choice": sev, "confidence": conf}, "sentiment": {"score": 0.5 if neg else 3.2},
            "leaving": {"noul": leave}}
