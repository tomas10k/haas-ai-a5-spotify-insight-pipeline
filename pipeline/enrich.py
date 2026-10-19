"""Stage 2 Classify (role: enrich). Jev answers the fixed questions; code validates, maps and saves.

In : runs/<run>/prepare/texts.jsonl (one line per distinct nonempty text)
Out: runs/<run>/enrich/enriched_texts.jsonl  one validated result per distinct text (appended, fsynced)
     runs/<run>/enrich/failures.jsonl        texts that failed validation after one retry (quarantine)
     runs/<run>/calls.jsonl                  every model attempt
Flow per text:  Jev (5 questions, 1 review per request) -> validate (retry invalid once) -> code rules
                -> Haiku only if (a) long review needs an exact quote or (b) capped hard case fallback -> save.
Stop rules: spend cap reached, --limit reached, Ctrl+C or --stop-after (interruption demo). Progress is kept.
"""
import json, re, threading, time, uuid
from concurrent.futures import ThreadPoolExecutor, FIRST_COMPLETED, wait
from pathlib import Path
from .common import ROOT, TOPICS, INTENTS, append_jsonl, read_jsonl, write_json, now
from .clients import Runtime, SpendCapReached, FAKE, fake_jev_answers, _is_transient, anthropic_call, ReplyError

SENT_LEVELS = 5


def label_config(cfg, prompt):
    e = cfg["enrich"]
    return (f"{e['jev_model']}+{e['haiku_model']}:{prompt['prompt_version']}+{e['haiku_prompt_version']}"
            f"+{prompt['schema_version']}+fb{e['fallback_fraction']}")


class Invalid(Exception):
    pass


def _load_done(path):
    done = {}
    if Path(path).exists():
        for line in open(path, encoding="utf-8"):
            try:
                r = json.loads(line)
                done[r["text_sha"]] = r
            except (json.JSONDecodeError, KeyError):
                pass  # a half written last line from a crash is ignored and redone
    return done


def _entities(text, terms):
    low = text.lower()
    return [t for t in terms if re.search(r"(?<![a-z])" + re.escape(t) + r"(?![a-z])", low)]


def split_sentences(text, max_options=60):
    """Exact substrings of the review, split after . ! ? or at line breaks. Code only."""
    parts = [m.group(0).strip() for m in re.finditer(r"[^.!?\n]+[.!?]*", text)]
    parts = [p for p in parts if len(p) >= 3 and p in text]
    if len(parts) > max_options:  # keep the first N; the whole review is the safety net
        parts = parts[:max_options]
    return parts or [text]


def _parse_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise Invalid("no JSON object in model reply")
    return json.loads(m.group(0))


class Enricher:
    def __init__(self, run_dir, cfg, rt):
        self.run_dir, self.cfg, self.rt = Path(run_dir), cfg, rt
        self.e = cfg["enrich"]
        self.prompt = json.loads((ROOT / self.e["prompt_file"]).read_text())
        self.questions = self.prompt["questions"]
        self.haiku_tpl = (ROOT / "prompts" / f"{self.e['haiku_prompt_version']}.md").read_text()
        self.terms = json.loads((ROOT / "config" / "entities.json").read_text())
        self.lc = label_config(cfg, self.prompt)
        self.out = self.run_dir / "enrich"
        self.out.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.fallbacks = 0
        self.processed = 0
        # worst case per call, for spend reservation (input estimate x2 margin, full output cap)
        r = rt.rates
        self.jev_worst = 4000 * r.get((self.e["jev_model"], "input"), 0)
        self.haiku_worst = 3000 * r.get((self.e["haiku_model"], "input"), 0) + \
            self.e["haiku_max_output_tokens"] * r.get((self.e["haiku_model"], "output"), 0)

    # ----- Jev -----
    def _jev(self, text, rid, sentences=None):
        qs = dict(self.questions)
        if sentences:
            qs["quote"] = {"type": "choice", "instructions": self.prompt["questions_for_long_reviews"]["quote"]["instructions"],
                           "criteria": {f"s{i + 1}": snt for i, snt in enumerate(sentences)}}

        def fn():
            if FAKE:
                a = fake_jev_answers(text)
                if sentences:
                    a["quote"] = {"choice": "s1", "confidence": 0.8}
                return a, {"input": 600 + len(text) // 4 * (2 if sentences else 1), "output": 0}, f"fake-{rid[:8]}"
            resp = self.rt.jev().system_one(state=text, questions=qs, model=self.e["jev_model"])
            ans = {}
            for k, a in resp.answers.items():
                d = a.model_dump()
                ans[k] = d
            u = resp.usage
            try:
                rid_ = resp.request_id
            except Exception:
                rid_ = "jev-noid-" + uuid.uuid4().hex[:12]
            usage = {"input": u.input_tokens, "output": u.output_tokens or 0}
            if usage["input"] is None:
                usage["input"], usage["usage_missing"] = 0, True  # reported as missing, never invented
            return ans, usage, rid_
        return self.rt.call(provider="typesafe", model=self.e["jev_model"], role="enrich", review_ids=[rid],
                            label_config=self.lc, prompt_version=self.prompt["prompt_version"], fn=fn,
                            worst_case_usd=self.jev_worst, max_attempts=self.e["max_attempts_transient"],
                            extra={"step": "jev_classify"})

    def _validate_jev(self, a):
        try:
            topic, intent = a["topic"]["choice"], a["intent"]["choice"]
            sev, score, noul = a["severity"]["choice"], float(a["sentiment"]["score"]), float(a["leaving"]["noul"])
        except (KeyError, TypeError, ValueError) as ex:
            raise Invalid(f"missing or malformed answer: {ex}")
        if topic not in TOPICS: raise Invalid(f"topic {topic!r} not allowed")
        if intent not in INTENTS: raise Invalid(f"intent {intent!r} not allowed")
        if sev not in {"1", "2", "3", "4", "5"}: raise Invalid(f"severity {sev!r} not allowed")
        if not 0 <= score <= SENT_LEVELS - 1: raise Invalid(f"sentiment score {score} out of range")
        if not 0 <= noul <= 1: raise Invalid(f"noul {noul} out of range")
        meta = {"topic_conf": float(a["topic"].get("confidence", 1)), "severity_conf": float(a["severity"].get("confidence", 1)),
                "topic_probs": {k: round(v, 4) for k, v in (a["topic"].get("probabilities") or {}).items()}}
        return topic, intent, int(sev), score, noul, meta

    # ----- Haiku (quote and capped fallback) -----
    def _haiku(self, text, rid, task, schema, step):
        prompt = self.haiku_tpl.replace("{task}", task).replace("{schema}", schema)

        def fn():
            if FAKE:
                q = text[:120]
                return {"evidence_quote": q, "topic": "other", "intent": "complaint", "severity": 2, "sentiment": -0.3}, \
                    {"input": 700 + len(text) // 4, "output": 60}, f"fake-h-{rid[:8]}"
            try:
                txt, usage, rid_ = anthropic_call(self.rt, model=self.e["haiku_model"], max_tokens=self.e["haiku_max_output_tokens"],
                                                  system=prompt, user=f"<review>\n{text}\n</review>")
            except ReplyError as ex:
                err = Invalid(str(ex)); err._usage, err._rid = ex._usage, ex._rid
                raise err
            try:
                return _parse_json(txt), usage, rid_
            except (Invalid, json.JSONDecodeError) as ex:
                err = Invalid(f"unparseable reply: {ex}")
                err._usage, err._rid = usage, rid_
                raise err
        return self.rt.call(provider="anthropic", model=self.e["haiku_model"], role="enrich", review_ids=[rid],
                            label_config=self.lc, prompt_version=self.e["haiku_prompt_version"], fn=fn,
                            worst_case_usd=self.haiku_worst, max_attempts=self.e["max_attempts_transient"],
                            extra={"step": step})

    def _with_one_retry(self, f, check):
        """Invalid output gets exactly one retry; then the error propagates (quarantine)."""
        for attempt in (1, 2):
            try:
                res, rec = f()
                return check(res), rec
            except Invalid:
                if attempt == 2:
                    raise

    def process(self, item):
        text, rid, ts = item["review_text"], item["first_review_id"], item["text_sha"]
        reasons, request_ids, steps = [], [], []
        e = self.e
        needs_quote = len(text) > e["quote_whole_text_max_chars"]
        sentences = split_sentences(text) if needs_quote else None

        def check(a):
            out = list(self._validate_jev(a))
            if sentences:
                c = (a.get("quote") or {}).get("choice", "")
                if not re.fullmatch(r"s\d+", c or "") or not 1 <= int(c[1:]) <= len(sentences):
                    raise Invalid(f"quote choice {c!r} not allowed")
                out[5]["quote"] = sentences[int(c[1:]) - 1]
            return tuple(out)
        (topic, intent, sev, score, noul, meta), rec = self._with_one_retry(lambda: self._jev(text, rid, sentences), check)
        request_ids.append(rec["request_id"]); steps.append("jev")
        # code rules: intent precedence via Noul, sentiment mapping, needs_review
        if noul >= e["leaving_threshold"]:
            if intent != "cancellation":
                reasons.append("noul_set_cancellation")
            intent = "cancellation"
        elif intent == "cancellation":
            intent = "complaint"  # Jev chose cancellation but Noul says no explicit departure
            reasons.append("noul_overrode_cancellation")
        sentiment = round(score / 2 - 1, 2)
        lo, hi = e["review_band"]
        if meta["topic_conf"] < e["low_confidence"]: reasons.append("low_topic_confidence")
        if meta["severity_conf"] < e["low_confidence"]: reasons.append("low_severity_confidence")
        if lo < noul < hi: reasons.append("uncertain_leaving")
        decided_by = "jev"
        use_fallback = False
        if reasons and any(r.startswith("low_") for r in reasons):
            with self.lock:
                if self.fallbacks < e["fallback_fraction"] * max(self.processed + 1, 1):
                    self.fallbacks += 1
                    use_fallback = True
        quote = meta.get("quote") or text
        if quote not in text:  # cannot happen by construction; guard anyway
            quote, _ = text, reasons.append("quote_fallback_whole_text")
        if use_fallback:
            task = ("Re-label this review from the text alone and copy the shortest exact phrase from the review "
                    "(character for character) that supports the topic and severity.")
            schema = '{"topic": "...", "intent": "...", "severity": 1, "sentiment": 0.0, "evidence_quote": "..."}'

            def check(res):
                q = res.get("evidence_quote", "")
                if not q or q not in text:
                    raise Invalid("evidence_quote is not an exact substring")
                if use_fallback:
                    if res.get("topic") not in TOPICS or res.get("intent") not in INTENTS: raise Invalid("label not allowed")
                    if res.get("severity") not in (1, 2, 3, 4, 5): raise Invalid("severity not allowed")
                    if not -1 <= float(res.get("sentiment", 9)) <= 1: raise Invalid("sentiment out of range")
                return res
            try:
                res, hrec = self._with_one_retry(lambda: self._haiku(text, rid, task, schema, "haiku_fallback"), check)
                request_ids.append(hrec["request_id"]); steps.append(hrec["step"])
                quote = res["evidence_quote"]
                topic, intent, sev, sentiment = res["topic"], res["intent"], int(res["severity"]), round(float(res["sentiment"]), 2)
                if noul >= e["leaving_threshold"]:
                    intent = "cancellation"
                decided_by = "haiku_fallback"
            except Invalid:
                reasons.append("haiku_fallback_invalid_after_retry_kept_jev")
        return {"text_sha": ts, "origin_review_id": rid, "label_config": self.lc, "status": "completed",
                "topic": topic, "intent": intent, "sentiment": sentiment, "severity": sev,
                "entities": _entities(text, self.terms), "evidence_quote": quote,
                "needs_review": bool(reasons), "review_reasons": reasons, "decided_by": decided_by,
                "jev": {"topic_conf": meta["topic_conf"], "severity_conf": meta["severity_conf"], "leaving": round(noul, 4),
                        "sentiment_score": round(score, 4), "topic_probs": meta["topic_probs"]},
                "request_ids": request_ids, "steps": steps, "phase": self.rt.phase, "completed_at": now()}


def run_enrich(run_dir, cfg, *, workers=1, limit=None, stop_after=None, phase=None, log=print):
    run_dir = Path(run_dir)
    texts_path = run_dir / "prepare" / "texts.jsonl"
    out_path = run_dir / "enrich" / "enriched_texts.jsonl"
    fail_path = run_dir / "enrich" / "failures.jsonl"
    done = _load_done(out_path)
    failed = _load_done(fail_path)
    rt = Runtime(run_dir, cfg["budget"]["spend_cap_usd"], cfg["enrich"]["max_requests_per_second"], "initial")
    en = Enricher(run_dir, cfg, rt)
    # saved results count as done only under the same label_config; changed settings mean new work
    stale = {ts for ts, r in done.items() if r.get("label_config") != en.lc}
    stale |= {ts for ts, r in failed.items() if r.get("label_config") != en.lc}
    if stale:
        log(f"[enrich] {len(stale):,} saved results use a different label_config: they will be redone")
        done = {ts: r for ts, r in done.items() if ts not in stale}
        failed = {ts: r for ts, r in failed.items() if ts not in stale}
    phase = phase or ("resume" if done or failed else "initial")
    rt.phase = phase
    pending = [it for it in read_jsonl(texts_path) if it["text_sha"] not in done and it["text_sha"] not in failed]
    if limit is not None:
        pending = pending[:max(0, limit - len(done))] if limit > len(done) else []
    stop_n = stop_after
    log(f"[enrich] run={rt.run_id} phase={phase} already_done={len(done)} pending_now={len(pending)} "
        f"workers={workers} label_config={en.lc} spent_so_far=${rt.ledger.spent:.4f} cap=${rt.ledger.cap:.2f}")
    t0 = time.monotonic()
    completed_now = failed_now = 0
    stop_reason = "finished"

    def task(item):
        try:
            return "ok", en.process(item)
        except Invalid as ex:
            return "invalid", {"text_sha": item["text_sha"], "origin_review_id": item["first_review_id"],
                               "label_config": en.lc, "status": "quarantined", "reason": f"invalid_output_after_retry: {ex}",
                               "attempts": 2, "at": now()}

    it = iter(pending)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        inflight = set()
        try:
            while True:
                while len(inflight) < workers:
                    if stop_n is not None and completed_now + len(inflight) >= stop_n:
                        break
                    nxt = next(it, None)
                    if nxt is None:
                        break
                    inflight.add(pool.submit(task, nxt))
                if not inflight:
                    break
                done_f, inflight = wait(inflight, return_when=FIRST_COMPLETED)
                for f in done_f:
                    try:
                        kind, row = f.result()
                    except SpendCapReached as ex:
                        stop_reason = f"spend_cap: {ex}"
                        it = iter(())
                        continue
                    except Exception as ex:
                        if _is_transient(ex):  # transient retries exhausted: stays pending for the next run
                            log(f"[enrich] call failed after bounded retries, left pending: {type(ex).__name__}: {ex}")
                            continue
                        stop_reason = f"fatal: {type(ex).__name__}: {ex}"  # setup or auth problem: stop, do not burn retries
                        log(f"[enrich] STOP, not retryable: {type(ex).__name__}: {ex}")
                        it = iter(())
                        continue
                    with en.lock:
                        if kind == "ok":
                            append_jsonl(out_path, row); completed_now += 1
                        else:
                            append_jsonl(fail_path, row); failed_now += 1
                        en.processed += 1
                    n = completed_now + failed_now
                    if n % 100 == 0:
                        log(f"[enrich] {len(done) + completed_now:,} done | {failed_now} quarantined | "
                            f"${rt.ledger.spent:.4f} | {n / max(time.monotonic() - t0, 1e-9):.1f} texts/s")
                if stop_n is not None and completed_now >= stop_n:
                    stop_reason = "stop_after (deliberate interruption)"
                    it = iter(())
        except KeyboardInterrupt:
            stop_reason = "keyboard_interrupt"
            log("[enrich] Ctrl+C: finishing in flight requests and saving progress...")
            it = iter(())
            for f in inflight:
                try:
                    kind, row = f.result()
                    append_jsonl(out_path if kind == "ok" else fail_path, row)
                    completed_now += kind == "ok"
                    failed_now += kind != "ok"
                except Exception as ex:  # an in flight call that failed stays pending for the next run
                    log(f"[enrich] in flight request not saved, left pending: {type(ex).__name__}: {ex}")
    secs = time.monotonic() - t0
    summary = {"stage": "enrich", "run_id": rt.run_id, "phase": phase, "label_config": en.lc,
               "completed_before": len(done), "completed_now": completed_now, "quarantined_now": failed_now,
               "haiku_fallbacks": en.fallbacks, "workers": workers, "seconds": round(secs, 2),
               "spent_usd_total": round(rt.ledger.spent, 6), "stop_reason": stop_reason, "at": now()}
    append_jsonl(run_dir / "run_log.jsonl", summary)
    log(f"[enrich] {stop_reason}: +{completed_now} completed, {failed_now} quarantined, {secs:.1f}s, total spent ${rt.ledger.spent:.4f}")
    return summary
