from __future__ import annotations

import json
from pathlib import Path

import yaml

from workbook_diff import diff_workbooks


REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_CASES = REPO_ROOT / "benchmarks" / "cases"
SCHEMA_DIR = REPO_ROOT / "schemas"


def test_public_benchmark_fixtures_match_expected_diffs() -> None:
    case_dirs = sorted(path for path in BENCHMARK_CASES.iterdir() if path.is_dir())
    assert case_dirs, "No public benchmark cases found."

    for case_dir in case_dirs:
        settings = yaml.safe_load((case_dir / "workbook_diff.yml").read_text(encoding="utf-8")) or {}
        result = diff_workbooks(
            case_dir / "baseline.xlsx",
            case_dir / "candidate.xlsx",
            config=settings.get("config") or {},
            options=settings.get("options") or {},
        )
        public_result = {key: value for key, value in result.items() if key != "_artifacts"}
        expected = json.loads((case_dir / "expected.diff.json").read_text(encoding="utf-8"))
        assert public_result == expected, case_dir.name


def test_public_json_schemas_are_valid_json() -> None:
    schema_paths = sorted(SCHEMA_DIR.glob("*.json"))
    assert schema_paths, "No JSON schemas found."

    for schema_path in schema_paths:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        assert schema["$schema"].startswith("https://json-schema.org/")
        assert schema["$id"].startswith("https://github.com/salexashenko/xlsxdiff/")
