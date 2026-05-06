from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple

from .utils import escape_html, write_json


def write_artifacts(result: Dict[str, Any], out_dir: Path, formats: Sequence[str], json_only: bool = False) -> Dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts: Dict[str, Path] = {}
    public_result = {key: value for key, value in result.items() if key != "_artifacts"}

    diff_json = out_dir / "diff.json"
    write_json(diff_json, public_result)
    artifacts["diff_json"] = diff_json

    graph_json = out_dir / "change_graph.json"
    write_json(graph_json, result["change_impact_dag"])
    artifacts["change_graph_json"] = graph_json

    diagnostics_json = out_dir / "diagnostics.json"
    write_json(diagnostics_json, {"diagnostics": result["diagnostics"]})
    artifacts["diagnostics_json"] = diagnostics_json

    llm_summary_json = out_dir / "llm_summary.json"
    write_json(llm_summary_json, result["llm_summary"])
    artifacts["llm_summary_json"] = llm_summary_json

    llm_summary_md = out_dir / "llm_summary.md"
    llm_summary_md.write_text(render_llm_summary_markdown(result["llm_summary"]), encoding="utf-8")
    artifacts["llm_summary_md"] = llm_summary_md

    csv_path = out_dir / "changed_cells.csv"
    _write_changed_cells_csv(csv_path, result["changes"])
    artifacts["changed_cells_csv"] = csv_path

    dot_path = out_dir / "graph.dot"
    dot_path.write_text(render_dot(result["change_impact_dag"]), encoding="utf-8")
    artifacts["graph_dot"] = dot_path

    if not json_only and "md" in formats:
        md_path = out_dir / "diff_report.md"
        md_path.write_text(render_markdown(result), encoding="utf-8")
        artifacts["markdown"] = md_path

    if not json_only and "html" in formats:
        html_path = out_dir / "diff_report.html"
        html_path.write_text(render_html(result), encoding="utf-8")
        artifacts["html"] = html_path

    return artifacts


def render_markdown(result: Dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Workbook Diff Report",
        "",
        "Compared:",
        f"- Baseline: `{result['baseline']['filename']}` `{result['baseline']['sha256'][:12]}`",
        f"- Candidate: `{result['candidate']['filename']}` `{result['candidate']['sha256'][:12]}`",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        f"- Overall confidence: **{summary['confidence']}**",
        "",
        "## Executive summary",
        "",
        f"1. {summary['one_sentence_summary']}",
        f"2. Formula changes: **{summary['formulas_changed']}**.",
        f"3. Outputs changed: **{summary['outputs_changed']}**.",
        f"4. Unexplained changes: **{summary['unexplained_change_count']}**.",
    ]

    if result["top_direct_changes"]:
        lines.extend(["", "## Top direct changes", "", "| Type | Location | Label | Old | New | Delta |", "|---|---|---|---:|---:|---:|"])
        for change in result["top_direct_changes"][:15]:
            lines.append(
                "| {kind} | `{ref}` | {label} | {old} | {new} | {delta} |".format(
                    kind=change["kind"],
                    ref=change["object_ref"],
                    label=_md(_label(change)),
                    old=_md(change.get("old_display", "")),
                    new=_md(change.get("new_display", "")),
                    delta=_md(_delta_display(change)),
                )
            )

    shifted_matches = result.get("structural_alignment", {}).get("shifted_matches", [])
    if shifted_matches:
        lines.extend(["", "## Structural alignment", ""])
        summary = result.get("structural_alignment", {}).get("summary", {})
        lines.append(
            f"Semantic row/column matching aligned {summary.get('shifted_semantic_matches', len(shifted_matches))} shifted cell(s) before diffing."
        )
        lines.extend(["", "| Old location | New location | Matched by |", "|---|---|---|"])
        for match in shifted_matches[:20]:
            lines.append(f"| `{match['old_ref']}` | `{match['new_ref']}` | {match.get('matched_by', '')} |")

    if result["top_impacted_outputs"]:
        lines.extend(
            [
                "",
                "## Top impacted outputs",
                "",
                "| Output | Location | Old | New | Delta | Explanation strength | Likely upstream changes | Caveats |",
                "|---|---|---:|---:|---:|---|---|---|",
            ]
        )
        changes_by_id = {change["id"]: change for change in result["changes"]}
        for output in result["top_impacted_outputs"][:15]:
            upstream = ", ".join(
                f"`{changes_by_id[item]['object_ref']}`" for item in output.get("upstream_change_ids", []) if item in changes_by_id
            )
            lines.append(
                "| {label} | `{ref}` | {old} | {new} | {delta} | {strength} | {upstream} | {caveats} |".format(
                    label=_md(output["label"]),
                    ref=output["ref"],
                    old=_md((output.get("old_value") or {}).get("display_value", "")),
                    new=_md((output.get("new_value") or {}).get("display_value", "")),
                    delta=_md(_delta_display(output)),
                    strength=output["explanation_strength"],
                    upstream=upstream or "none detected",
                    caveats=_md(_confidence_factor_display(output)),
                )
            )

    if result["change_impact_dag"]["edges"]:
        lines.extend(["", "## Change DAG", ""])
        for edge in result["change_impact_dag"]["edges"][:40]:
            lines.append(f"- `{edge['from']}` -> `{edge['to']}` ({edge['edge_type']})")

    if result["unexplained_changes"]:
        lines.extend(["", "## Unexplained changes", ""])
        lines.append("These values changed, but the engine could not connect them to a detected upstream change.")
        for change in result["unexplained_changes"][:15]:
            lines.append(f"- `{change['object_ref']}` {_label(change)}: {change.get('old_display', '')} -> {change.get('new_display', '')}")

    if result["diagnostics"]:
        lines.extend(["", "## Diagnostics", ""])
        for diagnostic in result["diagnostics"][:40]:
            ref = f" `{diagnostic['object_ref']}`" if diagnostic.get("object_ref") else ""
            lines.append(f"- **{diagnostic['code']}**{ref}: {diagnostic['message']}")

    return "\n".join(lines) + "\n"


def render_llm_summary_markdown(llm_summary: Dict[str, Any]) -> str:
    lines = [
        "# LLM Workbook Diff Summary",
        "",
        "## One Sentence",
        "",
        llm_summary["one_sentence_summary"],
        "",
        "## Counts",
        "",
    ]
    for key, value in llm_summary.get("counts", {}).items():
        lines.append(f"- {key}: {value}")
    if llm_summary.get("top_direct_changes"):
        lines.extend(["", "## Top Direct Changes", ""])
        for change in llm_summary["top_direct_changes"]:
            lines.append(f"- `{change['ref']}` {change.get('label') or ''}: {change.get('old') or ''} -> {change.get('new') or ''} {change.get('delta') or ''}".rstrip())
    if llm_summary.get("top_change_groups"):
        lines.extend(["", "## Top Change Groups", ""])
        for group in llm_summary["top_change_groups"]:
            lines.append(f"- {group.get('label') or group.get('group_type')}: {group.get('summary') or ''}".rstrip())
    if llm_summary.get("top_impacted_outputs"):
        lines.extend(["", "## Top Impacted Outputs", ""])
        for output in llm_summary["top_impacted_outputs"]:
            lines.append(
                f"- `{output['ref']}` {output.get('label') or ''}: {output.get('old') or ''} -> {output.get('new') or ''} "
                f"{output.get('delta') or ''}; strength={output.get('explanation_strength')}"
            )
    if llm_summary.get("caveats"):
        lines.extend(["", "## Caveats", ""])
        lines.extend(f"- {caveat}" for caveat in llm_summary["caveats"])
    return "\n".join(lines) + "\n"


def render_html(result: Dict[str, Any]) -> str:
    summary = result["summary"]
    graph_html = render_focused_graph_html(result)
    cards = [
        ("Direct changes", summary["direct_change_count"]),
        ("Formula changes", summary["formulas_changed"]),
        ("Outputs changed", summary["outputs_changed"]),
        ("Unexplained", summary["unexplained_change_count"]),
        ("Shifted cells", summary.get("shifted_semantic_matches", 0)),
        ("Opaque formulas", "yes" if summary["has_opaque_formulas"] else "no"),
        ("Macros or links", "yes" if summary["has_macros"] or summary["has_external_links"] else "no"),
    ]
    card_html = "".join(f"<div class='card'><div>{escape_html(label)}</div><strong>{escape_html(value)}</strong></div>" for label, value in cards)
    direct_rows = "".join(
        "<tr><td>{kind}</td><td><code>{ref}</code></td><td>{label}</td><td>{old}</td><td>{new}</td><td>{delta}</td></tr>".format(
            kind=escape_html(change["kind"]),
            ref=escape_html(change["object_ref"]),
            label=escape_html(_label(change)),
            old=escape_html(change.get("old_display", "")),
            new=escape_html(change.get("new_display", "")),
            delta=escape_html(_delta_display(change)),
        )
        for change in result["top_direct_changes"][:50]
    )
    output_rows = "".join(
        "<tr><td>{label}</td><td><code>{ref}</code></td><td>{old}</td><td>{new}</td><td>{delta}</td><td>{strength}</td><td>{explanation}</td><td>{caveats}</td></tr>".format(
            label=escape_html(output["label"]),
            ref=escape_html(output["ref"]),
            old=escape_html((output.get("old_value") or {}).get("display_value", "")),
            new=escape_html((output.get("new_value") or {}).get("display_value", "")),
            delta=escape_html(_delta_display(output)),
            strength=escape_html(output["explanation_strength"]),
            explanation=escape_html(output["explanation"]),
            caveats=escape_html(_confidence_factor_display(output)),
        )
        for output in result["top_impacted_outputs"][:50]
    )
    unexplained_items = "".join(
        f"<li><code>{escape_html(change['object_ref'])}</code> {escape_html(_label(change))}: {escape_html(change.get('old_display', ''))} -> {escape_html(change.get('new_display', ''))}</li>"
        for change in result["unexplained_changes"][:50]
    )
    diagnostics_items = "".join(
        "<li><strong>{code}</strong>{ref}: {message}</li>".format(
            code=escape_html(diagnostic["code"]),
            ref=f" <code>{escape_html(diagnostic['object_ref'])}</code>" if diagnostic.get("object_ref") else "",
            message=escape_html(diagnostic["message"]),
        )
        for diagnostic in result["diagnostics"][:80]
    )
    shifted_rows = "".join(
        "<tr><td><code>{old}</code></td><td><code>{new}</code></td><td>{by}</td><td>{confidence}</td></tr>".format(
            old=escape_html(match.get("old_ref", "")),
            new=escape_html(match.get("new_ref", "")),
            by=escape_html(match.get("matched_by", "")),
            confidence=escape_html(match.get("confidence", "")),
        )
        for match in result.get("structural_alignment", {}).get("shifted_matches", [])[:50]
    )
    structural_section = ""
    if shifted_rows:
        structural_section = (
            "<section><h2>Structural Alignment</h2>"
            "<p>Semantic row/column labels were used to align shifted cells before diffing.</p>"
            "<table><thead><tr><th>Old location</th><th>New location</th><th>Matched by</th><th>Confidence</th></tr></thead>"
            f"<tbody>{shifted_rows}</tbody></table></section>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Workbook Diff Report</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1f2933;
      --muted: #5b6776;
      --line: #d7dde5;
      --panel: #f7f9fb;
      --accent: #0f766e;
      --warn: #9a3412;
    }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: #ffffff;
      line-height: 1.45;
    }}
    header, main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 28px;
    }}
    header {{
      border-bottom: 1px solid var(--line);
    }}
    h1, h2 {{
      margin: 0 0 12px;
      letter-spacing: 0;
    }}
    .meta {{
      color: var(--muted);
      display: grid;
      gap: 4px;
      font-size: 14px;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
      margin: 20px 0 28px;
    }}
    .card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: var(--panel);
      color: var(--muted);
    }}
    .card strong {{
      display: block;
      color: var(--ink);
      font-size: 26px;
      margin-top: 4px;
    }}
    section {{
      margin: 30px 0;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 9px 8px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      font-weight: 600;
      background: #fbfcfd;
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.92em;
      background: #eef2f6;
      border-radius: 4px;
      padding: 1px 4px;
    }}
    ul {{
      padding-left: 20px;
    }}
    .summary {{
      font-size: 17px;
      border-left: 4px solid var(--accent);
      padding-left: 14px;
    }}
    .warn {{
      color: var(--warn);
    }}
    .graph-panel {{
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfd;
      padding: 14px;
    }}
    .graph-caption {{
      color: var(--muted);
      font-size: 13px;
      margin: 8px 0 0;
    }}
    .graph-node text {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 11px;
      fill: #172033;
    }}
    .graph-node .ref {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 10px;
      fill: #475569;
    }}
    .graph-node {{
      cursor: pointer;
    }}
    .graph-node:hover rect,
    .graph-node:focus rect {{
      filter: drop-shadow(0 2px 4px rgb(15 23 42 / 0.18));
    }}
    .graph-node .value {{
      font-size: 10px;
      fill: #334155;
    }}
    .graph-node .delta {{
      font-size: 10px;
      font-weight: 700;
      fill: #0f766e;
    }}
    .graph-detail-list {{
      display: grid;
      gap: 8px;
      margin-top: 12px;
    }}
    .graph-detail-list details {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 8px 10px;
    }}
    .graph-detail-list summary {{
      cursor: pointer;
      font-weight: 600;
    }}
    .path-line {{
      color: var(--muted);
      font-size: 13px;
      margin: 8px 0 0;
    }}
    .graph-legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px 14px;
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 10px;
    }}
    .legend-dot {{
      display: inline-block;
      width: 10px;
      height: 10px;
      border-radius: 999px;
      margin-right: 5px;
      vertical-align: -1px;
    }}
  </style>
  <script>
    function toggleGraphDetail(id) {{
      var el = document.getElementById(id);
      if (!el) return;
      el.open = !el.open;
      el.scrollIntoView({{ block: "nearest", behavior: "smooth" }});
    }}
  </script>
</head>
<body>
  <header>
    <h1>Workbook Diff Report</h1>
    <div class="meta">
      <div>Baseline: <code>{escape_html(result['baseline']['filename'])}</code> {escape_html(result['baseline']['sha256'][:12])}</div>
      <div>Candidate: <code>{escape_html(result['candidate']['filename'])}</code> {escape_html(result['candidate']['sha256'][:12])}</div>
      <div>Generated: {escape_html(datetime.now(timezone.utc).isoformat())}</div>
      <div>Overall confidence: <strong>{escape_html(summary['confidence'])}</strong></div>
    </div>
  </header>
  <main>
    <section>
      <div class="cards">{card_html}</div>
      <p class="summary">{escape_html(summary['one_sentence_summary'])}</p>
    </section>
    <section>
      <h2>Direct Changes</h2>
      <table><thead><tr><th>Type</th><th>Location</th><th>Label</th><th>Old</th><th>New</th><th>Delta</th></tr></thead><tbody>{direct_rows}</tbody></table>
    </section>
    {structural_section}
    <section>
      <h2>Impacted Outputs</h2>
      <table><thead><tr><th>Output</th><th>Location</th><th>Old</th><th>New</th><th>Delta</th><th>Strength</th><th>Explanation</th><th>Caveats</th></tr></thead><tbody>{output_rows}</tbody></table>
    </section>
    <section>
      <h2>Change DAG</h2>
      <div class="graph-panel">{graph_html}</div>
      <p class="graph-caption">Intermediate cells are collapsed. Click an output card to see representative dependency paths and upstream changes.</p>
    </section>
    <section>
      <h2>Unexplained Changes</h2>
      <p>These values changed, but the engine could not connect them to a detected upstream change.</p>
      <ul>{unexplained_items}</ul>
    </section>
    <section>
      <h2>Diagnostics</h2>
      <ul>{diagnostics_items}</ul>
    </section>
  </main>
</body>
</html>
"""


def render_dot(dag: Dict[str, Any]) -> str:
    lines = ["digraph WorkbookDiff {", "  rankdir=LR;", "  node [shape=box, style=rounded];"]
    for node_id, node in dag.get("nodes", {}).items():
        label = node.get("label") or node.get("ref") or node_id
        role = node.get("semantic_role", "unknown")
        color = {
            "assumption": "#0f766e",
            "output": "#b91c1c",
            "intermediate_calculation": "#1d4ed8",
            "raw_data": "#7c2d12",
        }.get(role, "#4b5563")
        lines.append(f'  "{_dot_escape(node_id)}" [label="{_dot_escape(label)}\\n{_dot_escape(node.get("ref", node_id))}", color="{color}"];')
    for edge in dag.get("edges", []):
        label = edge.get("evidence") or edge.get("edge_type", "")
        lines.append(f'  "{_dot_escape(edge["from"])}" -> "{_dot_escape(edge["to"])}" [label="{_dot_escape(label)}"];')
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_focused_graph_html(result: Dict[str, Any], max_roots: int = 7, max_outputs: int = 5) -> str:
    llm_summary = result.get("llm_summary", {})
    roots = list(llm_summary.get("top_direct_changes", []))[:max_roots]
    outputs = list(llm_summary.get("top_impacted_outputs", []))[:max_outputs]
    if not roots and not outputs:
        return "<div>No material change-impact graph to display.</div>"

    changes_by_id = {change.get("id"): change for change in result.get("changes", [])}
    root_by_id = {root.get("id"): root for root in roots}
    output_cards = [_focused_output_card(output, index, root_by_id, changes_by_id) for index, output in enumerate(outputs)]
    root_cards = [_focused_root_card(root, index) for index, root in enumerate(roots)]
    svg = _render_focused_graph_svg(root_cards, output_cards)
    details = _render_focused_graph_details(output_cards, changes_by_id)
    legend = """
      <div class="graph-legend">
        <span><span class="legend-dot" style="background:#0f766e"></span>Direct change</span>
        <span><span class="legend-dot" style="background:#dc2626"></span>Final/output variable</span>
        <span>Lines are collapsed dependency paths, not individual cell-by-cell edges.</span>
      </div>
    """
    return legend + svg + details


def _focused_root_card(root: Dict[str, Any], index: int) -> Dict[str, Any]:
    label = root.get("label") or root.get("ref") or "Direct change"
    value = _old_new_text(root.get("old"), root.get("new"))
    return {
        "id": root.get("id") or f"root_{index}",
        "ref": root.get("ref") or "",
        "label": label,
        "value": value,
        "delta": root.get("delta") or "",
        "role": root.get("semantic_role") or "direct",
        "index": index,
    }


def _focused_output_card(
    output: Dict[str, Any],
    index: int,
    root_by_id: Dict[str, Dict[str, Any]],
    changes_by_id: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    upstream_ids = [item for item in output.get("upstream_change_ids", []) if item in changes_by_id]
    visible_root_ids = [item for item in upstream_ids if item in root_by_id][:3]
    if not visible_root_ids and upstream_ids:
        visible_root_ids = upstream_ids[:1]
    hidden_count = max(0, len(set(upstream_ids)) - len(set(visible_root_ids)))
    return {
        "id": f"output_{index}",
        "ref": output.get("ref") or "",
        "label": output.get("label") or output.get("ref") or "Output",
        "value": _old_new_text(output.get("old"), output.get("new")),
        "delta": output.get("delta") or "",
        "strength": output.get("explanation_strength") or "unknown",
        "visible_root_ids": visible_root_ids,
        "upstream_ids": upstream_ids,
        "hidden_count": hidden_count,
        "paths": output.get("representative_paths", []),
        "explanation": output.get("explanation") or "",
        "detail_id": f"graph-detail-{index}",
    }


def _render_focused_graph_svg(roots: Sequence[Dict[str, Any]], outputs: Sequence[Dict[str, Any]]) -> str:
    node_w = 310
    mid_w = 240
    node_h = 84
    row_gap = 18
    margin_x = 28
    margin_y = 34
    col_gap = 90
    root_x = margin_x
    mid_x = margin_x + node_w + col_gap
    output_x = mid_x + mid_w + col_gap
    row_count = max(len(roots), len(outputs), 1)
    height = margin_y * 2 + row_count * node_h + max(0, row_count - 1) * row_gap
    width = output_x + node_w + margin_x
    mid_h = 96
    mid_y = margin_y + max(0, (height - margin_y * 2 - mid_h) / 2)

    root_positions = {}
    output_positions = {}
    for index, root in enumerate(roots):
        root_positions[root["id"]] = (root_x, margin_y + index * (node_h + row_gap))
    for index, output in enumerate(outputs):
        output_positions[output["id"]] = (output_x, margin_y + index * (node_h + row_gap))

    edge_svg = []
    mid_left = mid_x
    mid_right = mid_x + mid_w
    mid_center_y = mid_y + mid_h / 2
    for root in roots:
        rx, ry = root_positions[root["id"]]
        edge_svg.append(
            _focused_edge_path(rx + node_w, ry + node_h / 2, mid_left, mid_center_y, "#94a3b8")
        )
    for output in outputs:
        ox, oy = output_positions[output["id"]]
        edge_svg.append(
            _focused_edge_path(mid_right, mid_center_y, ox, oy + node_h / 2, "#94a3b8")
        )

    node_svg = []
    for root in roots:
        x, y = root_positions[root["id"]]
        node_svg.append(
            _focused_node_svg(
                x,
                y,
                node_w,
                node_h,
                title="Direct change",
                ref=root["ref"],
                label=root["label"],
                value=root["value"],
                delta=root["delta"],
                fill="#ecfdf5",
                stroke="#0f766e",
            )
        )
    node_svg.append(
        _focused_node_svg(
            mid_x,
            mid_y,
            mid_w,
            mid_h,
            title="Collapsed dependency paths",
            ref="Collapsed paths",
            label="Model logic",
            value="intermediate formulas hidden",
            delta="click outputs for paths",
            fill="#eff6ff",
            stroke="#2563eb",
        )
    )
    for output in outputs:
        x, y = output_positions[output["id"]]
        more = f"+{output['hidden_count']} more upstream" if output["hidden_count"] else output["strength"]
        node_svg.append(
            _focused_node_svg(
                x,
                y,
                node_w,
                node_h,
                title="Output",
                ref=output["ref"],
                label=output["label"],
                value=output["value"],
                delta=output["delta"] or more,
                fill="#fef2f2",
                stroke="#dc2626",
                onclick=f"toggleGraphDetail('{output['detail_id']}')",
            )
        )

    omitted = f'<text x="{margin_x}" y="{height - 10}" fill="#64748b" font-size="12">Intermediate cells are collapsed into the model-logic node; click outputs for representative paths.</text>'
    return (
        f'<svg role="img" aria-label="Focused change impact graph" viewBox="0 0 {width} {height}" width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth"><path d="M 0 0 L 8 4 L 0 8 z" fill="#94a3b8" /></marker></defs>'
        + "".join(edge_svg)
        + "".join(node_svg)
        + omitted
        + "</svg>"
    )


def _focused_edge_path(x1: float, y1: float, x2: float, y2: float, color: str) -> str:
    mid = max(24, (x2 - x1) / 2)
    return (
        f'<path d="M {x1:.1f} {y1:.1f} C {x1 + mid:.1f} {y1:.1f}, {x2 - mid:.1f} {y2:.1f}, {x2:.1f} {y2:.1f}" '
        f'stroke="{color}" stroke-width="1.5" fill="none" marker-end="url(#arrow)" />'
    )


def _focused_node_svg(
    x: float,
    y: float,
    width: int,
    height: int,
    title: str,
    ref: str,
    label: str,
    value: str,
    delta: str,
    fill: str,
    stroke: str,
    onclick: str = "",
) -> str:
    click_attrs = f' onclick="{escape_html(onclick)}" tabindex="0" role="button"' if onclick else ""
    return (
        f'<g class="graph-node"{click_attrs}>'
        f'<title>{escape_html(title)}: {escape_html(ref)} {escape_html(label)}</title>'
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width}" height="{height}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1.5" />'
        f'<text x="{x + 12:.1f}" y="{y + 20:.1f}" font-weight="700">{escape_html(_truncate(label, 34))}</text>'
        f'<text class="ref" x="{x + 12:.1f}" y="{y + 38:.1f}">{escape_html(_truncate(ref, 42))}</text>'
        f'<text class="value" x="{x + 12:.1f}" y="{y + 58:.1f}">{escape_html(_truncate(value, 44))}</text>'
        f'<text class="delta" x="{x + 12:.1f}" y="{y + 75:.1f}">{escape_html(_truncate(delta, 44))}</text>'
        f'</g>'
    )


def _render_focused_graph_details(outputs: Sequence[Dict[str, Any]], changes_by_id: Dict[str, Dict[str, Any]]) -> str:
    if not outputs:
        return ""
    items = []
    for output in outputs:
        upstream = []
        for change_id in output.get("upstream_ids", [])[:12]:
            change = changes_by_id.get(change_id)
            if not change:
                continue
            upstream.append(
                f'<li><code>{escape_html(change.get("object_ref", ""))}</code> {escape_html(_label(change))}: '
                f'{escape_html(change.get("old_display", ""))} → {escape_html(change.get("new_display", ""))} '
                f'{escape_html(_delta_display(change))}</li>'
            )
        paths = []
        for path in output.get("paths", [])[:5]:
            refs = " → ".join(f"<code>{escape_html(node)}</code>" for node in path.get("nodes", []))
            if refs:
                paths.append(f'<div class="path-line">{refs}</div>')
        items.append(
            f'<details id="{escape_html(output["detail_id"])}">'
            f'<summary><code>{escape_html(output["ref"])}</code> {escape_html(output["label"])}: {escape_html(output["value"])} {escape_html(output["delta"])}</summary>'
            f'<p>{escape_html(output["explanation"])}</p>'
            f'<div>{"".join(paths) or "<p>No representative path recorded.</p>"}</div>'
            f'<ul>{"".join(upstream) or "<li>No upstream direct changes recorded.</li>"}</ul>'
            f'</details>'
        )
    return '<div class="graph-detail-list">' + "".join(items) + "</div>"


def _old_new_text(old: Any, new: Any) -> str:
    old_text = "" if old is None else str(old)
    new_text = "" if new is None else str(new)
    if not old_text and not new_text:
        return ""
    return f"{old_text or 'blank'} → {new_text or 'blank'}"


def render_graph_svg(dag: Dict[str, Any], max_nodes: int = 80) -> str:
    nodes, edges, omitted = _graph_subset(dag, max_nodes=max_nodes)
    if not nodes:
        return "<div>No change-impact graph nodes to display.</div>"

    ranks = _graph_ranks(nodes, edges, dag.get("roots", []), dag.get("outputs", []))
    rank_items: Dict[int, List[str]] = {}
    for node_id, rank in ranks.items():
        rank_items.setdefault(rank, []).append(node_id)
    for items in rank_items.values():
        items.sort(key=lambda node_id: (_node_sort_key(nodes[node_id]), node_id))

    node_w = 220
    node_h = 58
    col_gap = 80
    row_gap = 24
    margin_x = 32
    margin_y = 42
    max_rank = max(rank_items)
    max_rows = max(len(items) for items in rank_items.values())
    width = max(760, margin_x * 2 + (max_rank + 1) * node_w + max_rank * col_gap)
    height = max(300, margin_y * 2 + max_rows * node_h + (max_rows - 1) * row_gap)

    positions: Dict[str, tuple] = {}
    for rank, items in rank_items.items():
        column_height = len(items) * node_h + max(0, len(items) - 1) * row_gap
        start_y = margin_y + max(0, (height - margin_y * 2 - column_height) / 2)
        x = margin_x + rank * (node_w + col_gap)
        for index, node_id in enumerate(items):
            positions[node_id] = (x, start_y + index * (node_h + row_gap))

    svg_edges = []
    for edge in edges:
        if edge["from"] not in positions or edge["to"] not in positions:
            continue
        x1, y1 = positions[edge["from"]]
        x2, y2 = positions[edge["to"]]
        start_x = x1 + node_w
        start_y = y1 + node_h / 2
        end_x = x2
        end_y = y2 + node_h / 2
        mid = max(24, (end_x - start_x) / 2)
        svg_edges.append(
            f'<path d="M {start_x:.1f} {start_y:.1f} C {start_x + mid:.1f} {start_y:.1f}, {end_x - mid:.1f} {end_y:.1f}, {end_x:.1f} {end_y:.1f}" '
            f'stroke="#94a3b8" stroke-width="1.4" fill="none" marker-end="url(#arrow)" />'
        )

    svg_nodes = []
    for node_id, node in nodes.items():
        x, y = positions[node_id]
        role = node.get("semantic_role", "unknown")
        fill, stroke = _node_colors(role, bool(node.get("changes")))
        label = _truncate(node.get("label") or node.get("ref") or node_id, 28)
        ref = _truncate(node.get("ref") or node_id, 32)
        title = escape_html(f"{node.get('ref', node_id)} | {role}")
        svg_nodes.append(
            f'<g class="graph-node"><title>{title}</title>'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{node_w}" height="{node_h}" rx="7" fill="{fill}" stroke="{stroke}" stroke-width="1.4" />'
            f'<text x="{x + 12:.1f}" y="{y + 22:.1f}" font-weight="700">{escape_html(label)}</text>'
            f'<text class="ref" x="{x + 12:.1f}" y="{y + 42:.1f}">{escape_html(ref)}</text>'
            f'</g>'
        )

    caption = ""
    if omitted:
        caption = f'<text x="{margin_x}" y="{height - 12}" fill="#64748b" font-size="12">{omitted} additional graph node(s) omitted.</text>'
    return (
        f'<svg role="img" aria-label="Change impact graph" viewBox="0 0 {width:.0f} {height:.0f}" width="{width:.0f}" height="{height:.0f}" xmlns="http://www.w3.org/2000/svg">'
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth"><path d="M 0 0 L 8 4 L 0 8 z" fill="#94a3b8" /></marker></defs>'
        + "".join(svg_edges)
        + "".join(svg_nodes)
        + caption
        + "</svg>"
    )


def _graph_subset(dag: Dict[str, Any], max_nodes: int) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]], int]:
    all_nodes = dag.get("nodes", {})
    all_edges = dag.get("edges", [])
    if len(all_nodes) <= max_nodes:
        return dict(all_nodes), list(all_edges), 0

    selected: List[str] = []
    seen: Set[str] = set()

    def add(node_id: str) -> None:
        if node_id in all_nodes and node_id not in seen and len(selected) < max_nodes:
            seen.add(node_id)
            selected.append(node_id)

    for node_id in dag.get("roots", [])[:20]:
        add(node_id)
    for node_id in dag.get("outputs", [])[:20]:
        add(node_id)
    for edge in all_edges:
        if edge["from"] in seen or edge["to"] in seen:
            add(edge["from"])
            add(edge["to"])
        if len(selected) >= max_nodes:
            break
    for node_id, _node in sorted(all_nodes.items(), key=lambda item: (_node_sort_key(item[1]), item[0])):
        add(node_id)
        if len(selected) >= max_nodes:
            break

    selected_set = set(selected)
    nodes = {node_id: all_nodes[node_id] for node_id in selected}
    edges = [edge for edge in all_edges if edge["from"] in selected_set and edge["to"] in selected_set]
    return nodes, edges, max(0, len(all_nodes) - len(nodes))


def _graph_ranks(nodes: Dict[str, Dict[str, Any]], edges: Sequence[Dict[str, Any]], roots: Sequence[str], outputs: Sequence[str]) -> Dict[str, int]:
    adjacency: Dict[str, List[str]] = {}
    indegree = {node_id: 0 for node_id in nodes}
    for edge in edges:
        if edge["from"] not in nodes or edge["to"] not in nodes:
            continue
        adjacency.setdefault(edge["from"], []).append(edge["to"])
        indegree[edge["to"]] = indegree.get(edge["to"], 0) + 1
    start_nodes = [node_id for node_id in roots if node_id in nodes] or [node_id for node_id, degree in indegree.items() if degree == 0]
    ranks = {node_id: 0 for node_id in nodes}
    queue = list(start_nodes)
    visited = set(queue)
    while queue:
        node_id = queue.pop(0)
        for dependent in adjacency.get(node_id, []):
            ranks[dependent] = max(ranks.get(dependent, 0), ranks[node_id] + 1)
            if dependent not in visited:
                visited.add(dependent)
                queue.append(dependent)
    output_rank = min(max(ranks.values()) + 1, 5)
    for output in outputs:
        if output in ranks:
            ranks[output] = max(ranks[output], output_rank)
    for node_id, rank in list(ranks.items()):
        ranks[node_id] = min(rank, 5)
    return ranks


def _node_sort_key(node: Dict[str, Any]) -> Tuple[int, float, str]:
    role_order = {
        "assumption": 0,
        "raw_data": 1,
        "intermediate_calculation": 2,
        "output": 3,
        "unknown": 4,
        "metadata": 5,
    }
    return (role_order.get(node.get("semantic_role", "unknown"), 6), -float(node.get("materiality_score") or 0), node.get("ref", ""))


def _node_colors(role: str, changed: bool) -> Tuple[str, str]:
    colors = {
        "assumption": ("#ecfdf5", "#0f766e"),
        "raw_data": ("#fff7ed", "#c2410c"),
        "intermediate_calculation": ("#eff6ff", "#2563eb"),
        "output": ("#fef2f2", "#dc2626"),
        "metadata": ("#f8fafc", "#64748b"),
    }
    fill, stroke = colors.get(role, ("#f8fafc", "#64748b"))
    if changed:
        return fill, stroke
    return "#ffffff", stroke


def _truncate(value: Any, max_len: int) -> str:
    text = "" if value is None else str(value)
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def _write_changed_cells_csv(path: Path, changes: Sequence[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "id",
                "kind",
                "directness",
                "object_ref",
                "old_ref",
                "new_ref",
                "address_changed",
                "semantic_id",
                "sheet_name",
                "label",
                "semantic_role",
                "old_display",
                "new_display",
                "delta",
                "materiality_score",
                "confidence",
            ],
        )
        writer.writeheader()
        for change in changes:
            if change.get("scope") != "cell":
                continue
            writer.writerow(
                {
                    "id": change["id"],
                    "kind": change["kind"],
                    "directness": change["directness"],
                    "object_ref": change["object_ref"],
                    "old_ref": change.get("old_ref", ""),
                    "new_ref": change.get("new_ref", ""),
                    "address_changed": change.get("address_changed", ""),
                    "semantic_id": change.get("semantic_id", ""),
                    "sheet_name": change.get("sheet_name", ""),
                    "label": _label(change),
                    "semantic_role": change.get("semantic_role", ""),
                    "old_display": change.get("old_display", ""),
                    "new_display": change.get("new_display", ""),
                    "delta": _delta_display(change),
                    "materiality_score": change.get("materiality_score", ""),
                    "confidence": change.get("confidence", ""),
                }
            )


def _label(change: Dict[str, Any]) -> str:
    labels = change.get("labels", [])
    if not labels:
        return ""
    best = max(labels, key=lambda item: item.get("confidence", 0))
    return best.get("text", "")


def _delta_display(item: Dict[str, Any]) -> str:
    delta = item.get("delta")
    if not delta:
        return ""
    return delta.get("display_point_delta") or " / ".join(
        value for value in [delta.get("display_delta"), delta.get("display_relative_delta")] if value
    )


def _confidence_factor_display(item: Dict[str, Any]) -> str:
    factors = item.get("confidence_factors") or []
    return ", ".join(str(factor.get("code", "")) for factor in factors if factor.get("code"))


def _md(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _dot_escape(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
