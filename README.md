# xlsxdiff

`xlsxdiff` is a semantic diff engine for Excel workbooks. It compares two `.xlsx` or `.xlsm` files, identifies changed constants and formulas, traces formula dependencies to impacted outputs, and writes reports for humans and LLM agents.

The project is designed for spreadsheet review workflows where a plain cell-by-cell diff is too noisy: financial models, planning workbooks, operating dashboards, and generated Excel artifacts.

Typical output is meant to be directly usable in review:

```text
Summary!G31 Total LTV changed from 1180 to 1220 (+40.0 / +3.4%), likely explained by Assumptions!D14 Growth Rate changing from 0.18 to 0.22; 0 unexplained value changes were detected.
```

## What It Does

- Detects changed constants, formulas, workbook metadata, defined names, tables, comments, hyperlinks, and optional style changes.
- Parses formula references to build a dependency graph from changed inputs to impacted outputs.
- Infers semantic cell identity from defined names, row headers, and column headers, so cells can be matched by meaning rather than only by A1 address.
- Aligns many shifted model cells when stable semantic labels can be inferred from row/column headers, defined names, and nearby labels, reducing false delete/add noise.
- Groups real modeling edits such as inserted model steps, raw data refreshes, and formula blocks.
- Emits compact `llm_summary.json` output so agents can summarize a workbook diff without reading a full report.

## Install

```bash
pip install xlsxdiff
```

For local development:

```bash
pip install -e ".[dev]"
```

## CLI

```bash
xlsxdiff old.xlsx new.xlsx --out diff_out
```

`workbook-diff` is also installed as a backwards-compatible CLI alias.

By default the output directory includes:

- `diff_report.html`: interactive report with a focused impact graph.
- `llm_summary.json`: compact structured summary for agents.
- `llm_summary.md`: Markdown version of the LLM summary.
- `diff.json`: full structured diff.
- `change_graph.json`: dependency graph and impact paths.
- `changed_cells.csv`: flat changed-cell table.
- `diagnostics.json`: parser and model caveats.
- `graph.dot`: Graphviz dependency graph.

`diff.json` and `llm_summary.json` use `schema_version: "0.1"`. Draft public schemas live in `schemas/`.

## Python API

```python
from pathlib import Path

from workbook_diff import diff_workbooks, write_artifacts

result = diff_workbooks(Path("old.xlsx"), Path("new.xlsx"))
write_artifacts(result, Path("diff_out"), formats=["html", "json", "md"])

print(result["llm_summary"]["one_sentence_summary"])
```

Pass config as a dictionary when a workbook has known output cells or semantic ranges:

```python
result = diff_workbooks(
    Path("old.xlsx"),
    Path("new.xlsx"),
    config={
        "outputs": [
            {"ref": "Summary!G31", "name": "Total LTV"},
            {"ref": "Summary!B6", "name": "2027 supportable capex"},
        ],
        "assumption_ranges": ["Assumptions!B7:C10"],
        "raw_data_sheets": ["Raw Export"],
    },
)
```

## LLM Usage

For agent workflows, read `llm_summary.json` or `result["llm_summary"]` instead of trying to summarize the full diff. The summary includes:

- `one_sentence_summary`: a ready-to-send summary sentence.
- `top_direct_changes`: important changed assumptions, formulas, inputs, or metadata.
- `top_change_groups`: grouped edits such as inserted/deleted modeling steps.
- `top_impacted_outputs`: ranked final variables with old value, new value, delta, and upstream change IDs.
- `claims`: structured evidence-backed claims that support the one-sentence summary.
- `caveats`: diagnostics that should temper the answer.

A useful agent response pattern is to use `one_sentence_summary` for the answer, mention one or two `top_direct_changes` or `top_change_groups` only when the user asks for detail, and surface `caveats` when the diff includes unexplained output changes or unsupported formula constructs.

## Support Matrix

| Feature | Current status |
| --- | --- |
| A1 references | Supported |
| Cross-sheet references | Supported |
| Small ranges | Supported and expanded into cell-level dependency edges |
| Large ranges | Represented as range nodes; changed cells inside those ranges get virtual membership edges |
| Defined names / named ranges | Detected and modeled as graph roots for downstream impact |
| Structured table references | Partial; table ranges are detected, but structured-column semantics are limited |
| External workbook references | Detected and modeled as opaque external references; external workbooks are not fetched |
| Inserted rows/columns | Partial; shifted cells are aligned when stable semantic labels can be inferred |
| `INDIRECT` / `OFFSET` | Reported as opaque or partial dependency extraction |
| Volatile functions | Detected and treated as confidence caveats |
| Dynamic arrays | Partial; dependency extraction may be incomplete |
| Pivot tables | Not evaluated |
| VBA macros / UDFs | Detected where possible, never executed |

## Regenerate Example Reports

The repository includes example workbooks and a script that regenerates report artifacts locally:

```bash
python examples/ai_arr_capex/run_diff.py
```

Generated example reports are ignored by Git.

## Security and Limitations

`xlsxdiff` reads workbook files as Office Open XML packages. It does not execute macros, external links, or workbook code.

Formula values are compared from cached workbook values. The engine does not currently recalculate Excel formulas itself, so stale cached values can produce stale value diffs. Formula dependency parsing covers common Excel references and ranges, but dynamic references such as `INDIRECT`, complex structured references, and some newer Excel functions are reported with diagnostics rather than fully expanded.

## Development

```bash
python -m pytest -q
```

Public benchmark fixtures and the checked-in sample report can be regenerated with:

```bash
python benchmarks/generate_benchmarks.py
```

## License

`xlsxdiff` is released under the Zero-Clause BSD license. See `LICENSE`.
