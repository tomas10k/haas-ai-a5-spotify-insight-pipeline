/* Spotify Insight Pipeline dashboard (v4). Every number comes from the deployed backend (/api, site/api/index.py),
   which runs SQL over the SQLite database built from saved pipeline outputs by `python3 -m pipeline db`.
   No keys and no model calls in the browser or the backend. */
const API = (route, params = {}) => fetch("/api/" + route + "?" + new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null)))
  .then(r => r.json().then(j => { if (!r.ok) throw new Error(j.error || r.statusText); return j; }));
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

/* Layout: run toggle -> KPI tiles -> three donuts -> recommendation callout -> memo
   -> [toggle] walk-through -> [toggle] ranked issues -> [toggle] cost calculator -> [toggle] how it works */
const TOPICS = ["access", "usability", "playback", "downloads", "catalog", "billing", "support", "other"];
const INTENTS = ["cancellation", "complaint", "request", "praise", "unclear"];
const diffV = i => i.verify && ["topic", "intent", "severity"].some(f => String(i.verify[f]) !== String(i[f]));
const diffH = i => i.human && ["topic", "intent", "severity"].some(f => String(i.human[f]) !== String(i[f]));
const pct1 = (n, d) => d ? (100 * n / d).toFixed(1) + "%" : "–";

/* ---------- run toggle ---------- */
function runs() {
  $("#runchips").innerHTML = D.runs.map((r, i) => `<button class="runchip ${r.status}" role="tab" data-i="${i}" aria-selected="false"><b>${esc(r.label)}</b><span>${r.status === "done" ? n0(r.rows_read) + " reviews · " + usd(r.total_cost_usd) : "pending"}</span></button>`).join("");
  $("#runchips").onclick = e => { const b = e.target.closest(".runchip"); if (b) selectRun(+b.dataset.i); };
  const fin = D.runs.findIndex(r => r.key === D.final_run && r.status === "done");
  selectRun(fin >= 0 ? fin : D.runs.map((r, i) => [r, i]).filter(([r]) => r.status === "done").pop()?.[1] ?? 0);
}
function selectRun(i) {
  RUN = D.runs[i];
  document.querySelectorAll(".runchip").forEach((b, k) => b.setAttribute("aria-selected", k === i));
  $("#runrole").textContent = RUN.role || "";
  ["rankRun", "howRun"].forEach(id => $("#" + id).textContent = RUN.label);
  if (RUN.status !== "done") {
    $("#kpis").innerHTML = `<p class="muted">Not run yet.</p>`; ["donuts", "reco", "memo", "rank", "examples", "rpath"].forEach(id => $("#" + id).innerHTML = "");
    return;
  }
  overview(); answer(); ranking(); examples(); searchSetup(); how();
}

/* ---------- KPI tiles + donuts: one /api/metrics call ---------- */
function tile(label, value, sub) { return `<div class="tile kpi"><b>${value}</b><span>${label}</span>${sub ? `<span class="sub">${sub}</span>` : ""}</div>`; }
function overview() {
  const r = RUN;
  $("#kpis").innerHTML = `<p class="small muted">Loading from the database…</p>`; $("#donuts").innerHTML = "";
  API("metrics", { run: r.key }).then(m => {
    if (RUN !== r) return;
    const st = m.status, done = st.completed || 0, full = D.full_file?.records;
    $("#kpis").innerHTML =
      tile("Reviews classified", n0(done), `of ${n0(m.rows)} in this run · ${n0(st.quarantined || 0)} quarantined${st.pending ? " · " + n0(st.pending) + " pending" : ""}`) +
      tile("Labels reused from identical text", n0(m.completed_via_exact_text_reuse), `${pct1(m.completed_via_exact_text_reuse, done)} of classified reviews, no model call`) +
      tile("Distinct texts sent to the model", n0(r.distinct), "one label per distinct text") +
      tile("Full file rows profiled", n0(full), full && m.rows < full ? `this run classifies ${pct1(done, full)} of them` : "the whole file");
    const cc = m.topics.reduce((a, t) => a + t.complaints, 0), T = Object.fromEntries(m.topics.map(t => [t.topic, t]));
    const c = t => T[t]?.complaints || 0;
    const intent = INTENTS.map((k, j) => ({ label: k, n: m.by_intent[k] || 0, color: `var(--s${j + 1})` }));
    const areas = [["Usability", c("usability")], ["Billing + support", c("billing") + c("support")], ["Playback", c("playback")], ["Access", c("access")]]
      .map(([label, n], j) => ({ label, n, color: `var(--s${j + 1})` }))
      .concat([{ label: "Not one of the four areas", n: c("other") + c("catalog") + c("downloads"), color: "var(--s-other)", note: "generic criticism, catalog, downloads" }]);
    const sev = [1, 2, 3, 4, 5].map(k => ({ label: "Severity " + k, n: m.by_severity[k] || 0, color: `var(--o${k})`, note: ["no problem, praise, unclear or a request", "annoyance or generic criticism", "degraded function, some use remains", "core task blocked", "serious financial, privacy or data harm"][k - 1] }));
    $("#donuts").innerHTML =
      donut("What customers say", "Intent of every classified review", intent, done, "reviews") +
      donut("Area comparison", "Complaints and cancellations by area", areas, cc, "complaints") +
      donut("Severity", "Severity of every classified review", sev, done, "reviews");
  }).catch(e => $("#kpis").innerHTML = `<div class="banner warn">Backend error: ${esc(e.message)}</div>`);
}
function donut(title, sub, parts, total, unit) {
  const R = 70, r0 = 46, cx = 90, cy = 90, sum = parts.reduce((a, p) => a + p.n, 0) || 1;
  let a0 = -Math.PI / 2;
  const arcs = parts.filter(p => p.n > 0).map(p => {
    const a1 = a0 + 2 * Math.PI * p.n / sum, large = a1 - a0 > Math.PI ? 1 : 0;
    const P = (rad, a) => `${(cx + rad * Math.cos(a)).toFixed(2)} ${(cy + rad * Math.sin(a)).toFixed(2)}`;
    const d = p.n === sum ? `M ${P(R, 0)} A ${R} ${R} 0 1 1 ${P(R, Math.PI)} A ${R} ${R} 0 1 1 ${P(R, 0)} M ${P(r0, 0)} A ${r0} ${r0} 0 1 0 ${P(r0, Math.PI)} A ${r0} ${r0} 0 1 0 ${P(r0, 0)} Z`
      : `M ${P(R, a0)} A ${R} ${R} 0 ${large} 1 ${P(R, a1)} L ${P(r0, a1)} A ${r0} ${r0} 0 ${large} 0 ${P(r0, a0)} Z`;
    a0 = a1;
    return `<path d="${d}" fill="${p.color}" class="slice" data-tip="${esc(p.label)}: ${n0(p.n)} ${unit} (${pct1(p.n, sum)})"></path>`;
  }).join("");
  return `<figure class="donut card"><figcaption><h3>${esc(title)}</h3><span class="small muted">${esc(sub)}</span></figcaption>
    <div class="donut-body"><svg viewBox="0 0 180 180" role="img" aria-label="${esc(title)} donut chart">${arcs}
      <text x="90" y="86" text-anchor="middle" class="d-total">${n0(total)}</text><text x="90" y="104" text-anchor="middle" class="d-unit">${esc(unit)}</text></svg>
    <table class="legend"><tbody>${parts.map(p => `<tr data-tip="${esc(p.note || p.label)}"><td><span class="sw" style="background:${p.color}"></span>${esc(p.label)}</td><td class="num">${n0(p.n)}</td><td class="num muted">${pct1(p.n, sum)}</td></tr>`).join("")}</tbody></table></div></figure>`;
}

/* ---------- recommendation callout + memo ---------- */
function md(s) { const L = s.split("\n"); let h = "", ul = false;
  const inl = t => esc(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\[([CTF]\d{3})\]/g, '<code class="small cite" data-tip="saved number: $1 in claims.csv or topic_claims.csv">$1</code>');
  for (const l of L) { if (/^\s*[-*] /.test(l)) { if (!ul) { h += "<ul>"; ul = true; } h += "<li>" + inl(l.replace(/^\s*[-*] /, "")) + "</li>"; continue; }
    if (ul) { h += "</ul>"; ul = false; }
    if (l.startsWith("## ")) h += "<h2>" + inl(l.slice(3)) + "</h2>"; else if (l.startsWith("# ")) h += "<h1>" + inl(l.slice(2)) + "</h1>"; else if (l.trim()) h += "<p>" + inl(l) + "</p>"; }
  return h + (ul ? "</ul>" : ""); }
function answer() {
  const r = RUN;
  if (!r.memo) { $("#reco").innerHTML = ""; $("#memo").innerHTML = `<div class="memo"><p class="muted">No memo for this run (the memo step was not run).</p></div>`; return; }
  const rec = (r.memo.split(/^## Recommendation\s*$/m)[1] || "").split(/^## /m)[0].trim();
  const area = (rec.match(/\*\*(.+?)\*\*/) || [])[1];
  const sents = rec.split(/(?<=\.)\s+(?=[A-Z])/), why = sents.length > 1 ? sents[1] : sents[0];  // sentence 1 names the area (shown as the headline)
  $("#reco").innerHTML = `<div class="callout"><span class="eyebrow">Recommended focus for next quarter</span>
    <div class="callout-area">${esc(area ? area[0].toUpperCase() + area.slice(1) : "See memo")}</div>
    <p><b>Why:</b> ${md(why).replace(/^<p>|<\/p>$/g, "")}</p><a class="small" href="#memo-s">Read the full memo ↓</a></div>`;
  const mc = r.memo_check;
  $("#memo").innerHTML = `<div class="memo"><div class="tags"><span class="chip model">AI written by ${esc({ "gpt-6-luna": "GPT-6 Luna", "claude-sonnet-5": "Claude Sonnet 5" }[r.memo_model] || (r.memo_model || "model").replace(/-/g, " "))} from saved totals only</span><span class="chip ${mc?.passed ? "evid" : "warn"}">Number check ${mc?.passed ? "passed" : "failed"}</span>${mc?.human_review ? `<span class="chip code" data-tip="The model's exact output is saved as memo_model_output.md; review_notes.md lists each edit">Reviewed by a person: ${mc.human_review.edits} edits, check ${mc.human_review.check_after_edits_passed ? "passed" : "failed"} after edits</span>` : ""}</div>
    ${mc && !mc.passed ? `<p class="small bad">Code found: ${esc(mc.errors.join("; "))}</p>` : ""}${md(r.memo)}
    <p class="small muted">Codes like C009 are saved numbers in <code>claims.csv</code> (one issue); T and F codes are in <code>topic_claims.csv</code> (areas, trends, coverage). Code, not the model, wrote each number.</p></div>`;
}

/* ---------- ranked issues (toggle) ---------- */
let HIDE_OTHER = false, SHOW_ALL = false;
const OPEN_ALL = new URLSearchParams(location.search).has("open");  // ?open=1 expands every toggle (handy for review)
function ranking() {
  const r = RUN;
  if (!r.ranking.length) { $("#rank").innerHTML = `<p class="muted">No ranking for this run.</p>`; return; }
  const all = r.ranking.filter(x => !(HIDE_OTHER && x.issue_id.startsWith("ISS_OTHER")));
  const rows = SHOW_ALL ? all : all.slice(0, 12);
  const mx = Math.max(...all.map(x => +x.priority_score));
  $("#rank").innerHTML = `<div class="rankhead"><p class="explain">Score = complaints × average severity (1 to 5) = sum of severities. Only complaints and cancellations count; ties break by issue ID. Click an issue to see its reviews.</p>
      <label class="inline"><input type="checkbox" id="hideOther" ${HIDE_OTHER ? "checked" : ""}> Hide the generic “other” bucket</label></div>
    <div class="tablewrap"><table><tr><th class="num">#</th><th>Issue</th><th>Area</th><th class="num">Complaints</th><th class="num">Avg severity</th><th>Score</th></tr>
    ${rows.map(x => { const is = r.issues[x.issue_id] || {}, gen = x.issue_id.startsWith("ISS_OTHER"); return `<tr class="${gen ? "generic" : ""}"><td class="num">${x.rank}</td><td><button class="linkbtn" data-issue="${esc(x.issue_id)}"><b>${esc(is.name)}</b></button>${gen ? ' <span class="tag" data-tip="Generic criticism with no specific product area; not one of the four areas in the question">not an area</span>' : ""}<br><code class="small" data-tip="${esc(is.description)}">${esc(x.issue_id)}</code></td><td>${esc(is.topic)}</td><td class="num">${n0(x.complaint_count)}</td><td class="num">${(+x.mean_severity).toFixed(2)}</td>
      <td class="barcell"><div class="hbarrow"><span class="track"><div class="hbar ${gen ? "muted-bar" : ""}" style="width:${(100 * x.priority_score / mx).toFixed(1)}%"></div></span><span class="val">${n0(x.priority_score)}</span></div></td></tr>`; }).join("")}</table></div>
    ${all.length > 12 ? `<button class="btn" id="showAll">${SHOW_ALL ? "Show top 12" : `Show all ${all.length} issues`}</button>` : ""}
    <div id="issuePanel"></div>`;
  if ($("#showAll")) $("#showAll").onclick = () => { SHOW_ALL = !SHOW_ALL; ranking(); };
  $("#hideOther").onchange = e => { HIDE_OTHER = e.target.checked; ranking(); };
  $("#rank").querySelectorAll("[data-issue]").forEach(b => b.onclick = () => issue(b.dataset.issue));
}
function issue(id) {
  const r = RUN, P = $("#issuePanel"); P.innerHTML = `<p class="muted small">Loading ${esc(id)}…</p>`;
  API("issue", { run: r.key, id, limit: 25 }).then(d => {
    const I = d.issue, cl = Object.fromEntries(d.claims.map(c => [c.metric, c.claim_id]));
    const cite = (m, v) => `${v}${cl[m] ? ` <code class="small" data-tip="claims.csv">${cl[m]}</code>` : ""}`;
    P.innerHTML = `<div class="card"><h3>#${I.rank} ${esc(I.name || id)} <code class="small">${esc(id)}</code></h3><p class="explain">${esc(I.description || "")}</p>
      <div class="tiles">${[["Complaints", cite("complaint_count", n0(I.complaint_count))], ["Severity sum = score", cite("severity_sum", n0(I.severity_sum))], ["Mean severity", cite("mean_severity", I.mean_severity)], ["Cancellation intent", n0(I.cancellations)]].map(([l, x]) => `<div class="tile"><b>${x}</b><span>${l}</span></div>`).join("")}</div>
      <p class="small muted">Severity mix: ${d.severity_counts.map(s => `sev ${s.severity}: ${n0(s.n)}`).join(" · ")}. Highest severity first; ×N = identical texts sharing one label. Click one to open it in the walk-through.</p>
      <div class="rlist" style="max-height:340px">${d.members.map((m, k) => `<button class="ritem" data-m="${k}"><span class="txt">${esc(m.text)}</span><span class="tags"><span class="tag">sev ${m.severity}</span><span class="tag">${m.intent}</span>${m.member_rows > 1 ? `<span class="tag">×${m.member_rows}</span>` : ""}</span></button>`).join("")}</div></div>`;
    P.querySelectorAll("[data-m]").forEach(b => b.onclick = () => openWalk(d.members[+b.dataset.m]));
  }).catch(e => P.innerHTML = `<div class="banner warn">${esc(e.message)}</div>`);
}

/* ---------- walk-through (toggle) ---------- */
function openWalk(item, banner) { $("#walk").open = true; path(item, banner); $("#rpath").scrollIntoView({ behavior: "smooth", block: "start" }); }
function examples() {
  const r = RUN; $("#examples").innerHTML = `<p class="small muted">Loading examples…</p>`;
  API("examples", { run: r.key }).then(d => {
    if (RUN !== r) return;
    $("#examples").innerHTML = d.examples.map((e, k) => `<button class="excard ${e.kind}" data-x="${k}" ${e.review ? "" : "disabled"}>
      <span class="exkind">${k + 1} · ${esc(e.title)}</span><span class="small">${esc(e.why)}</span>
      ${e.review ? `<span class="extext">“${esc(e.review.text.slice(0, 140))}${e.review.text.length > 140 ? "…" : ""}”</span><span class="tags"><span class="tag">${e.review.topic}</span><span class="tag">${e.review.intent}</span><span class="tag">sev ${e.review.severity}</span></span>` : `<span class="small muted">No review of this kind in this run.</span>`}</button>`).join("");
    $("#examples").querySelectorAll("[data-x]").forEach(b => b.onclick = () => {
      document.querySelectorAll(".excard").forEach(x => x.setAttribute("aria-pressed", x === b));
      path(d.examples[+b.dataset.x].review);
    });
    if (OPEN_ALL && d.examples[0].review) { $("#examples [data-x]").setAttribute("aria-pressed", "true"); path(d.examples[0].review); }
  }).catch(e => $("#examples").innerHTML = `<div class="banner warn">${esc(e.message)}</div>`);
}
function searchSetup() {
  const opt = (id, vals) => $(id).innerHTML = `<option value="">all</option>` + vals.map(v => `<option>${v}</option>`).join("");
  opt("#ftopic", TOPICS); opt("#fintent", INTENTS); opt("#fsev", [1, 2, 3, 4, 5]);
  $("#fdiff").innerHTML = `<option value="">all reviews</option>${RUN.verify ? `<option value="verify">Jev vs verifier disagreed</option><option value="verified">checked by the verifier</option>` : ""}${RUN.golden ? `<option value="human">my golden label disagreed</option>` : ""}<option value="flagged">flagged needs_review</option>`;
  $("#rlist").innerHTML = ""; $("#rpath").innerHTML = ""; $(".explorer").classList.remove("has-list");
}
let LIST = [];
function search() {
  const r = RUN;
  $(".explorer").classList.add("has-list");
  $("#rlist").innerHTML = `<p class="small muted">Querying the database…</p>`;
  API("reviews", { run: r.key, q: $("#qtext").value.trim(), topic: $("#ftopic").value, intent: $("#fintent").value, severity: $("#fsev").value, diff: $("#fdiff").value, limit: 200 }).then(d => {
    if (RUN !== r) return;
    LIST = d.reviews;
    $("#rlist").innerHTML = `<p class="small muted">${n0(d.total)} of ${n0(r.reviews_total)} distinct reviews match${d.total > LIST.length ? ` (first ${n0(LIST.length)} shown)` : ""}</p>` +
      LIST.map((i, k) => `<button class="ritem" data-k="${k}"><span class="txt">${hlWord(i.text, $("#qtext").value.trim())}</span>
        <span class="tags"><span class="tag">${i.topic}</span><span class="tag">${i.intent}</span><span class="tag">sev ${i.severity}</span>${diffV(i) ? '<span class="tag warn">Jev ≠ verifier</span>' : ""}${diffH(i) ? '<span class="tag human">me ≠ Jev</span>' : ""}${i.copies > 1 ? `<span class="tag">×${i.copies}</span>` : ""}</span></button>`).join("");
    $("#rlist").onclick = e => { const b = e.target.closest(".ritem"); if (!b) return; document.querySelectorAll("#rlist .ritem").forEach(x => x.setAttribute("aria-selected", x === b)); path(LIST[+b.dataset.k]); };
    if (!LIST.length) $("#rpath").innerHTML = `<p class="muted">No reviews match. Try another word or clear a filter.</p>`;
  }).catch(e => $("#rlist").innerHTML = `<div class="banner warn">Backend error: ${esc(e.message)}</div>`);
}
function hlWord(t, w) { if (!w) return esc(t); const i = t.toLowerCase().indexOf(w.toLowerCase()); return i < 0 ? esc(t) : esc(t.slice(0, i)) + "<mark>" + esc(t.slice(i, i + w.length)) + "</mark>" + esc(t.slice(i + w.length)); }
function trace(id) {
  API("review", { run: RUN.key, id }).then(d => {
    const rec = d.record;
    if (!d.review) { $("#rpath").innerHTML = `<div class="card"><h3>${esc(rec.review_id)}</h3><p>Status <b>${esc(rec.status)}</b>${rec.reason ? `, reason <code>${esc(rec.reason)}</code>` : ""}. Not classified, so it joins no issue and no aggregate.</p></div>`; return; }
    path(d.review, `<div class="banner info small">Record <code>${esc(rec.review_id)}</code> · status <b>${esc(rec.status)}</b> · ${rec.cache_source_id ? `labels reused from identical text in <code>${esc(rec.cache_source_id)}</code>` : "labeled directly"} · ${esc(rec.rating)} stars · ${esc(rec.month)}${d.issue ? ` · issue <code>${esc(d.issue.issue_id)}</code> rank #${d.issue.rank}, claims ${d.claims.map(c => `<code>${c.claim_id}</code>`).join(" ")}` : ""}${d.cited_in_memo ? " · <b>cited in the memo</b>" : ""}</div>`);
  }).catch(e => $("#rpath").innerHTML = `<div class="banner warn">${esc(e.message)}</div>`);
}
function hl(t, q) { const i = q ? t.indexOf(q) : -1; return i < 0 ? esc(t) : esc(t.slice(0, i)) + "<mark>" + esc(q) + "</mark>" + esc(t.slice(i + q.length)); }
function path(i, banner = "") {
  if (!i) return;
  const j = i.jev || {}, probs = Object.entries(j.topic_probs || {}).sort((a, b) => b[1] - a[1]).slice(0, 3);
  const cmpRow = (a, b) => `<td class="${String(a) === String(b) ? "" : "d"}">${esc(b)}</td>`;
  const cols = [["Pipeline (Jev + code)", i]].concat(i.verify ? [["Verifier, blind (Haiku)", i.verify]] : []).concat(i.human ? [["Golden label (me)", i.human]] : []);
  const step = (n, c, t, who, b) => `<div class="step"><div class="badge ${c}">${n}</div><div class="body"><h3>${t} <span class="chip ${c === "evid" ? "evid" : c}">${who}</span></h3>${b}</div></div>`;
  const bars = probs.map(([k, v]) => `<div class="pbar"><span>${k}</span><span class="track"><span class="fill" style="width:${(v * 100).toFixed(0)}%"></span></span><span class="num">${(v * 100).toFixed(0)}%</span></div>`).join("");
  $("#rpath").innerHTML = banner + `<div class="steps">` +
    step(1, "code", "Prepare", "code", `<div class="quote">${hl(i.text, i.quote)}</div><p class="small muted">${esc(i.stars)} stars (kept as metadata, never shown to a model) · ${esc(i.date)} · ${i.copies > 1 ? `this exact text appears ${n0(i.copies)} times: labeled once, reused for the rest` : "unique text"}. Highlight = the saved evidence quote.</p>`) +
    step(2, "model", "Classify", "Jev + code rules", `${bars ? `<div class="pbars"><span class="small muted">Jev's top topics</span>${bars}</div>` : ""}<p class="small">Departure probability ${n2(j.leaving)} (≥ 0.5 sets cancellation). ${i.decided_by === "haiku_fallback" ? "<b>Jev was unsure, so the capped Haiku fallback relabeled it.</b>" : "Decided by Jev."}</p>
      <p class="small">Result: <b>${esc(i.topic)}</b> · <b>${esc(i.intent)}</b> · severity <b>${esc(i.severity)}</b> · sentiment ${n2(i.sentiment)}. Flags: ${i.reasons.length ? i.reasons.map(x => `<code>${esc(x)}</code>`).join(" ") : "none"}</p>`) +
    step(3, "model", "Verify and compare", "Haiku + code", `<div class="tablewrap"><table class="cmp"><tr><th></th>${cols.map(c => `<th>${c[0]}</th>`).join("")}</tr>
      ${["topic", "intent", "severity", "sentiment"].map(f => `<tr><td>${f}</td>${cols.map(([, o], k) => k === 0 ? `<td>${esc(f === "sentiment" ? n2(o[f]) : o[f])}</td>` : cmpRow(f === "sentiment" ? n2(i[f]) : i[f], f === "sentiment" ? n2(o[f]) : o[f])).join("")}</tr>`).join("")}</table></div>
      ${cols.length === 1 ? `<p class="small muted">Not in the random verifier sample${RUN.key === "golden" ? "" : " and not a golden review"}; only about 1% of texts are double checked.</p>` : `<p class="small muted">Red = different from the pipeline.</p>`}`) +
    step(4, "code", "Group", "code (+ Haiku names)", !RUN.ranking.length ? `<p class="muted">Grouping was not run for this run.</p>` : i.issue ? `<p>Joins issue <code>${esc(i.issue)}</code>: <b>${esc(i.issue_name)}</b></p>` : `<p class="muted">Intent is ${esc(i.intent)}, not a complaint or cancellation, so it joins no issue.</p>`) +
    step(5, "code", "Rank", "SQL", i.issue_rank ? `<p>That issue ranks <b>#${i.issue_rank}</b>; this review adds ${i.severity} to its score.</p>` : `<p class="muted">Not ranked.</p>`) +
    step(6, "evid", "Recommend", "Sonnet + code check", `<p>${i.in_memo ? "<b>Quoted in the memo.</b>" : i.issue_rank && i.issue_rank <= 10 ? "Its issue is in the memo's evidence pack." : "Not cited in the memo."}</p>`) + `</div>`;
}

/* ---------- how it works (toggle, visual) ---------- */
const PHASES = [
  ["code", "Prepare", "Read every row, fingerprint it, group identical texts, set empty ones aside", "Code", "CSV → texts to label"],
  ["model", "Classify", "Jev answers 5 fixed questions per review; code validates and maps; unsure cases get a capped Haiku second look", "Jev + code", "text → topic, intent, severity, quote"],
  ["model", "Verify", "Haiku relabels a random 1% without seeing Jev's answer; code compares", "Haiku + code", "sample → agreement report"],
  ["mix", "Group", "Code puts each complaint into exactly one issue; Haiku only suggests names", "Code + Haiku", "complaints → issues"],
  ["code", "Rank", "Score = complaints × average severity, computed in SQL", "Code", "issues → ranking"],
  ["mix", "Recommend", "Sonnet writes the memo from saved totals only; code checks every number and ID; a person reviews", "Sonnet + code", "ranking → memo"]];
function how() {
  const r = RUN, c = r.calls || {}, v = r.verify, g = r.golden?.summary, T = D.system_tests;
  const flow = `<div class="flow">${PHASES.map(([cl, t, s, w, io], i) => `<div class="phase ${cl}"><span class="n">${i + 1} · ${w}</span><span class="t">${t}</span><span class="s">${s}</span><span class="pio">${io}</span></div>`).join("")}</div>
    <div class="legend-row"><span class="chip code">Code</span><span class="muted small">exact, free, repeatable</span><span class="chip model">Model</span><span class="muted small">reads language, paid per call</span><span class="chip evid">Both</span><span class="muted small">model proposes, code checks</span></div>`;
  const stages = [["Classify (Jev)", "jev_classify"], ["Hard cases (Haiku)", "haiku_fallback"], ["Verify (Haiku)", "verify"], ["Group names (Haiku)", "group"], ["Memo (Sonnet)", "memo"]].filter(([, k]) => c[k]);
  const tot = stages.reduce((a, [, k]) => a + c[k].cost_usd, 0) || 1;
  const spend = `<div class="card"><h3>Where the money went in this run · ${usd(r.total_cost_usd)}</h3>
    <div class="costbar">${stages.map(([l, k], j) => `<span style="width:${Math.max(0.6, 100 * c[k].cost_usd / tot)}%;background:var(--s${j + 1})" data-tip="${esc(l)}: ${usd(c[k].cost_usd)} · ${n0(c[k].attempts)} calls"></span>`).join("")}</div>
    <table class="legend"><tbody>${stages.map(([l, k], j) => `<tr><td><span class="sw" style="background:var(--s${j + 1})"></span>${esc(l)}</td><td class="num">${n0(c[k].attempts)} calls</td><td class="num">${n0(c[k].failed)} failed</td><td class="num">${usd(c[k].cost_usd)}</td><td class="num muted">${pct1(c[k].cost_usd, tot)}</td></tr>`).join("")}</tbody></table>
    <p class="small muted">Prepare, records and rank are code only and cost nothing. Failed attempts are retried with backoff; every attempt is logged.</p></div>`;
  const meter = (label, x, sub) => `<div class="meter"><div class="mhead"><span>${label}</span><b>${pct(x)}</b></div><div class="mtrack"><span style="width:${(100 * x).toFixed(0)}%"></span></div>${sub ? `<span class="small muted">${sub}</span>` : ""}</div>`;
  let checks = "";
  if (g) {
    const conf = r.golden.confusion, head = conf[0].slice(1), mx = Math.max(1, ...conf.slice(1).flatMap(x => x.slice(1).map(Number)));
    checks += `<div class="card"><h3>Golden 50 · my hand labels vs the pipeline</h3>
      <div class="meters">${meter("Topic", g.topic_agreement)}${meter("Intent", g.intent_agreement)}${meter("Severity exact", g.severity_exact, "average gap " + n2(g.severity_mae) + " levels")}${meter("Quote is an exact substring", g.quote_exact_substring_rate)}</div>
      <p class="small muted">I labeled these 50 before any model saw them; my labels never enter a prompt. 50 is a small diagnostic sample.</p>
      <details><summary>Topic confusion table</summary><div class="tablewrap"><table class="heat"><tr><th>me \\ pipeline</th>${head.map(h => `<th class="num">${h}</th>`).join("")}</tr>
      ${conf.slice(1).map(x => `<tr><th>${x[0]}</th>${x.slice(1).map((y, k) => `<td class="num" style="background:color-mix(in srgb,var(--code) ${Math.round(60 * y / mx)}%,var(--surface))" data-tip="me ${x[0]}, pipeline ${head[k]}: ${y}">${y === "0" ? "" : y}</td>`).join("")}</tr>`).join("")}</table></div></details></div>`;
  }
  if (v) checks += `<div class="card"><h3>Independent verifier · Jev vs Haiku on ${n0(v.n)} random texts</h3>
      <div class="meters">${meter("Topic", v.topic_agreement)}${meter("Intent", v.intent_agreement)}${meter("Severity exact", v.severity_exact, "average gap " + n2(v.severity_mae) + " levels")}</div>
      <p class="small muted">${n0(v.disagreements)} texts disagree on at least one field; search them in the walk-through with “Jev vs verifier disagreed”.</p></div>`;
  const tests = T ? `<div class="card"><h3>System tests · ${T.passed} of ${T.total} passed</h3><p class="small muted">Real model calls on synthetic reviews with faults injected in code (${usd(T.api_spend_usd)}); kept out of every business number.</p>
      <div class="testgrid">${T.results.map(x => `<div class="testcell ${x.passed ? "ok" : "bad"}" data-tip="${esc(x.what)} → ${esc(JSON.stringify(x.observed).slice(0, 220))}"><span class="mark">${x.passed ? "✓" : "✗"}</span><span>${esc((t => t[0].toUpperCase() + t.slice(1))(x.test.replace(/_/g, " ").replace(/\bapi\b/, "API").replace(/\bcsv\b/, "CSV")))}</span></div>`).join("")}</div></div>` : "";
  const notes = `<div class="notes">${[
    ["Scope", "The full file (660,622 rows) is profiled. The final run classifies a seeded 100,000 review sample that contains the golden 50 and the 10,000 development sample; the other 560,609 nonempty reviews are not classified."],
    ["Resume", "Every result is saved as it arrives. The final run was stopped on purpose at 25,000 texts and resumed without paying again for finished reviews, then recovered from a real network outage."],
    ["Limits", "Reviews are self selected; cancellation language is intent, not churn. The generic “other” bucket includes boycott posts. Severity tends to be one level high on premium restrictions."]]
    .map(([t, s]) => `<div class="note"><b>${t}</b><span class="small">${s}</span></div>`).join("")}</div>`;
  $("#howBody").innerHTML = flow + `<div class="howgrid">${spend}${checks}${tests}</div>` + notes;
}

/* ---------- cost calculator (unchanged logic) ---------- */
let PR = {}, CH = {}, CTL = {};
const rate = (m, item) => PR[m + "|" + item] ?? 0;
const OPTIONS = {
  classify: [["jev", "Jev 1.13.0 (measured)"], ["haiku", "Claude Haiku 4.5 only (estimate)"]],
  fallback: [["haiku", "Claude Haiku 4.5, capped (measured)"], ["sonnet", "Claude Sonnet 5, capped (estimate)"], ["off", "Off"]],
  verify: [["haiku", "Claude Haiku 4.5 (measured)"], ["sonnet", "Claude Sonnet 5 (estimate)"]],
  group: [["haiku", "Claude Haiku 4.5 (measured)"], ["sonnet", "Claude Sonnet 5 (estimate)"]],
  memo: [["sonnet", "Claude Sonnet 5 (measured)"], ["luna", "GPT-6 Luna (estimate)"], ["haiku", "Claude Haiku 4.5 (estimate)"]]};
const MODEL = { haiku: "claude-haiku-4-5-20251001", sonnet: "claude-sonnet-5", luna: "gpt-6-luna" };
function calc() {
  const C = D.cost;
  if (!C.available) { $("#calc").innerHTML = `<p class="muted">The paid pilot has not been run yet: <code>python3 cost/calculator.py pilot</code></p>`; return; }
  C.rates.forEach(r => PR[r.model + "|" + r.item] = +r.price_per_unit_usd);
  CH = { classify: "jev", fallback: "haiku", verify: "haiku", group: "haiku", memo: "sonnet" };
  const A = C.assumptions;
  CTL = { n: 100013, reuse: true, workers: A.scenarios.base.workers, cap: A.controls.spend_cap_usd, fbcap: A.controls.fallback_fraction_cap, rps: A.controls.max_requests_per_second };
  const E = C.estimates;
  $("#calc").innerHTML = `<div class="calc">
    <div class="stagepick"><h3>1 · Choose a model per step</h3>
      ${Object.entries(OPTIONS).map(([k, opts]) => `<label>${{ classify: "Classify", fallback: "Hard cases", verify: "Verify", group: "Name issues", memo: "Memo" }[k]}<select data-ch="${k}">${opts.map(([v, l]) => `<option value="${v}">${l}</option>`).join("")}</select></label>`).join("")}
      <h3 style="margin-top:8px">2 · Choose a volume</h3>
      <div class="volume"><input type="range" id="vol" min="2" max="5.82" step="0.01" value="5">
        <div class="presets">${[[50, "Golden 50"], [100, "Pilot 100"], [500, "Dev 500"], [10000, "10,000"], [100013, "Final 100,000"], [660622, "Full 660,622"]].map(([v, l]) => `<button class="btn" data-n="${v}">${l}</button>`).join("")}</div>
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


/* ---------- boot ---------- */
API("site").then(d => {
  D = d; calc(); runs();
  if (OPEN_ALL) document.querySelectorAll("details.toggle").forEach(x => x.open = true);
  $("#searchForm").onsubmit = e => { e.preventDefault(); search(); };
  $("#traceForm").onsubmit = e => { e.preventDefault(); const v = $("#traceId").value.trim(); if (v) trace(v); };
  $("#foot").innerHTML = `Served by the backend (<code>/api</code>, Python) from a SQLite database built from saved run files by <code>python3 -m pipeline db</code> on ${esc(D.db_built_at)}. No API keys and no model calls on this page or in the backend. Data: BwandoWando, 3.4 Million Spotify Google Store Reviews (CC0), May 2022 to Nov 2023. Reviews are self selected; cancellation language is expressed intent, not observed churn. <a href="${esc(D.repo)}">Source code</a> · <a href="/api/health">/api/health</a>`;
}).catch(e => document.querySelector("main").insertAdjacentHTML("afterbegin", `<div class="banner warn">Could not reach the backend (/api/site): ${esc(e.message)}</div>`));
