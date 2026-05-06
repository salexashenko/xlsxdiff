from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import yaml

from workbook_diff import diff_workbooks

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - exercised only outside the dev environment.
    Draft202012Validator = None  # type: ignore[assignment]


REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_CASES = REPO_ROOT / "benchmarks" / "cases"
SCHEMA_DIR = REPO_ROOT / "schemas"


CHECKS = [
    ("diff_match", "full diff match"),
    ("top_root", "top root correct"),
    ("top_output", "top output correct"),
    ("path", "path contains expected nodes"),
    ("strength", "explanation strength correct"),
    ("direct_noise", "no false noisy direct changes"),
    ("schema", "schema valid"),
]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run scored public benchmark cases.")
    parser.add_argument("--cases-dir", type=Path, default=BENCHMARK_CASES)
    args = parser.parse_args(argv)

    case_dirs = sorted(path for path in args.cases_dir.iterdir() if path.is_dir())
    if not case_dirs:
        print(f"No benchmark cases found in {args.cases_dir}", file=sys.stderr)
        return 1

    rows = []
    for case_dir in case_dirs:
        rows.append(_score_case(case_dir))

    _print_report(rows)
    return 0 if all(all(status for _name, status in row["checks"]) for row in rows) else 1


def _score_case(case_dir: Path) -> Dict[str, Any]:
    actual = _run_case(case_dir)
    expected = json.loads((case_dir / "expected.diff.json").read_text(encoding="utf-8"))
    actual_llm = actual.get("llm_summary", {})
    expected_llm = expected.get("llm_summary", {})
    actual_output = _first_final_output(actual_llm)
    expected_output = _first_final_output(expected_llm)
    checks = [
        ("diff_match", actual == expected),
        ("top_root", _first_ref(actual_llm.get("top_direct_changes")) == _first_ref(expected_llm.get("top_direct_changes"))),
        ("top_output", (actual_output or {}).get("ref") == (expected_output or {}).get("ref")),
        ("path", _path_contains_expected_nodes(actual_output, expected_output)),
        ("strength", (actual_output or {}).get("explanation_strength") == (expected_output or {}).get("explanation_strength")),
        ("direct_noise", _refs(actual_llm.get("top_direct_changes")) == _refs(expected_llm.get("top_direct_changes"))),
        ("schema", _schema_valid(actual)),
    ]
    return {"case": case_dir.name, "checks": checks}


def _run_case(case_dir: Path) -> Dict[str, Any]:
    settings = yaml.safe_load((case_dir / "workbook_diff.yml").read_text(encoding="utf-8")) or {}
    result = diff_workbooks(
        case_dir / "baseline.xlsx",
        case_dir / "candidate.xlsx",
        config=settings.get("config") or {},
        options=settings.get("options") or {},
    )
    return {key: value for key, value in result.items() if key != "_artifacts"}


def _first_final_output(llm_summary: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    outputs = llm_summary.get("final_outputs") or llm_summary.get("top_impacted_outputs") or []
    return outputs[0] if outputs else None


def _first_ref(items: Any) -> Optional[str]:
    if not items:
        return None
    return items[0].get("ref")


def _refs(items: Any) -> List[str]:
    return [item.get("ref") for item in (items or [])]


def _path_contains_expected_nodes(actual_output: Optional[Dict[str, Any]], expected_output: Optional[Dict[str, Any]]) -> bool:
    expected_nodes = _first_path_nodes(expected_output)
    if not expected_nodes:
        return True
    actual_nodes = _first_path_nodes(actual_output)
    if not actual_nodes:
        return False
    cursor = 0
    for node in actual_nodes:
        if node == expected_nodes[cursor]:
            cursor += 1
            if cursor == len(expected_nodes):
                return True
    return False


def _first_path_nodes(output: Optional[Dict[str, Any]]) -> List[str]:
    if not output:
        return []
    paths = output.get("representative_paths") or []
    if not paths:
        return []
    return list(paths[0].get("nodes") or [])


def _schema_valid(public_result: Dict[str, Any]) -> bool:
    if Draft202012Validator is None:
        return False
    diff_schema = json.loads((SCHEMA_DIR / "diff.schema.v0.1.json").read_text(encoding="utf-8"))
    llm_schema = json.loads((SCHEMA_DIR / "llm_summary.schema.v0.1.json").read_text(encoding="utf-8"))
    Draft202012Validator(llm_schema).validate(public_result["llm_summary"])

    diff_schema = copy.deepcopy(diff_schema)
    diff_schema["properties"]["llm_summary"] = {"type": "object"}
    Draft202012Validator(diff_schema).validate(public_result)
    return True


def _print_report(rows: Iterable[Dict[str, Any]]) -> None:
    rows = list(rows)
    case_width = max(len("case"), *(len(row["case"]) for row in rows))
    print(f"{'case':<{case_width}}  " + "  ".join(name for name, _label in CHECKS))
    for row in rows:
        status_by_name = dict(row["checks"])
        values = ["ok" if status_by_name[name] else "FAIL" for name, _label in CHECKS]
        print(f"{row['case']:<{case_width}}  " + "  ".join(f"{value:<10}" for value in values))
    print()
    print(f"cases passed: {sum(1 for row in rows if all(status for _name, status in row['checks']))}/{len(rows)}")
    for name, label in CHECKS:
        passed = sum(1 for row in rows if dict(row["checks"])[name])
        print(f"{label}: {passed}/{len(rows)}")


if __name__ == "__main__":
    raise SystemExit(main())
