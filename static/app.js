/* CodeLens demo client. Same JSON API the CLI uses; all rendering escapes model text. */
"use strict";

const $ = (id) => document.getElementById(id);
const resultEl = $("result");
const chainEl = $("chainage");
const chainText = $("chain-text");
const surveyTime = $("survey-time");

let chainTimer = null;

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function paragraphs(text) {
  return esc(text).split(/\n{2,}|\n/).filter((p) => p.trim())
    .map((p) => `<p>${p}</p>`).join("");
}

function badge(kind) {
  const id = kind === "verified" ? "i-pin" : kind === "rejected" ? "i-void" : "i-query";
  return `<svg class="badge" aria-hidden="true"><use href="#${id}"/></svg>`;
}

function startChainage(label) {
  const t0 = performance.now();
  chainEl.hidden = false;
  const tick = () => {
    const s = Math.floor((performance.now() - t0) / 1000);
    const mm = String(Math.floor(s / 60)).padStart(2, "0");
    const ss = String(s % 60).padStart(2, "0");
    chainText.textContent = `${label} … ${mm}:${ss}`;
  };
  tick();
  chainTimer = setInterval(tick, 250);
  return t0;
}

function stopChainage() {
  clearInterval(chainTimer);
  chainTimer = null;
  chainEl.hidden = true;
}

function setBusy(busy) {
  for (const id of ["btn-scan", "btn-analyze", "btn-ask"]) $(id).disabled = busy;
}

function showError(message) {
  resultEl.innerHTML = `<div class="error-state" role="alert"><strong>Survey failed.</strong><p>${esc(message)}</p></div>`;
}

function durationBar(seconds) {
  const w = Math.max(4, Math.min(320, seconds * 14));
  return `<div class="duration" aria-label="Model call took ${esc(String(seconds))} seconds">
    <span>surveyed in ${esc(String(seconds))}s</span>
    <span class="bar" style="width:${w}px" aria-hidden="true"></span></div>`;
}

function refItem(kind, key, coord, extra, excerpt) {
  const cls = kind === "verified" ? "verified" : "rejected";
  const reason = extra ? `<span class="reason">${esc(extra)}</span>` : "";
  const body = excerpt ? `<pre>${esc(excerpt)}</pre>` : "";
  return `<details class="ref ${cls}">
    <summary>${badge(kind)}<span class="key">${key}</span>
    <span class="coord">${esc(coord)}</span>${reason}</summary>${body}</details>`;
}

function wireFocusDimming() {
  const ev = resultEl.querySelector(".evidence");
  if (!ev) return;
  ev.addEventListener("toggle", () => {
    ev.classList.toggle("has-open", !!ev.querySelector(".ref[open]"));
  }, true);
}

async function postJSON(url, payload) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}

async function runScan() {
  const path = $("path").value.trim();
  if (!path) { showError("Enter a repository path first."); return; }
  setBusy(true);
  try {
    const r = await fetch(`/api/scan?path=${encodeURIComponent(path)}`);
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
    const rows = [
      ["Languages", esc(JSON.stringify(d.languages))],
      ["Folders", esc((d.folders || []).join(", ")) || "—"],
      ["Manifests", `<span class="mono">${esc((d.manifests || []).join(", ")) || "—"}</span>`],
      ["Likely entry points", `<span class="mono">${esc((d.entry_points || []).join(", ")) || "none found (candidates only)"}</span>`],
      ["Source files", esc(String(d.file_count))],
      ["Skipped", esc(String(d.skipped))],
    ];
    if (d.truncated) rows.push(["Note", "Partial analysis — file limit reached."]);
    resultEl.innerHTML = `<h2 style="margin-top:0">Schedule — ${esc(d.repo_name)}</h2>
      <table class="schedule"><tbody>${rows.map(([k, v]) => `<tr><th scope="row">${k}</th><td>${v}</td></tr>`).join("")}</tbody></table>
      <p class="hint">Instant — no AI call. Same index Analyze and Ask build on.</p>`;
  } catch (e) { showError(e.message); } finally { setBusy(false); }
}

function renderAnswer(data) {
  const vok = data.verified || [];
  const bad = data.rejected || [];
  const excerpts = data.excerpts || {};
  let verdict;
  if (vok.length && !bad.length) verdict = "VERIFIED — every cited coordinate checked against the files.";
  else if (vok.length) verdict = "PARTIAL — only the ✅ coordinates below are evidence.";
  else if (bad.length) verdict = "UNSUPPORTED — no cited coordinate verified. Do not treat as fact.";
  else verdict = "INFERRED — the model cited nothing checkable.";

  let h = `<div class="answer-body">${paragraphs(data.answer)}</div>
    <p class="verdict-line">${esc(verdict)}</p><div class="evidence">`;
  if (vok.length) {
    h += "<h2>Monuments — verified coordinates</h2>" + vok.map((c, i) =>
      refItem("verified", `K${i + 1}`, c, "", excerpts[c] || "")).join("");
  }
  if (bad.length) {
    h += "<h2>Voids — rejected, do not trust</h2>" + bad.map((b, i) =>
      refItem("rejected", `V${i + 1}`, b.coord || b, b.reason || "", "")).join("");
  }
  resultEl.innerHTML = h + "</div>" + (data.elapsed_s != null ? durationBar(data.elapsed_s) : "");
  wireFocusDimming();
}

async function runModel(action) {
  const path = $("path").value.trim();
  if (!path) { showError("Enter a repository path first."); return; }
  const q = $("q").value.trim();
  if (action === "ask" && !q) { showError("Enter a question first."); return; }
  setBusy(true);
  const t0 = startChainage(action === "analyze" ? "Analyzing" : "Asking the local model");
  try {
    const data = await postJSON(`/api/${action}`, { path, q });
    stopChainage();
    if (data.error) { showError(data.error); return; }
    data.elapsed_s = Math.round(((performance.now() - t0) / 1000) * 10) / 10;
    renderAnswer(data);
    surveyTime.textContent = `last survey ${data.elapsed_s}s · ${new Date().toLocaleTimeString()}`;
  } catch (e) { stopChainage(); showError(e.message); } finally { setBusy(false); }
}

$("btn-scan").addEventListener("click", runScan);
$("btn-analyze").addEventListener("click", () => runModel("analyze"));
$("btn-ask").addEventListener("click", () => runModel("ask"));
