from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from workbook_diff import diff_workbooks, write_artifacts


EXAMPLE_DIR = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AI ARR/capex workbook diff example through the library API.")
    parser.add_argument(
        "--baseline",
        type=Path,
        default=EXAMPLE_DIR / "workbooks" / "ai_arr_capex_model_v1_march.xlsx",
    )
    parser.add_argument(
        "--candidate",
        type=Path,
        default=EXAMPLE_DIR / "workbooks" / "ai_arr_capex_model_v2_may.xlsx",
    )
    parser.add_argument("--config", type=Path, default=EXAMPLE_DIR / "workbook_diff.yml")
    parser.add_argument("--out", type=Path, default=EXAMPLE_DIR / "reports" / "diff_main")
    args = parser.parse_args()

    config = _load_yaml(args.config)
    result = diff_workbooks(
        args.baseline,
        args.candidate,
        config=config,
        options={"include_hidden_sheets": True, "max_range_expand_cells": 1000},
    )
    artifacts = write_artifacts(result, args.out, formats=["html", "json", "md"])
    print(result["llm_summary"]["one_sentence_summary"])
    for name, path in artifacts.items():
        print(f"{name}: {path}")


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML config must be a mapping: {path}")
    return data


if __name__ == "__main__":
    main()
