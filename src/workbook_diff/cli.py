from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import yaml

from .diff import diff_workbooks
from .reporting import write_artifacts


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(prog="diffsheet", description="Compare two Excel workbooks and generate semantic diff reports.")
    parser.add_argument("baseline", type=Path, help="Baseline .xlsx or .xlsm workbook")
    parser.add_argument("candidate", type=Path, help="Candidate .xlsx or .xlsm workbook")
    parser.add_argument("--config", type=Path, help="Optional YAML config file")
    parser.add_argument("--out", type=Path, default=Path("diff_out"), help="Output directory")
    parser.add_argument("--format", default="html,json,md", help="Comma-separated formats: html,json,md")
    parser.add_argument("--include-style-changes", action="store_true")
    parser.add_argument("--include-comments", action="store_true")
    parser.add_argument("--include-hidden-sheets", action="store_true", default=True)
    parser.add_argument("--ignore-hidden-sheets", action="store_true")
    parser.add_argument("--materiality-pct", type=float, default=0.01)
    parser.add_argument("--materiality-abs", type=float, default=1000)
    parser.add_argument("--max-visible-nodes", type=int, default=80)
    parser.add_argument("--max-range-expand-cells", type=int, default=1000)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json-only", action="store_true")
    parser.add_argument("--value-mode", choices=["cached", "none", "recalc-libreoffice", "recalc-excel"], default="cached")
    args = parser.parse_args(argv)

    if args.value_mode != "cached":
        parser.error("Only --value-mode cached is implemented in the MVP.")

    config = _load_config(args.config)
    options: Dict[str, Any] = {
        "include_style_changes": args.include_style_changes,
        "include_comments": args.include_comments,
        "include_hidden_sheets": args.include_hidden_sheets and not args.ignore_hidden_sheets,
        "materiality_pct": args.materiality_pct,
        "materiality_abs": args.materiality_abs,
        "max_visible_nodes": args.max_visible_nodes,
        "max_range_expand_cells": args.max_range_expand_cells,
        "strict": args.strict,
    }
    result = diff_workbooks(args.baseline, args.candidate, config=config, options=options)
    formats = [item.strip().lower() for item in args.format.split(",") if item.strip()]
    artifacts = write_artifacts(result, args.out, formats=formats, json_only=args.json_only)
    for name, path in artifacts.items():
        print(f"{name}: {path}")


def _load_config(path: Optional[Path]) -> Dict[str, Any]:
    if not path:
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError("Config file must contain a YAML mapping.")
    return data


if __name__ == "__main__":
    main(sys.argv[1:])
