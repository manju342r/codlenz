/* CodeLens demo client. Same JSON API the CLI uses; all rendering escapes model text. */
"use strict";

const $ = (id) => document.getElementById(id);
const resultEl = $("result");
const chainEl = $("chainage");
const chainText = $("chain-text");
const surveyTime = $("survey-time");

/* Backend selection: same origin by default; ?backend=https://host persists
   to localStorage (used when this page is hosted statically, e.g. Vercel). */
function apiBase() {
  try {
    const q = new URLSearchParams(location.search).get("backend");
    if (q) {
      localStorage.setItem("codelens-backend", q);
      return q.replace(/\/$/, "");
    }
    return localStorage.getItem("codelens-backend") || "";
  } catch (e) { return ""; }
}
const API = apiBase();

const DEMO_SAMPLE = `## 1. PROJECT OVERVIEW
- CodeLens helps developers understand unfamiliar codebases locally.
- Scan, architectural briefing, and grounded Q&A with verified references.
- Canned demo sample — not a live model run.
## 2. TECHNOLOGY STACK
- Python CLI (Click, Rich); zero-dependency web page.
- Ollama + Gemma 3 4B primary, Qwen 2.5 3B fallback.
## 3. ARCHITECTURE
- CLI and demo server share one pipeline: scan, retrieve, prompt, verify.
- Browser page calls same-origin /api/* endpoints.
## 4. KEY COMPONENTS
- scanner.py: pathlib repo index.
- verifier.py: guilty-until-proven-innocent ref checker.
## 5. EXECUTION FLOW
- Path or Git URL resolves to a directory.
- Scanner indexes, model explains, verifier checks each citation.
## 6. AI AND MEMORY ARCHITECTURE
- Stateless local inference; the prompt carries all context per call.
## 7. IMPORTANT FINDINGS
- CONFIRMED: no network calls leave the machine except localhost Ollama.
- SUSPECTED: nothing in this sample — run a live survey for real findings.
## 8. QUICK SUMMARY
- Local-first code understanding with citations you can trust, verified line by line.`;

let chainTimer = null;

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function renderBody(text) {
  let h = "", inList = false;
  const closeList = () => { if (inList) { h += "</ul>"; inList = false; } };
  for (const raw of String(text).split("\n")) {
    const trimmed = raw.trim();
    if (/^##\s+/.test(trimmed)) {
      closeList();
      h += `<h3>${esc(trimmed.replace(/^##\s+/, ""))}</h3>`;
      continue;
    }
    const m = raw.match(/^(\s*)- (.*)$/);
    if (m) {
      if (!inList) { h += '<ul class="brief">'; inList = true; }
      const pad = Math.min(m[1].length, 6);
      h += `<li${pad ? ` style="margin-left:${(pad * 1.1).toFixed(1)}rem"` : ""}>${esc(m[2])}</li>`;
      continue;
    }
    closeList();
    if (trimmed) h += `<p>${esc(trimmed)}</p>`;
  }
  closeList();
  return h;
}

function paragraphs(text) {
  return renderBody(text);
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

function showError(message, demo) {
  Narrator.stop();
  document.getElementById("listen-bar").hidden = true;
  resultEl.innerHTML = `<div class="error-state" role="alert"><strong>Survey failed.</strong><p>${esc(message)}</p>${
    demo ? `<p><button type="button" id="btn-demo">Load canned demo sample</button></p>` : ""
  }</div>`;
  const b = document.getElementById("btn-demo");
  if (b) b.addEventListener("click", () => {
    resultEl.innerHTML = `<div class="answer-body"><p class="hint">Canned demo sample — connect a backend for live surveys.</p>${renderBody(DEMO_SAMPLE)}</div>`;
    Narrator.refresh();
  });
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
  let r;
  try {
    r = await fetch(API + url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (err) {
    throw new Error(`Cannot reach backend (${API || "same origin"}). Make sure 'codelens serve' is running.`);
  }
  const ct = r.headers.get("content-type") || "";
  if (!ct.includes("application/json")) {
    if (!r.ok) {
      throw new Error(
        API
          ? `Backend returned HTTP ${r.status}`
          : `No backend connected (HTTP ${r.status}). Run 'codelens serve' and add ?backend=http://localhost:8000 to the URL.`
      );
    }
    throw new Error("Backend did not return JSON.");
  }
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}

async function runScan() {
  const path = $("path").value.trim();
  if (!path) { showError("Enter a repository path first."); return; }
  Narrator.stop();
  setBusy(true);
  try {
    let r;
    try {
      r = await fetch(`${API}/api/scan?path=${encodeURIComponent(path)}`);
    } catch (err) {
      throw new Error(`Cannot reach backend (${API || "same origin"}). Make sure 'codelens serve' is running.`);
    }
    const ct = r.headers.get("content-type") || "";
    if (!ct.includes("application/json")) {
      if (!r.ok) {
        throw new Error(
          API
            ? `Backend returned HTTP ${r.status}`
            : `No backend connected (HTTP ${r.status}). Run 'codelens serve' and add ?backend=http://localhost:8000 to the URL.`
        );
      }
      throw new Error("Backend did not return JSON.");
    }
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
  Narrator.refresh();
}

async function runModel(action) {
  const path = $("path").value.trim();
  if (!path) { showError("Enter a repository path first."); return; }
  const q = $("q").value.trim();
  if (action === "ask" && !q) { showError("Enter a question first."); return; }
  Narrator.stop();
  setBusy(true);
  const t0 = startChainage(action === "analyze" ? "Analyzing" : "Asking the local model");
  try {
    const data = await postJSON(`/api/${action}`, { path, q });
    stopChainage();
    if (data.error) { showError(data.error); return; }
    data.elapsed_s = Math.round(((performance.now() - t0) / 1000) * 10) / 10;
    renderAnswer(data);
    surveyTime.textContent = `last survey ${data.elapsed_s}s · ${data.model || "unknown model"} · ${new Date().toLocaleTimeString()}`;
  } catch (e) { stopChainage(); showError(e.message, true); } finally { setBusy(false); }
}

$("btn-scan").addEventListener("click", runScan);
$("btn-analyze").addEventListener("click", () => runModel("analyze"));
$("btn-ask").addEventListener("click", () => runModel("ask"));

/* Listen to Summary: narrates the verified answer text with speechSynthesis.
   No new content is generated — bullets are read in order, markdown stripped. */
function sayable(s) {
  return String(s)
    .replace(/✅/g, "verified")
    .replace(/❌/g, "rejected")
    .replace(/⚠️?/g, "warning")
    .replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B00}-\u{2BFF}\u{FE0F}]/gu, "")
    .replace(/`{1,3}/g, "")
    .replace(/\*\*?/g, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/([A-Za-z0-9_./-]+\.[A-Za-z0-9]+):(\d+)[–-](\d+)/g, "$1, lines $2 to $3")
    .replace(/([A-Za-z0-9_./-]+\.[A-Za-z0-9]+):(\d+)/g, "$1, line $2")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function sectionIntro(title) {
  const m = title.match(/^(\d+)\.\s*(.*)$/);
  return m ? `Section ${m[1]}: ${m[2]}.` : `${title}.`;
}

const Narrator = (() => {
  const supported = "speechSynthesis" in window;
  let queue = [];   // [{sec, li, text}]
  let qi = 0, playing = false;
  let sections = []; // [{title, items: [li elements]}]
  let statusEl = null, secSelect = null;

  function collect() {
    sections = [];
    const heads = [...document.querySelectorAll("#result .answer-body h3")];
    if (!heads.length) {
      const items = [...document.querySelectorAll("#result .answer-body ul.brief > li")];
      if (items.length) sections = [{ title: "Answer", head: null, items }];
      return;
    }
    for (const h of heads) {
      const items = [];
      let el = h.nextElementSibling;
      while (el && el.tagName !== "H3") {
        if (el.tagName === "UL") items.push(...el.querySelectorAll(":scope > li"));
        el = el.nextElementSibling;
      }
      sections.push({ title: h.textContent.trim(), head: h, items });
    }
  }

  function clearMarks() {
    document.querySelectorAll("#result .narrating").forEach((el) => el.classList.remove("narrating"));
  }

  function setStatus(s) { if (statusEl) statusEl.textContent = s; }

  function mark(sec, idx) {
    clearMarks();
    const S = sections[sec];
    if (!S) return;
    if (S.head) S.head.classList.add("narrating");
    const li = S.items[idx];
    if (li) {
      li.classList.add("narrating");
      li.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
    setStatus(`Narrating: ${S.title} — bullet ${idx + 1} of ${S.items.length}`);
  }

  function utter(text, onend) {
    const u = new SpeechSynthesisUtterance(text);
    const vs = document.getElementById("narr-voice");
    if (vs && vs.value) {
      const v = speechSynthesis.getVoices().find((x) => x.name === vs.value);
      if (v) u.voice = v;
    }
    const rs = document.getElementById("narr-rate");
    u.rate = rs ? parseFloat(rs.value) : 1;
    u.onend = onend;
    u.onerror = onend;
    speechSynthesis.speak(u);
  }

  function step() {
    if (!playing || qi >= queue.length) { finish(true); return; }
    const { sec, idx, text } = queue[qi];
    mark(sec, idx);
    utter(text, () => { qi += 1; step(); });
  }

  function buildQueue(secFilter) {
    queue = [];
    sections.forEach((S, si) => {
      if (secFilter != null && si !== secFilter) return;
      S.items.forEach((li, ii) => {
        const t = sayable(li.textContent);
        if (t) queue.push({ sec: si, idx: ii, text: t });
      });
    });
  }

  function playQueue(label) {
    if (!queue.length) return;
    speechSynthesis.cancel();
    playing = true;
    qi = 0;
    if (label) setStatus(label);
    step();
  }

  function finish(done) {
    playing = false;
    if (done) { clearMarks(); setStatus(sections.length ? "Finished." : ""); }
  }

  return {
    refresh() {
      const bar = document.getElementById("listen-bar");
      if (!supported) { bar.hidden = true; return; }
      collect();
      if (!sections.length || !sections.some((S) => S.items.length)) { bar.hidden = true; return; }
      bar.hidden = false;
      bar.innerHTML = `<div class="listen-bar" role="group" aria-label="Listen to Summary">
        <h2>Listen to Summary</h2>
        <div class="listen-controls">
          <button type="button" data-act="all">Play all</button>
          <button type="button" data-act="pause">Pause</button>
          <button type="button" data-act="resume">Resume</button>
          <button type="button" data-act="stop">Stop</button>
          <label>Section <select id="narr-sec" aria-label="Choose section"></select></label>
          <button type="button" data-act="sec">Play section</button>
          <label>Voice <select id="narr-voice" aria-label="Choose voice"></select></label>
          <label>Speed <select id="narr-rate" aria-label="Playback speed">
            <option value="0.75">0.75x</option><option value="1" selected>1x</option>
            <option value="1.25">1.25x</option><option value="1.5">1.5x</option>
          </select></label>
        </div>
        <div class="listen-status" id="narr-status" role="status"></div>
      </div>`;
      statusEl = document.getElementById("narr-status");
      secSelect = document.getElementById("narr-sec");
      sections.forEach((S, i) => {
        const o = document.createElement("option");
        o.value = i;
        o.textContent = `${S.title} (${S.items.length})`;
        secSelect.appendChild(o);
      });
      const fillVoices = () => {
        const sel = document.getElementById("narr-voice");
        if (!sel || sel.options.length) return;
        speechSynthesis.getVoices().forEach((v) => {
          const o = document.createElement("option");
          o.value = v.name;
          o.textContent = `${v.name} (${v.lang})`;
          if (v.default) o.selected = true;
          sel.appendChild(o);
        });
      };
      fillVoices();
      if (speechSynthesis.onvoiceschanged !== undefined) speechSynthesis.onvoiceschanged = fillVoices;
      setStatus(`Ready — ${sections.length} section${sections.length > 1 ? "s" : ""}.`);
      bar.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => this.act(b.dataset.act)));
    },
    act(which) {
      if (!supported) return;
      if (which === "all") { buildQueue(null); playQueue("Playing full summary…"); }
      else if (which === "sec" && secSelect) {
        const i = parseInt(secSelect.value, 10);
        buildQueue(i);
        playQueue(`Playing: ${sections[i] ? sections[i].title : ""}`);
      }
      else if (which === "pause") { speechSynthesis.pause(); setStatus("Paused."); }
      else if (which === "resume") { speechSynthesis.resume(); }
      else if (which === "stop") { speechSynthesis.cancel(); finish(false); clearMarks(); setStatus("Stopped."); }
    },
    stop() {
      if (!supported) return;
      speechSynthesis.cancel();
      playing = false;
      clearMarks();
    },
  };
})();

(function theme() {
  const btn = $("btn-theme");
  const apply = (dark) => {
    document.documentElement.dataset.theme = dark ? "dark" : "";
    if (!dark) delete document.documentElement.dataset.theme;
    btn.setAttribute("aria-pressed", String(dark));
    btn.textContent = dark ? "Lights on" : "Lights out";
    try { localStorage.setItem("codelens-theme", dark ? "dark" : "light"); } catch (e) {}
  };
  let dark = false;
  try {
    const saved = localStorage.getItem("codelens-theme");
    dark = saved ? saved === "dark"
      : window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  } catch (e) {}
  apply(!!dark);
  btn.addEventListener("click", () => apply(document.documentElement.dataset.theme !== "dark"));
})();
