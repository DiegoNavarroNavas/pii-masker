#!/usr/bin/env python3
"""
Generate an HTML dashboard from benchmark JSON results.

The dashboard focuses on:
- false negatives by expected category
- false positives by predicted category
- misclassifications (same span text, wrong category)

Usage:
  python tests/generate_benchmark_error_dashboard.py \
    --input benchmarks/results/transformers/generated/small.json \
    --output benchmarks/error/dashboard.html
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_ROOT = REPO_ROOT / "benchmarks"

ALIAS_MAP = {
    "ORG": "ORGANIZATION",
    "PHONE": "PHONE_NUMBER",
}


def normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def canonical_label(label: str, alias_aware: bool) -> str:
    if not alias_aware:
        return label
    return ALIAS_MAP.get(label, label)


def split_by_key(
    records: list[dict[str, Any]],
    key_fn,
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in records:
        grouped[key_fn(item)].append(item)
    return grouped


def evaluate_model_errors(
    *,
    model_name: str,
    model_payload: dict[str, Any],
    cases_by_id: dict[str, dict[str, Any]],
    alias_aware: bool,
) -> dict[str, Any]:
    fn_records: list[dict[str, Any]] = []
    fp_records: list[dict[str, Any]] = []
    misclass_records: list[dict[str, Any]] = []

    for case_result in model_payload.get("results_by_case", []):
        case_id = case_result.get("case_id")
        case_info = cases_by_id.get(case_id, {})
        expected = case_info.get("expected", [])
        detections = case_result.get("detections", [])

        expected_rows = [
            {
                "text": e["text"],
                "text_norm": normalize_text(e["text"]),
                "entity_type_raw": e["entity_type"],
                "entity_type": canonical_label(e["entity_type"], alias_aware),
            }
            for e in expected
        ]
        detection_rows = [
            {
                "text": d["text"],
                "text_norm": normalize_text(d["text"]),
                "entity_type_raw": d["entity_type"],
                "entity_type": canonical_label(d["entity_type"], alias_aware),
                "score": float(d.get("score", 0.0)),
            }
            for d in detections
        ]

        # We match in phases to avoid double counting:
        # 1) exact text+label matches
        # 2) same-text mismatched-label matches (count ONLY as misclassification)
        # 3) leftovers -> FN / FP
        matched_expected: set[int] = set()
        matched_detection: set[int] = set()

        expected_by_key = split_by_key(
            [
                {"idx": idx, **item}
                for idx, item in enumerate(expected_rows)
            ],
            key_fn=lambda item: (item["text_norm"], item["entity_type"]),
        )
        detections_by_key = split_by_key(
            [
                {"idx": idx, **item}
                for idx, item in enumerate(detection_rows)
            ],
            key_fn=lambda item: (item["text_norm"], item["entity_type"]),
        )

        for key in set(expected_by_key) & set(detections_by_key):
            exp_items = expected_by_key[key]
            det_items = detections_by_key[key]
            take = min(len(exp_items), len(det_items))
            for i in range(take):
                matched_expected.add(exp_items[i]["idx"])
                matched_detection.add(det_items[i]["idx"])

        expected_by_text = split_by_key(
            [
                {"idx": idx, **item}
                for idx, item in enumerate(expected_rows)
                if idx not in matched_expected
            ],
            key_fn=lambda item: (item["text_norm"], ""),
        )
        detections_by_text = split_by_key(
            [
                {"idx": idx, **item}
                for idx, item in enumerate(detection_rows)
                if idx not in matched_detection
            ],
            key_fn=lambda item: (item["text_norm"], ""),
        )

        for text_key in set(expected_by_text) & set(detections_by_text):
            exp_items = expected_by_text[text_key]
            det_items = sorted(
                detections_by_text[text_key],
                key=lambda x: x["score"],
                reverse=True,
            )
            used_exp_local: set[int] = set()
            for det in det_items:
                det_type = det["entity_type"]
                candidate_exp = next(
                    (
                        exp
                        for exp in exp_items
                        if exp["idx"] not in used_exp_local and exp["entity_type"] != det_type
                    ),
                    None,
                )
                if candidate_exp is None:
                    continue
                used_exp_local.add(candidate_exp["idx"])
                matched_expected.add(candidate_exp["idx"])
                matched_detection.add(det["idx"])
                misclass_records.append(
                    {
                        "model": model_name,
                        "case_id": case_id,
                        "category": candidate_exp["entity_type"],
                        "text": det["text"],
                        "predicted_type": det["entity_type_raw"],
                        "expected_type": candidate_exp["entity_type_raw"],
                        "score": det["score"],
                        "pair": f"{det['entity_type_raw']} -> {candidate_exp['entity_type_raw']}",
                    }
                )

        for idx, exp in enumerate(expected_rows):
            if idx in matched_expected:
                continue
            fn_records.append(
                {
                    "model": model_name,
                    "case_id": case_id,
                    "category": exp["entity_type"],
                    "text": exp["text"],
                    "expected_type": exp["entity_type_raw"],
                }
            )

        for idx, det in enumerate(detection_rows):
            if idx in matched_detection:
                continue
            fp_records.append(
                {
                    "model": model_name,
                    "case_id": case_id,
                    "category": det["entity_type"],
                    "text": det["text"],
                    "predicted_type": det["entity_type_raw"],
                    "score": det["score"],
                }
            )

    fn_counts = Counter(item["category"] for item in fn_records)
    fp_counts = Counter(item["category"] for item in fp_records)
    misclass_counts = Counter(item["category"] for item in misclass_records)
    pair_counts = Counter(item["pair"] for item in misclass_records)
    categories = sorted(set(fn_counts) | set(fp_counts) | set(misclass_counts))

    return {
        "model": model_name,
        "engine": model_payload.get("engine", "unknown"),
        "ok": bool(model_payload.get("ok", False)),
        "summary": model_payload.get("summary", {}),
        "totals": {
            "fn": len(fn_records),
            "fp": len(fp_records),
            "misclass": len(misclass_records),
        },
        "counts": {
            "categories": categories,
            "fn": {k: fn_counts.get(k, 0) for k in categories},
            "fp": {k: fp_counts.get(k, 0) for k in categories},
            "misclass": {k: misclass_counts.get(k, 0) for k in categories},
            "pairs": dict(sorted(pair_counts.items(), key=lambda x: (-x[1], x[0]))),
        },
        "examples": {
            "fn": fn_records,
            "fp": fp_records,
            "misclass": misclass_records,
        },
    }


def make_html(payload: dict[str, Any]) -> str:
    data_json = json.dumps(payload, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Benchmark Error Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {{
      --bg: #0b1020;
      --panel: #131a31;
      --ink: #eef2ff;
      --muted: #a8b0cc;
      --grid: #2a3356;
      --fn: #ff7f50;
      --fp: #59c3c3;
      --mis: #f4d35e;
      --accent: #9ad1d4;
    }}
    body {{
      margin: 0;
      padding: 24px;
      background: var(--bg);
      color: var(--ink);
      font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
    }}
    h1, h2, h3 {{ margin: 0 0 10px 0; }}
    .muted {{ color: var(--muted); }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--grid);
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 16px;
    }}
    .row {{
      display: grid;
      grid-template-columns: repeat(3, minmax(220px, 1fr));
      gap: 12px;
    }}
    .stat {{
      background: #0f1530;
      border: 1px solid var(--grid);
      border-radius: 10px;
      padding: 10px;
    }}
    .stat .k {{ color: var(--muted); font-size: 12px; }}
    .stat .v {{ font-size: 22px; font-weight: 700; }}
    label {{ font-size: 13px; color: var(--muted); }}
    select, input[type=checkbox] {{
      margin-top: 6px;
      font-size: 13px;
    }}
    select {{
      width: 100%;
      background: #0f1530;
      color: var(--ink);
      border: 1px solid var(--grid);
      padding: 6px;
      border-radius: 8px;
    }}
    .toolbar {{
      display: grid;
      grid-template-columns: 2fr 1fr 1fr;
      gap: 12px;
      align-items: end;
    }}
    .grid2 {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }}
    .table-wrap {{
      max-height: 360px;
      overflow: auto;
      border: 1px solid var(--grid);
      border-radius: 8px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }}
    th, td {{
      border: 1px solid var(--grid);
      padding: 6px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      position: sticky;
      top: 0;
      background: #182147;
      z-index: 1;
    }}
    .pill {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      border: 1px solid var(--grid);
      background: #0f1530;
      font-size: 11px;
      color: var(--muted);
    }}
  </style>
</head>
<body>
  <h1>Benchmark Error Dashboard</h1>
  <p class="muted">Per-model false negatives, false positives, and misclassifications by category.</p>

  <div class="card toolbar">
    <div>
      <label for="modelSelect">Model</label>
      <select id="modelSelect"></select>
    </div>
    <div>
      <label for="aliasMode">Label mode</label><br />
      <select id="aliasMode">
        <option value="strict">Strict labels</option>
        <option value="alias">Alias-aware labels</option>
      </select>
    </div>
    <div>
      <span class="pill" id="enginePill">engine</span>
    </div>
  </div>

  <div class="card row">
    <div class="stat"><div class="k">False Negatives</div><div class="v" id="fnTotal">0</div></div>
    <div class="stat"><div class="k">False Positives</div><div class="v" id="fpTotal">0</div></div>
    <div class="stat"><div class="k">Misclassifications</div><div class="v" id="misTotal">0</div></div>
  </div>

  <div class="card row">
    <div class="stat"><div class="k">Avg Exact F1</div><div class="v" id="avgF1Exact">0.000</div></div>
    <div class="stat"><div class="k">Avg Exact F2</div><div class="v" id="avgF2Exact">0.000</div></div>
    <div class="stat"><div class="k">Avg Partial F1</div><div class="v" id="avgF1Partial">0.000</div></div>
  </div>
  <div class="card row">
    <div class="stat"><div class="k">Avg Partial F2</div><div class="v" id="avgF2Partial">0.000</div></div>
    <div class="stat"><div class="k">Avg Exact Precision</div><div class="v" id="avgPrecisionExact">0.000</div></div>
    <div class="stat"><div class="k">Avg Exact Recall</div><div class="v" id="avgRecallExact">0.000</div></div>
  </div>

  <div class="card grid2">
    <div>
      <h3>Errors By Category</h3>
      <canvas id="categoryChart"></canvas>
    </div>
    <div>
      <h3>Top Misclassification Pairs</h3>
      <canvas id="pairChart"></canvas>
    </div>
  </div>

  <div class="card">
    <h3>False Negatives (Expected Missed)</h3>
    <div class="table-wrap"><table id="fnTable"></table></div>
  </div>
  <div class="card">
    <h3>False Positives (Unexpected Detections)</h3>
    <div class="table-wrap"><table id="fpTable"></table></div>
  </div>
  <div class="card">
    <h3>Misclassifications (Same Text, Wrong Label)</h3>
    <div class="table-wrap"><table id="misTable"></table></div>
  </div>

  <script>
    const DATA = {data_json};
    const modelSelect = document.getElementById("modelSelect");
    const aliasMode = document.getElementById("aliasMode");
    const enginePill = document.getElementById("enginePill");

    for (const modelName of Object.keys(DATA.models.strict)) {{
      const option = document.createElement("option");
      option.value = modelName;
      option.textContent = modelName;
      modelSelect.appendChild(option);
    }}

    let categoryChart = null;
    let pairChart = null;

    function escapeHtml(text) {{
      return String(text)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }}

    function renderTable(tableId, headers, rows) {{
      const table = document.getElementById(tableId);
      let html = "<tr>" + headers.map(h => `<th>${{escapeHtml(h)}}</th>`).join("") + "</tr>";
      for (const row of rows) {{
        html += "<tr>" + row.map(col => `<td>${{escapeHtml(col)}}</td>`).join("") + "</tr>";
      }}
      table.innerHTML = html;
    }}

    function getActiveModelData() {{
      const mode = aliasMode.value;
      const model = modelSelect.value;
      return DATA.models[mode][model];
    }}

    function renderCharts(modelData) {{
      const categories = modelData.counts.categories;
      const fn = categories.map(k => modelData.counts.fn[k] || 0);
      const fp = categories.map(k => modelData.counts.fp[k] || 0);
      const mis = categories.map(k => modelData.counts.misclass[k] || 0);

      if (categoryChart) categoryChart.destroy();
      categoryChart = new Chart(document.getElementById("categoryChart"), {{
        type: "bar",
        data: {{
          labels: categories,
          datasets: [
            {{ label: "FN", data: fn, backgroundColor: "#ff7f50" }},
            {{ label: "FP", data: fp, backgroundColor: "#59c3c3" }},
            {{ label: "Misclass", data: mis, backgroundColor: "#f4d35e" }},
          ],
        }},
        options: {{
          responsive: true,
          plugins: {{ legend: {{ labels: {{ color: "#eef2ff" }} }} }},
          scales: {{
            x: {{ ticks: {{ color: "#eef2ff" }}, grid: {{ color: "#2a3356" }} }},
            y: {{ beginAtZero: true, ticks: {{ color: "#eef2ff" }}, grid: {{ color: "#2a3356" }} }},
          }},
        }},
      }});

      const pairs = Object.entries(modelData.counts.pairs).slice(0, 12);
      if (pairChart) pairChart.destroy();
      pairChart = new Chart(document.getElementById("pairChart"), {{
        type: "bar",
        data: {{
          labels: pairs.map(p => p[0]),
          datasets: [{{ label: "Count", data: pairs.map(p => p[1]), backgroundColor: "#9ad1d4" }}],
        }},
        options: {{
          indexAxis: "y",
          responsive: true,
          plugins: {{ legend: {{ labels: {{ color: "#eef2ff" }} }} }},
          scales: {{
            x: {{ beginAtZero: true, ticks: {{ color: "#eef2ff" }}, grid: {{ color: "#2a3356" }} }},
            y: {{ ticks: {{ color: "#eef2ff" }}, grid: {{ color: "#2a3356" }} }},
          }},
        }},
      }});
    }}

    function render() {{
      const modelData = getActiveModelData();
      document.getElementById("fnTotal").textContent = modelData.totals.fn;
      document.getElementById("fpTotal").textContent = modelData.totals.fp;
      document.getElementById("misTotal").textContent = modelData.totals.misclass;
      const s = modelData.summary || {{}};
      document.getElementById("avgF1Exact").textContent = Number(s.avg_f1_exact || 0).toFixed(3);
      document.getElementById("avgF2Exact").textContent = Number(s.avg_f2_exact || 0).toFixed(3);
      document.getElementById("avgF1Partial").textContent = Number(s.avg_f1_partial || 0).toFixed(3);
      document.getElementById("avgF2Partial").textContent = Number(s.avg_f2_partial || 0).toFixed(3);
      document.getElementById("avgPrecisionExact").textContent = Number(s.avg_precision_exact || 0).toFixed(3);
      document.getElementById("avgRecallExact").textContent = Number(s.avg_recall_exact || 0).toFixed(3);
      enginePill.textContent = modelData.engine;

      renderCharts(modelData);

      renderTable(
        "fnTable",
        ["Category", "Case", "Expected text", "Expected label"],
        modelData.examples.fn.map(x => [x.category, x.case_id, x.text, x.expected_type]),
      );

      renderTable(
        "fpTable",
        ["Category", "Case", "Detected text", "Predicted label", "Score"],
        modelData.examples.fp.map(x => [x.category, x.case_id, x.text, x.predicted_type, x.score.toFixed(4)]),
      );

      renderTable(
        "misTable",
        ["Category", "Case", "Text", "Predicted", "Expected", "Pair", "Score"],
        modelData.examples.misclass.map(x => [
          x.category,
          x.case_id,
          x.text,
          x.predicted_type,
          x.expected_type,
          x.pair,
          x.score.toFixed(4),
        ]),
      );
    }}

    modelSelect.addEventListener("change", render);
    aliasMode.addEventListener("change", render);
    render();
  </script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate benchmark error dashboard HTML.")
    parser.add_argument(
        "--input",
        type=str,
        default=str(BENCHMARK_ROOT / "results" / "transformers" / "generated" / "small.json"),
        help="Path to benchmark JSON results file.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(BENCHMARK_ROOT / "error" / "dashboard.html"),
        help="Path to output HTML dashboard.",
    )
    args = parser.parse_args()

    source = Path(args.input)
    payload = json.loads(source.read_text(encoding="utf-8"))
    cases_by_id = {item["case_id"]: item for item in payload.get("cases", [])}

    models_strict: dict[str, Any] = {}
    models_alias: dict[str, Any] = {}
    for model_name, model_payload in payload.get("models", {}).items():
        if not model_payload.get("ok"):
            continue
        models_strict[model_name] = evaluate_model_errors(
            model_name=model_name,
            model_payload=model_payload,
            cases_by_id=cases_by_id,
            alias_aware=False,
        )
        models_alias[model_name] = evaluate_model_errors(
            model_name=model_name,
            model_payload=model_payload,
            cases_by_id=cases_by_id,
            alias_aware=True,
        )

    dashboard_payload = {
        "generated_from": str(source),
        "models": {
            "strict": models_strict,
            "alias": models_alias,
        },
    }

    html = make_html(dashboard_payload)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    print(f"Wrote dashboard: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

