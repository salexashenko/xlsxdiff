# xlsxdiff

`xlsxdiff` is a semantic diff engine for Excel workbooks. It compares two `.xlsx` or `.xlsm` files, identifies changed constants and formulas, follows formula dependencies to impacted outputs, and writes reports for both humans and LLM agents.

The tool is meant for spreadsheet review workflows where a plain cell-by-cell diff is too noisy: financial models, planning workbooks, operating dashboards, and generated Excel artifacts.

Before diffing cells, `xlsxdiff` infers semantic cell identities from defined names, row headers, and column headers. This lets it describe cells as intersections like `Anthropic ARR / 2027E` and align cells that moved because a row or column was inserted.

## Quick Start

```bash
pip install -e ".[dev]"
xlsxdiff old.xlsx new.xlsx --out diff_out
```

`workbook-diff` is also installed as a backwards-compatible CLI alias.

By default the output directory includes:

- `diff_report.html`: interactive human-readable report with a focused impact graph.
- `llm_summary.json`: compact structured summary for agents.
- `llm_summary.md`: Markdown summary for direct user responses.
- `diff.json`: full structured diff.
- `change_graph.json`: dependency graph and impact paths.
- `changed_cells.csv`: flat changed-cell table.
- `diagnostics.json`: parser and model caveats.
- `graph.dot`: Graphviz dependency graph.

## Python API

```python
from pathlib import Path

from workbook_diff import diff_workbooks, write_artifacts

result = diff_workbooks(Path("old.xlsx"), Path("new.xlsx"))
write_artifacts(result, Path("diff_out"), formats=["html", "json", "md"])

print(result["llm_summary"]["one_sentence_summary"])
```

Pass a YAML-backed config as a dictionary when the workbook has known output cells or domain-specific labels:

```python
result = diff_workbooks(
    Path("old.xlsx"),
    Path("new.xlsx"),
    config={
        "outputs": [
            {"ref": "Summary!G31", "name": "Total LTV"},
            {"ref": "Summary!B6", "name": "2027 supportable capex"},
        ]
    },
)
```

## LLM Usage

For agent workflows, read `llm_summary.json` or `result["llm_summary"]` instead of trying to summarize the full diff. The file is intentionally small and contains:

- `one_sentence_summary`: a ready-to-send summary sentence.
- `top_direct_changes`: the most important changed assumptions, formulas, inputs, or metadata.
- `top_change_groups`: grouped edits such as inserted or deleted modeling steps.
- `top_impacted_outputs`: ranked final variables with old value, new value, delta, and upstream change IDs.
- `caveats`: diagnostics that should temper the answer.

A good agent response pattern is: use `one_sentence_summary` when present, mention one or two `top_direct_changes` or `top_change_groups` if the user asks for detail, and surface `caveats` when the diff includes unexplained output changes or unsupported formula constructs.

## Example

The AI ARR/capex sample workbooks live under `examples/ai_arr_capex/workbooks`. The example runner imports the main library API and writes reports under `examples/ai_arr_capex/reports/diff_main`.

```bash
python examples/ai_arr_capex/run_diff.py
open examples/ai_arr_capex/reports/diff_main/diff_report.html
```

The optional scripts in `examples/ai_arr_capex/scripts` show how the sample workbooks were generated and verified. They use the Codex spreadsheet artifact runtime; the committed `.xlsx` workbooks do not require that runtime.

## Configuration

Configs are YAML mappings passed with `--config`.

```yaml
outputs:
  - ref: Summary!B6
    name: Combined supportable capex 2026E
  - ref: Summary!B7
    name: Combined supportable capex 2027E

semantic_roles:
  assumption_sheets:
    - Assumptions
  raw_data_sheets:
    - Raw Stripe Export
```

Configured outputs are prioritized in the HTML graph, Markdown report, and LLM summary.

## Semantic Alignment

Financial models often identify a cell by both its row label and column label, not by its A1 address. For example, the value in `Summary!C12` may mean `Anthropic ARR / 2027E`. `xlsxdiff` stores that semantic identity on each cell snapshot and uses it to match old and new cells before comparing values.

This also reduces noise when a modeler inserts a row or column. If `Gross Margin / 2027E` moves from `Summary!C12` to `Summary!C13`, the diff treats it as the same logical cell. The inserted row is reported as a modeling step, while formulas and final outputs are compared against their aligned logical predecessors.

## Security and Limitations

`xlsxdiff` reads workbook files as Office Open XML packages. It does not execute macros, external links, or workbook code.

Formula values are compared from cached workbook values. The engine does not currently recalculate Excel formulas itself, so stale cached values can produce stale value diffs. Formula dependency parsing covers common Excel references and ranges, but dynamic references such as `INDIRECT`, complex structured references, and some newer Excel functions are reported with diagnostics rather than fully expanded.

## Development

```bash
python -m pytest -q
```

Before publishing publicly, add the license file and project metadata you want attached to the package.
