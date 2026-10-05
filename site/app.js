/* Spotify Insight Pipeline site (v2). Reads data/site_data.json, built by `python3 -m pipeline site`.
   No keys, no API calls: every number is from that file or computed on the page with the formula shown. */
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const n0 = x => x == null || isNaN(x) ? "–" : Number(x).toLocaleString("en-US", { maximumFractionDigits: 0 });
const n2 = x => x == null || isNaN(x) ? "–" : Number(x).toLocaleString("en-US", { maximumFractionDigits: 2 });
const pct = x => x == null ? "–" : (x * 100).toFixed(0) + "%";
const usd = x => x == null || isNaN(x) ? "–" : x < 0.01 ? "$" + x.toFixed(4) : x < 100 ? "$" + x.toFixed(2) : "$" + Math.round(x).toLocaleString("en-US");
const dur = s => s < 90 ? n0(s) + " s" : s < 5400 ? n0(s / 60) + " min" : n2(s / 3600) + " h";
let D, RUN;

$("#themeBtn").onclick = () => { const c = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"); document.documentElement.dataset.theme = c === "dark" ? "light" : "dark"; };
const tip = $("#tip");
document.addEventListener("mousemove", e => { const t = e.target.closest("[data-tip]"); if (!t) { tip.style.display = "none"; return; }
  tip.textContent = t.dataset.tip; tip.style.display = "block"; tip.style.left = Math.min(e.clientX + 12, innerWidth - 320) + "px"; tip.style.top = e.clientY + 14 + "px"; });

/* ---------- 1. how it works ---------- */
const PHASES = [
  ["code", "Prepare", "Read all rows, fingerprint each, find identical texts, set empty ones aside", "Code"],
  ["model", "Classify", "Jev answers 5 fixed questions per review: topic, intent, severity, tone, leaving?", "Jev + code checks"],
  ["model", "Verify", "Haiku relabels a random 1% blind; code compares", "Haiku + code"],
  ["mix", "Group", "Code puts each complaint into one issue; Haiku only names issues", "Code + Haiku"],
  ["code", "Rank", "Score = complaints × average severity, in SQL", "Code"],
  ["mix", "Recommend", "Claude Sonnet writes the memo from the totals; code checks every number", "Sonnet + code"]];
function how() {
  $("#flow").innerHTML = PHASES.map(([c, t, s, w], i) => `<div class="phase ${c}"><span class="n">${i + 1} · ${w}</span><span class="t">${t}</span><span class="s">${s}</span></div>`).join("");
}

/* ---------- 2. runs ---------- */
function runs() {
  $("#runchips").innerHTML = D.runs.map((r, i) => `<button class="runchip ${r.status}" data-i="${i}" aria-selected="false"><b>${esc(r.label)}</b><span>${r.status === "done" ? n0(r.rows_read) + " reviews · " + usd(r.total_cost_usd) : "pending"}</span></button>`).join("");
  $("#runchips").onclick = e => { const b = e.target.closest(".runchip"); if (b) selectRun(+b.dataset.i); };
  const def = D.runs.map((r, i) => [r, i]).filter(([r]) => r.status === "done").pop();
  selectRun(def ? def[1] : 0);
}
function selectRun(i) {
  RUN = D.runs[i];
  document.querySelectorAll(".runchip").forEach((b, k) => b.setAttribute("aria-selected", k === i));
  const r = RUN, p = $("#runpanel");
  if (r.status !== "done") { p.innerHTML = `<p><b>${esc(r.label)}</b>: ${esc(r.role)}</p><p class="muted">Not run yet. Command: <code>python3 -m pipeline run --input &lt;file&gt; --run-id ${esc(r.run_id)}</code></p>`; answer(); explore(); return; }
  const c = r.calls, s = r.stage_seconds || {}, st = r.records_status || {};
  const call = k => c[k] ? `${n0(c[k].attempts)} call${c[k].attempts === 1 ? "" : "s"} · ${usd(c[k].cost_usd)}` : "no calls";
  const v = r.verify, g = r.golden?.summary;
  const mini = [
    ["Prepare", n0(r.rows_read) + " rows", `${n0(r.distinct)} distinct texts · ${n0(r.reuse)} reused · ${n0(r.empty)} empty`],
    ["Classify", n0(st.completed) + " labeled", `${call("jev_classify")}${c.haiku_fallback ? " · " + n0(c.haiku_fallback.attempts) + " Haiku fallback" : ""} · ${n0(r.flagged)} flagged`],
    ["Verify", v ? pct(v.topic_agreement) + " agree" : "not run", v ? `${n0(v.n)} sampled · ${n0(v.disagreements)} disagreements` : "run all stages to add it"],
    ["Group", r.ranking.length ? n0(Object.keys(r.issues).length) + " issues" : "not run", r.ranking.length ? n0(r.ranking.reduce((a, x) => a + +x.complaint_count, 0)) + " complaints placed" : ""],
    ["Rank", r.ranking[0] ? "#1 score " + n0(r.ranking[0].priority_score) : "not run", r.ranking[0] ? esc(r.issues[r.ranking[0].issue_id]?.name || r.ranking[0].issue_id) : ""],
    ["Recommend", r.memo_check ? (r.memo_check.passed ? "check passed" : "check failed") : "not run", r.memo_check ? n0(r.memo_check.cited_claims?.length) + " cited numbers" : ""]];
  let evalHtml = "";
  if (g) {
    const conf = r.golden.confusion, head = conf[0].slice(1), mx = Math.max(1, ...conf.slice(1).flatMap(x => x.slice(1).map(Number)));
    evalHtml += `<div class="card"><h3>Golden 50: my labels vs the pipeline</h3>
      <p class="explain">I labeled these 50 reviews by hand first. The pipeline labeled the same texts without seeing my answers. Agreement is the share of the 50 where we chose the same label; a missing label counts as wrong.</p>
      <div class="tiles">${[["Topic", pct(g.topic_agreement)], ["Intent", pct(g.intent_agreement)], ["Severity exact", pct(g.severity_exact)], ["Severity avg gap", n2(g.severity_mae) + " levels"], ["Tone within ±0.25", pct(g["sentiment_within_0.25"])], ["Quotes exact", pct(g.quote_exact_substring_rate)]].map(([l, x]) => `<div class="tile"><b>${x}</b><span>${l}</span></div>`).join("")}</div>
      <p class="explain">Reading it: topic and intent are strong; severity is usually off by one level; tone is the weakest field because I scored praise mildly while Jev scores it strongly. 50 reviews is a small diagnostic sample, and 8 of them I marked as ambiguous.</p>
      <details><summary>Topic confusion table</summary><div class="tablewrap"><table class="heat"><tr><th>me \\ pipeline</th>${head.map(h => `<th class="num">${h}</th>`).join("")}</tr>
      ${conf.slice(1).map(x => `<tr><th>${x[0]}</th>${x.slice(1).map((y, k) => `<td class="num" style="background:color-mix(in srgb,var(--code) ${Math.round(60 * y / mx)}%,var(--surface))" data-tip="me ${x[0]}, pipeline ${head[k]}: ${y}">${y === "0" ? "" : y}</td>`).join("")}</tr>`).join("")}</table></div></details>
      <button class="btn" data-go="human">See each disagreement in the explorer ↓</button></div>`;
  }
  if (v) evalHtml += `<div class="card"><h3>Independent verifier: Jev vs Haiku</h3>
      <p class="explain">Haiku relabeled ${n0(v.n)} randomly chosen reviews from this run without seeing Jev's answer. High agreement between two different models suggests the labels are not one model's quirk; disagreements show where the definitions are hard.</p>
      <div class="tiles">${[["Topic", pct(v.topic_agreement)], ["Intent", pct(v.intent_agreement)], ["Severity exact", pct(v.severity_exact)], ["Severity avg gap", n2(v.severity_mae) + " levels"], ["Disagreements", n0(v.disagreements)]].map(([l, x]) => `<div class="tile"><b>${x}</b><span>${l}</span></div>`).join("")}</div>
      <button class="btn" data-go="verify">See the disagreements in the explorer ↓</button></div>`;
  if (!evalHtml) evalHtml = `<p class="muted">No checks saved for this run yet.</p>`;
  p.innerHTML = `<p><b>${esc(r.label)}</b> · ${esc(r.role)}</p>
    <div class="tiles">${[["Reviews in", n0(r.rows_read)], ["Labeled", n0(st.completed)], ["Set aside", n0(st.quarantined || 0)], ["API cost", usd(r.total_cost_usd)], ["Wall clock", dur(r.wall_clock_seconds || 0)]].map(([l, x]) => `<div class="tile"><b>${x}</b><span>${l}</span></div>`).join("")}</div>
    <div class="mini">${mini.map(([l, b, sub], k) => `<div data-tip="${esc(PHASES[k][2])}"><span class="lab">${k + 1} · ${l}</span><b>${b}</b><span class="sub">${sub}</span><span class="sub">${s[["prepare", "enrich", "verify", "group", "rank", "memo"][k]] != null ? n2(s[["prepare", "enrich", "verify", "group", "rank", "memo"][k]]) + " s" : ""}</span></div>`).join("")}</div>
    ${evalHtml}`;
  p.querySelectorAll("[data-go]").forEach(b => b.onclick = () => { FILTER.diff = b.dataset.go; explore(); $("#explore").scrollIntoView({ behavior: "smooth" }); });
  answer(); explore();
}

/* ---------- 3. calculator ---------- */
let PR = {}, CH = {}, CTL = {};
const rate = (m, item) => PR[m + "|" + item] ?? 0;
const OPTIONS = {
  classify: [["jev", "Jev 1.13.0 (measured)"], ["haiku", "Claude Haiku 4.5 only (estimate)"]],
  fallback: [["haiku", "Claude Haiku 4.5, capped (measured)"], ["sonnet", "Claude Sonnet 5, capped (estimate)"], ["off", "Off"]],
  verify: [["haiku", "Claude Haiku 4.5 (measured)"], ["sonnet", "Claude Sonnet 5 (estimate)"]],
  group: [["haiku", "Claude Haiku 4.5 (measured)"], ["sonnet", "Claude Sonnet 5 (estimate)"]],
  memo: [["sonnet", "Claude Sonnet 5"], ["haiku", "Claude Haiku 4.5"]]};
const MODEL = { haiku: "claude-haiku-4-5-20251001", sonnet: "claude-sonnet-5" };
function calc() {
  const C = D.cost;
  if (!C.available) { $("#calc").innerHTML = `<p class="muted">The paid pilot has not been run yet: <code>python3 cost/calculator.py pilot</code></p>`; return; }
  C.rates.forEach(r => PR[r.model + "|" + r.item] = +r.price_per_unit_usd);
  CH = { classify: "jev", fallback: "haiku", verify: "haiku", group: "haiku", memo: "sonnet" };
  const A = C.assumptions;
  CTL = { n: 660622, reuse: true, workers: A.scenarios.base.workers, cap: A.controls.spend_cap_usd, fbcap: A.controls.fallback_fraction_cap, rps: A.controls.max_requests_per_second };
  const E = C.estimates;
  $("#calc").innerHTML = `<div class="calc">
    <div class="stagepick"><h3>1 · Choose a model per step</h3>
      ${Object.entries(OPTIONS).map(([k, opts]) => `<label>${{ classify: "Classify", fallback: "Hard cases", verify: "Verify", group: "Name issues", memo: "Memo" }[k]}<select data-ch="${k}">${opts.map(([v, l]) => `<option value="${v}">${l}</option>`).join("")}</select></label>`).join("")}
      <h3 style="margin-top:8px">2 · Choose a volume</h3>
      <div class="volume"><input type="range" id="vol" min="2" max="5.82" step="0.01" value="5.82">
        <div class="presets">${[[50, "Golden 50"], [100, "Pilot 100"], [500, "Dev 500"], [10000, "10,000"], [660622, "Full 660,622"]].map(([v, l]) => `<button class="btn" data-n="${v}">${l}</button>`).join("")}</div>
        <label class="inline"><input type="checkbox" id="reuse" checked> Label identical texts once and reuse the answer (the full file has ${n0(A.full_run.distinct_texts)} distinct texts in ${n0(A.full_run.nonempty)} reviews)</label>
        <div class="form"><label>Workers<input type="number" id="workers" min="1" max="8" value="${CTL.workers}"></label><label>Spend cap (USD)<input type="number" id="cap" value="${CTL.cap}"></label></div></div>
    </div>
    <div style="display:grid;gap:12px;align-content:start"><h3>3 · Result</h3><div id="calcOut"></div></div></div>
    <details><summary>Prices, measurements and assumptions</summary><div id="calcDetail"></div></details>`;
  $("#calc").addEventListener("input", e => {
    if (e.target.dataset.ch) CH[e.target.dataset.ch] = e.target.value;
    if (e.target.id === "vol") CTL.n = Math.round(10 ** +e.target.value);
    if (e.target.id === "reuse") CTL.reuse = e.target.checked;
    if (e.target.id === "workers") CTL.workers = Math.max(1, +e.target.value);
    if (e.target.id === "cap") CTL.cap = +e.target.value;
    if (e.target.dataset.rate) PR[e.target.dataset.rate] = (+e.target.value) / 1e6;
    if (e.target.dataset.est) C.estimates[e.target.dataset.est] = +e.target.value;
    recalc();
  });
  $("#calc").addEventListener("change", e => { if (e.target.dataset.ch) { CH[e.target.dataset.ch] = e.target.value; recalc(); } });
  $("#calc").querySelectorAll("[data-n]").forEach(b => b.onclick = () => { CTL.n = +b.dataset.n; $("#vol").value = Math.log10(CTL.n); recalc(); });
  calcDetail(); recalc();
}
function calcDetail() {
  const C = D.cost, M = C.measured, P = C.pilot, E = C.estimates;
  $("#calcDetail").innerHTML = `<p class="explain">Measured on the pilot (<code>${esc(P.run_id)}</code>, ${n0(P.ids)} reviews, input checksum ${P.input_sha256.startsWith("c884ac3b") ? "matches the manifest" : "MISMATCH"}): cold run ${n2(P.cold_seconds)} s; warm rerun ${n2(P.warm_seconds)} s with ${n0(P.warm_enrich_calls)} new labeling calls. Jev reads about ${n0(M.jev.in_short)} tokens per short review and ${n0(M.jev.in_long)} per long one (${pct(D.cost.assumptions.full_run.share_long_texts_over_200_chars)} of texts), at ${n2(M.jev.texts_per_second_1_worker)} reviews per second per worker. Instructor check (prices doubled): ${C.check ? (C.check.doubles && C.check.time_unchanged ? "API cost doubles, time unchanged ✓" : "failed") : "not run"}.</p>
    <div class="tablewrap"><table><tr><th>Model</th><th>Item</th><th>USD per 1M tokens</th><th>Source</th></tr>
    ${C.rates.map(r => `<tr><td><code class="small">${esc(r.model)}</code></td><td>${esc(r.item)}</td><td><input type="number" step="0.001" data-rate="${esc(r.model + "|" + r.item)}" value="${+(r.price_per_unit_usd * 1e6).toFixed(4)}"></td><td class="small"><a href="${esc(r.source_url)}" target="_blank" rel="noopener">source</a> · ${esc(r.checked_date)}</td></tr>`).join("")}</table></div>
    <div class="form"><label>Haiku only: input tokens per review <span class="est">estimate</span><input type="number" data-est="haiku_only_in_per_review" value="${E.haiku_only_in_per_review}"></label>
      <label>Haiku only: output tokens per review <span class="est">estimate</span><input type="number" data-est="haiku_only_out_per_review" value="${E.haiku_only_out_per_review}"></label>
      <label>Haiku only: reviews per second per worker <span class="est">estimate</span><input type="number" data-est="haiku_only_reviews_per_second_1_worker" value="${E.haiku_only_reviews_per_second_1_worker}"></label></div>
    <p class="small muted">${esc(E.note)} Item cost = billed tokens × price per token. Local laptop compute is not metered (unknown), and is not counted as zero.</p>`;
}
function recalc() {
  const C = D.cost, M = C.measured, A = C.assumptions, E = C.estimates;
  const ratio = A.full_run.distinct_texts / A.full_run.nonempty, share = A.full_run.share_long_texts_over_200_chars;
  const n = CTL.n, texts = !CTL.reuse ? Math.min(n, A.full_run.nonempty) : n >= A.full_run.rows ? A.full_run.distinct_texts : Math.round(n * ratio);
  // variable: per distinct text
  let clsPer, clsLabel, thr;
  if (CH.classify === "jev") { const tok = (1 - share) * M.jev.in_short + share * (M.jev.in_long || M.jev.in_short); clsPer = tok * M.jev.attempts_per_text * rate(M.jev.model, "input"); clsLabel = `Jev: ${n0(tok)} input tokens × ${(rate(M.jev.model, "input") * 1e6).toFixed(3)} $/M (output free)`; thr = Math.min(M.jev.texts_per_second_1_worker * CTL.workers, CTL.rps); }
  else { clsPer = E.haiku_only_in_per_review * rate(MODEL.haiku, "input") + E.haiku_only_out_per_review * rate(MODEL.haiku, "output"); clsLabel = `Haiku: ${E.haiku_only_in_per_review} in + ${E.haiku_only_out_per_review} out tokens per review (estimate)`; thr = E.haiku_only_reviews_per_second_1_worker * CTL.workers; }
  const fbModel = MODEL[CH.fallback];
  const fbPer = CH.fallback === "off" ? 0 : Math.min(M.fallback.rate, CTL.fbcap) * (M.fallback.in_per_call * rate(fbModel, "input") + M.fallback.out_per_call * rate(fbModel, "output"));
  // fixed: once per run
  const vN = Math.min(2000, Math.max(20, Math.round(0.01 * texts)), texts);
  const verify = vN * (M.verify.in_per_review * rate(MODEL[CH.verify], "input") + M.verify.out_per_review * rate(MODEL[CH.verify], "output"));
  const gScale = texts > 1000 ? A.group_scale_factor : 1;
  const group = gScale * (M.group.in * rate(MODEL[CH.group], "input") + M.group.out * rate(MODEL[CH.group], "output"));
  const memo = M.memo.in * rate(MODEL[CH.memo], "input") + M.memo.out * rate(MODEL[CH.memo], "output");
  const variable = texts * (clsPer + fbPer), fixed = verify + group + memo, total = variable + fixed;
  const hours = texts / thr + (n > 100000 ? A.full_run.prepare_seconds_measured_full_file : 0);
  const mx = Math.max(total, CTL.cap) * 1.05;
  const mm = M.models || {}, measuredModel = { fallback: mm.haiku_fallback, verify: mm.verify, group: mm.group, memo: mm.memo };
  const tag = k => (k === "classify" ? CH.classify === "jev" : CH[k] === "off" || MODEL[CH[k]] === measuredModel[k]) ? '<span class="meas">measured</span>' : '<span class="est">estimate from measured tokens</span>';
  $("#calcOut").innerHTML = `
    <div><span class="big">${usd(total)}</span> <span class="muted">for ${n0(n)} reviews (${n0(texts)} labeled${CTL.reuse ? ", the rest reused" : ""}) · about ${dur(hours)} with ${CTL.workers} worker${CTL.workers > 1 ? "s" : ""}</span></div>
    <div class="stack" data-tip="variable ${usd(variable)} + fixed ${usd(fixed)}; red line = spend cap ${usd(CTL.cap)}"><div class="v" style="width:${100 * variable / mx}%"></div><div class="f" style="width:${100 * fixed / mx}%"></div><div class="capline" style="left:${100 * CTL.cap / mx}%"></div></div>
    <p class="small ${total > CTL.cap ? "bad" : "ok"}">${total > CTL.cap ? "Over the spend cap: the pipeline would stop at the cap and save progress." : "Within the spend cap of " + usd(CTL.cap) + "."}</p>
    <div class="costbox var"><h4>Variable · grows with every review</h4>
      <div class="line"><span>Classify ${tag("classify")}</span><span>${usd(texts * clsPer)}</span></div><div class="small muted">${clsLabel} · ${usd(clsPer * 1000)} per 1,000 reviews</div>
      <div class="line"><span>Hard cases ${tag("fallback")}</span><span>${usd(texts * fbPer)}</span></div><div class="small muted">${CH.fallback === "off" ? "No second look" : `${pct(Math.min(M.fallback.rate, CTL.fbcap))} of reviews (cap ${pct(CTL.fbcap)}) get one extra call`}</div></div>
    <div class="costbox fix"><h4>Fixed · paid once per run</h4>
      <div class="line"><span>Verify ${n0(vN)} sampled reviews ${tag("verify")}</span><span>${usd(verify)}</span></div>
      <div class="line"><span>Name issues ${tag("group")}</span><span>${usd(group)}</span></div>
      <div class="line"><span>Write and check memo ${tag("memo")}</span><span>${usd(memo)}</span></div></div>`;
}

/* ---------- 4. answer ---------- */
function md(s) { const L = s.split("\n"); let h = "", ul = false;
  const inl = t => esc(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\[([CT]\d{3})\]/g, '<code class="small" data-tip="saved number, see claims.csv">$1</code>');
  for (const l of L) { if (/^\s*[-*] /.test(l)) { if (!ul) { h += "<ul>"; ul = true; } h += "<li>" + inl(l.replace(/^\s*[-*] /, "")) + "</li>"; continue; }
    if (ul) { h += "</ul>"; ul = false; }
    if (l.startsWith("## ")) h += "<h2>" + inl(l.slice(3)) + "</h2>"; else if (l.startsWith("# ")) h += "<h1>" + inl(l.slice(2)) + "</h1>"; else if (l.trim()) h += "<p>" + inl(l) + "</p>"; }
  return h + (ul ? "</ul>" : ""); }
function answer() {
  const r = RUN; $("#answerRun").textContent = r.label;
  if (r.status !== "done" || !r.memo) { $("#memo").innerHTML = `<p class="muted">No memo for this run${r.status === "done" ? " (run all six stages to create one)" : ""}.</p>`; }
  else { const mc = r.memo_check;
    $("#memo").innerHTML = `<div class="memo"><div class="tags"><span class="chip model">Written by ${esc((r.memo_model || "model").replace("claude-", "Claude ").replace(/-/g, " "))} from saved totals</span><span class="chip ${mc?.passed ? "evid" : "warn"}">Number check ${mc?.passed ? "passed" : "failed"}</span></div>
      ${mc && !mc.passed ? `<p class="small bad">Code found: ${esc(mc.errors.join("; "))}</p>` : ""}${md(r.memo)}
      <p class="small muted">Codes like C005 are saved numbers in <code>claims.csv</code> (one issue) and T003 in <code>topic_claims.csv</code> (one area). Code, not the model, wrote each number.</p></div>`; }
  if (r.status !== "done" || !r.ranking.length) { $("#rank").innerHTML = `<p class="muted">No ranking for this run.</p>`; return; }
  const mx = Math.max(...r.ranking.map(x => +x.priority_score));
  $("#rank").innerHTML = `<p class="explain">Score = complaints × average severity (1 to 5) = sum of severities. Only complaints and cancellations count. Ties break by issue ID.</p>
    <div class="tablewrap"><table><tr><th class="num">#</th><th>Issue</th><th>Area</th><th class="num">Complaints</th><th class="num">Avg severity</th><th>Score</th></tr>
    ${r.ranking.map(x => { const is = r.issues[x.issue_id] || {}; return `<tr><td class="num">${x.rank}</td><td><b>${esc(is.name)}</b><br><code class="small" data-tip="${esc(is.description)}">${esc(x.issue_id)}</code></td><td>${esc(is.topic)}</td><td class="num">${n0(x.complaint_count)}</td><td class="num">${(+x.mean_severity).toFixed(2)}</td>
      <td class="barcell"><div class="hbarrow"><span class="track"><div class="hbar" style="width:${(100 * x.priority_score / mx).toFixed(1)}%"></div></span><span class="val">${n0(x.priority_score)}</span></div></td></tr>`; }).join("")}</table></div>`;
}

/* ---------- 5. explorer ---------- */
const FILTER = { diff: "any", topic: "", intent: "", severity: "" };
const diffV = i => i.verify && ["topic", "intent", "severity"].some(f => String(i.verify[f]) !== String(i[f]));
const diffH = i => i.human && ["topic", "intent", "severity"].some(f => String(i.human[f]) !== String(i[f]));
function explore() {
  const r = RUN; $("#exploreRun").textContent = r.label;
  if (r.status !== "done") { $("#filters").innerHTML = ""; $("#rlist").innerHTML = `<p class="muted">Pending run.</p>`; $("#rpath").innerHTML = ""; return; }
  const R = r.reviews, sel = (k, vals) => `<label>${k}<select data-f="${k}"><option value="">all</option>${vals.map(v => `<option ${String(FILTER[k]) === String(v) ? "selected" : ""}>${v}</option>`).join("")}</select></label>`;
  const hasH = R.some(i => i.human), hasV = R.some(i => i.verify);
  $("#filters").innerHTML = `<label>Show<select data-f="diff">
      <option value="any" ${FILTER.diff === "any" ? "selected" : ""}>all reviews</option>
      ${hasV ? `<option value="verify" ${FILTER.diff === "verify" ? "selected" : ""}>Jev vs Haiku disagreed</option><option value="verified" ${FILTER.diff === "verified" ? "selected" : ""}>checked by Haiku</option>` : ""}
      ${hasH ? `<option value="human" ${FILTER.diff === "human" ? "selected" : ""}>me vs Jev disagreed</option>` : ""}</select></label>
    ${sel("topic", ["access", "usability", "playback", "downloads", "catalog", "billing", "support", "other"])}${sel("intent", ["cancellation", "complaint", "request", "praise", "unclear"])}${sel("severity", [1, 2, 3, 4, 5])}`;
  $("#filters").onchange = e => { FILTER[e.target.dataset.f] = e.target.value; explore(); };
  if ((FILTER.diff === "human" && !hasH) || ((FILTER.diff === "verify" || FILTER.diff === "verified") && !hasV)) FILTER.diff = "any";
  const list = R.filter(i => (FILTER.diff === "any" || (FILTER.diff === "verify" && diffV(i)) || (FILTER.diff === "verified" && i.verify) || (FILTER.diff === "human" && diffH(i)))
    && (!FILTER.topic || i.topic === FILTER.topic) && (!FILTER.intent || i.intent === FILTER.intent) && (!FILTER.severity || String(i.severity) === FILTER.severity));
  $("#rlist").innerHTML = `<p class="small muted">${n0(list.length)} of ${n0(r.reviews_total)} distinct reviews${r.reviews_total > R.length ? ` (site shows ${n0(R.length)}, disagreements first)` : ""}</p>` +
    list.slice(0, 300).map((i, k) => `<button class="ritem" data-k="${R.indexOf(i)}" aria-selected="${k === 0}"><span class="txt">${esc(i.text)}</span>
      <span class="tags"><span class="tag">${i.topic}</span><span class="tag">${i.intent}</span><span class="tag">sev ${i.severity}</span>${diffV(i) ? '<span class="tag warn">Jev ≠ Haiku</span>' : ""}${diffH(i) ? '<span class="tag human">me ≠ Jev</span>' : ""}${i.copies > 1 ? `<span class="tag">×${i.copies}</span>` : ""}</span></button>`).join("");
  $("#rlist").onclick = e => { const b = e.target.closest(".ritem"); if (!b) return; document.querySelectorAll(".ritem").forEach(x => x.setAttribute("aria-selected", x === b)); path(R[+b.dataset.k]); };
  list.length ? path(list[0]) : ($("#rpath").innerHTML = `<p class="muted">No reviews match these filters.</p>`);
}
function hl(t, q) { const i = q ? t.indexOf(q) : -1; return i < 0 ? esc(t) : esc(t.slice(0, i)) + "<mark>" + esc(q) + "</mark>" + esc(t.slice(i + q.length)); }
function path(i) {
  const j = i.jev || {}, probs = Object.entries(j.topic_probs || {}).sort((a, b) => b[1] - a[1]).slice(0, 3);
  const cmpRow = (f, a, b) => `<td class="${String(a) === String(b) ? "" : "d"}">${esc(b)}</td>`;
  const cols = [["Pipeline (Jev + code)", i]].concat(i.verify ? [["Haiku verifier (blind)", i.verify]] : []).concat(i.human ? [["Me (golden label)", i.human]] : []);
  const step = (n, c, t, b) => `<div class="step"><div class="badge ${c}">${n}</div><div class="body"><h3>${t}</h3>${b}</div></div>`;
  $("#rpath").innerHTML = `<div class="steps">` +
    step(1, "code", "Prepare", `<div class="quote">${hl(i.text, i.quote)}</div><p class="small muted">${esc(i.stars)} stars (kept as metadata, never shown to a model) · ${esc(i.date)} · ${i.copies > 1 ? `this exact text appears ${n0(i.copies)} times: labeled once, reused for the rest` : "unique text"}</p>`) +
    step(2, "model", "Classify", `<p class="small">Jev's top topics: ${probs.map(([k, v]) => `<b>${k}</b> ${(v * 100).toFixed(0)}%`).join(" · ") || "n/a"}. Leaving probability ${n2(j.leaving)}. ${i.decided_by === "haiku_fallback" ? "<b>Jev was unsure, so Haiku relabeled it</b> (capped fallback)." : ""}</p>
      <p class="small">Code rules: ${i.reasons.length ? i.reasons.map(x => `<code>${esc(x)}</code>`).join(" ") : "no flags"}. Highlighted text = the saved evidence quote.</p>`) +
    step(3, "model", "Verify and compare", `<div class="tablewrap"><table class="cmp"><tr><th></th>${cols.map(c => `<th>${c[0]}</th>`).join("")}</tr>
      ${["topic", "intent", "severity", "sentiment"].map(f => `<tr><td>${f}</td>${cols.map(([, o], k) => k === 0 ? `<td>${esc(f === "sentiment" ? n2(o[f]) : o[f])}</td>` : cmpRow(f, f === "sentiment" ? n2(i[f]) : i[f], f === "sentiment" ? n2(o[f]) : o[f])).join("")}</tr>`).join("")}</table></div>
      ${cols.length === 1 ? `<p class="small muted">Not in the random verifier sample${RUN.key === "golden" ? "" : ", and not a golden review"}.</p>` : `<p class="small muted">Red = different from the pipeline.</p>`}`) +
    step(4, "code", "Group", !RUN.ranking.length ? `<p class="muted">Grouping was not run for this run.</p>` : i.issue ? `<p>Issue <code>${esc(i.issue)}</code>: <b>${esc(i.issue_name)}</b></p>` : `<p class="muted">Intent is ${esc(i.intent)}, not a complaint or cancellation, so it joins no issue.</p>`) +
    step(5, "code", "Rank", i.issue_rank ? `<p>That issue ranks <b>#${i.issue_rank}</b>; this review adds ${i.severity} to its score.</p>` : `<p class="muted">Not ranked.</p>`) +
    step(6, "evid", "Recommend", `<p>${i.in_memo ? "<b>Quoted in the memo.</b>" : i.issue_rank && i.issue_rank <= 10 ? "Its issue is in the memo's evidence." : "Not cited in the memo."}</p>`) + `</div>`;
}

fetch("data/site_data.json").then(r => r.json()).then(d => {
  D = d; how(); calc(); runs();
  $("#foot").innerHTML = `Built from saved run files by <code>python3 -m pipeline site</code> on ${esc(D.generated_at)}. No API keys and no model calls on this page. Data: BwandoWando, 3.4 Million Spotify Google Store Reviews (CC0), May 2022 to Nov 2023. Reviews are self selected; cancellation language is expressed intent, not observed churn. <a href="${esc(D.repo)}">Source code</a>`;
}).catch(e => document.querySelector("main").insertAdjacentHTML("afterbegin", `<div class="banner warn">Could not load data/site_data.json: ${esc(e.message)}</div>`));
