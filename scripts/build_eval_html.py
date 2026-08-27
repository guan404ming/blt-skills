#!/usr/bin/env python3
"""Build a self-contained blind A/B evaluation web page from the human-eval sheet.

Reads data/human_eval/human_eval_sheet.csv and emits a single static HTML file
(no server, no dependencies) that raters open in a browser. The page shows the
English source plus two anonymized versions per case, collects a forced-choice
singability pick and 1-5 MOS ratings, and exports one CSV per rater. Cases are
shown in a fixed order (sheet order) so all raters see the same sequence.

Usage:
    uv run scripts/build_eval_html.py
"""

import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SHEET = REPO / "data/human_eval/human_eval_sheet.csv"
OUT = REPO / "data/human_eval/eval.html"


def main():
    with open(SHEET, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    cases = [
        {
            "case": r["case"],
            "source": r["english_source"].split(" / "),
            "A": r["version_A"].split(" / "),
            "B": r["version_B"].split(" / "),
        }
        for r in rows
    ]
    html = TEMPLATE.replace("__CASES__", json.dumps(cases, ensure_ascii=False))
    OUT.write_text(html, encoding="utf-8")
    print(f"Wrote {len(cases)} cases to {OUT}")
    print("Each rater: open this file in a browser, fill all items, click Export.")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Singability Blind Evaluation</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 760px; margin: 24px auto;
         padding: 0 16px; line-height: 1.6; color: #1a1a1a; }
  h1 { font-size: 20px; }
  .src { background: #f4f4f6; padding: 12px 14px; border-radius: 8px;
         font-style: italic; color: #444; }
  .ver { border: 1px solid #ddd; border-radius: 8px; padding: 12px 14px; margin: 10px 0; }
  .ver h3 { margin: 0 0 6px; }
  .line { margin: 2px 0; }
  .q { margin: 14px 0; }
  .q label { margin-right: 14px; cursor: pointer; }
  .scale label { margin-right: 10px; }
  .nav { display: flex; justify-content: space-between; margin-top: 20px; }
  button { font-size: 15px; padding: 8px 16px; border-radius: 6px; border: 1px solid #888;
           background: #fff; cursor: pointer; }
  button.primary { background: #2b6cb0; color: #fff; border-color: #2b6cb0; }
  button:disabled { opacity: .4; cursor: not-allowed; }
  .progress { color: #666; font-size: 14px; }
  .hidden { display: none; }
  fieldset { border: 1px solid #e0e0e0; border-radius: 8px; margin: 12px 0; }
  legend { font-weight: 600; padding: 0 6px; }
  .def { background: #eef4fb; border-left: 4px solid #2b6cb0; border-radius: 6px;
         padding: 10px 14px; margin: 12px 0; font-size: 14px; }
  .warn { color: #c0392b; font-size: 14px; min-height: 18px; }
</style>
</head>
<body>
<div id="intro">
  <h1>Singable Lyrics: Blind A/B Evaluation</h1>
  <p>You will see an English source and two anonymized Chinese versions (A and B).
     Imagine both sung to the original melody (same number of notes). For each case:</p>
  <div class="def">
    <b>What does &ldquo;singable&rdquo; mean?</b> A translation is <b>singable</b> when it can be
    sung naturally to the original melody. Concretely: (1) its syllable count matches the
    melody&rsquo;s notes, so one syllable lands on one note without cramming or stretching;
    (2) word stress and phrasing fall on the natural musical beats; and (3) it still reads as
    fluent, idiomatic Chinese. Judge it by mentally singing it to the tune, not just by reading.
  </div>
  <ul>
    <li>Pick the <b>more singable</b> version (A or B).</li>
    <li>Rate each version 1-5 on <b>singability</b> (fits the melody),
        <b>naturalness</b> (reads as fluent Chinese), and <b>meaning</b>
        (keeps the sense and feeling of the English).</li>
  </ul>
  <p>Your name (used only in the exported filename):
     <input id="rater" type="text" placeholder="rater id (e.g. r1)"></p>
  <button class="primary" onclick="start()">Start</button>
</div>

<div id="task" class="hidden">
  <div class="progress" id="progress"></div>
  <h1 id="caseId"></h1>
  <p><b>English source</b></p>
  <div class="src" id="src"></div>
  <div class="ver"><h3>Version A</h3><div id="verA"></div></div>
  <div class="ver"><h3>Version B</h3><div id="verB"></div></div>

  <fieldset>
    <legend>Which is more singable?</legend>
    <div class="q" id="pick"></div>
  </fieldset>
  <fieldset>
    <legend>MOS 1-5 (1 = poor, 5 = excellent)</legend>
    <div class="q scale" id="sa"></div>
    <div class="q scale" id="sb"></div>
    <div class="q scale" id="na"></div>
    <div class="q scale" id="nb"></div>
    <div class="q scale" id="ma"></div>
    <div class="q scale" id="mb"></div>
  </fieldset>

  <div class="warn" id="warn"></div>
  <div class="nav">
    <button onclick="prev()" id="prevBtn">&larr; Prev</button>
    <button class="primary" onclick="next()" id="nextBtn">Next &rarr;</button>
  </div>
</div>

<div id="done" class="hidden">
  <h1>All done, thank you!</h1>
  <p>Click below to download your responses, then send the CSV file back.</p>
  <button class="primary" onclick="exportCsv()">Export CSV</button>
</div>

<script>
const CASES = __CASES__;
let rater = "";
let i = 0;
const ans = CASES.map(() => ({pick:"", sa:"", sb:"", na:"", nb:"", ma:"", mb:""}));

function start() {
  rater = (document.getElementById("rater").value || "").trim();
  if (!rater) { alert("Please enter your name."); return; }
  document.getElementById("intro").classList.add("hidden");
  document.getElementById("task").classList.remove("hidden");
  render();
}

function radios(name, opts, current) {
  return opts.map(o =>
    `<label><input type="radio" name="${name}" value="${o.v}"
      ${current === o.v ? "checked" : ""}> ${o.t}</label>`).join("");
}

function render() {
  const c = CASES[i], a = ans[i];
  document.getElementById("progress").textContent = `Case ${i+1} / ${CASES.length}`;
  document.getElementById("caseId").textContent = c.case;
  document.getElementById("src").innerHTML = c.source.map(l => `<div class="line">${l}</div>`).join("");
  document.getElementById("verA").innerHTML = c.A.map(l => `<div class="line">${l}</div>`).join("");
  document.getElementById("verB").innerHTML = c.B.map(l => `<div class="line">${l}</div>`).join("");
  document.getElementById("pick").innerHTML =
    radios("pick", [{v:"A",t:"A"},{v:"B",t:"B"}], a.pick);
  const scale = [1,2,3,4,5].map(n => ({v:String(n), t:n}));
  document.getElementById("sa").innerHTML = "Singability A: " + radios("sa", scale, a.sa);
  document.getElementById("sb").innerHTML = "Singability B: " + radios("sb", scale, a.sb);
  document.getElementById("na").innerHTML = "Naturalness A: " + radios("na", scale, a.na);
  document.getElementById("nb").innerHTML = "Naturalness B: " + radios("nb", scale, a.nb);
  document.getElementById("ma").innerHTML = "Meaning A: " + radios("ma", scale, a.ma);
  document.getElementById("mb").innerHTML = "Meaning B: " + radios("mb", scale, a.mb);
  document.getElementById("prevBtn").disabled = (i === 0);
  document.getElementById("nextBtn").textContent =
    (i === CASES.length - 1) ? "Finish" : "Next →";
  document.getElementById("warn").textContent = "";
}

function collect() {
  const get = n => (document.querySelector(`input[name="${n}"]:checked`) || {}).value || "";
  ans[i] = {pick:get("pick"), sa:get("sa"), sb:get("sb"), na:get("na"), nb:get("nb"), ma:get("ma"), mb:get("mb")};
}

function complete(a) { return a.pick && a.sa && a.sb && a.na && a.nb && a.ma && a.mb; }

function prev() { collect(); if (i > 0) { i--; render(); } }

function next() {
  collect();
  if (!complete(ans[i])) {
    document.getElementById("warn").textContent = "Please answer all items before continuing.";
    return;
  }
  if (i < CASES.length - 1) { i++; render(); }
  else {
    document.getElementById("task").classList.add("hidden");
    document.getElementById("done").classList.remove("hidden");
  }
}

function exportCsv() {
  const head = ["rater","case","more_singable_A_or_B",
    "MOS_A_singability_1to5","MOS_B_singability_1to5",
    "MOS_A_naturalness_1to5","MOS_B_naturalness_1to5",
    "MOS_A_meaning_1to5","MOS_B_meaning_1to5"];
  const rows = [head.join(",")];
  CASES.forEach((c, k) => {
    const a = ans[k];
    rows.push([rater, c.case, a.pick, a.sa, a.sb, a.na, a.nb, a.ma, a.mb].join(","));
  });
  const blob = new Blob([rows.join("\n")], {type:"text/csv;charset=utf-8"});
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `responses_${rater.replace(/[^A-Za-z0-9_-]/g,"_")}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
