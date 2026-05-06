from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from workbook_diff import diff_workbooks
from benchmarks.run_benchmark import main as run_benchmark


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


def test_public_benchmark_artifacts_match_public_schemas() -> None:
    diff_schema = json.loads((SCHEMA_DIR / "diff.schema.v0.1.json").read_text(encoding="utf-8"))
    llm_schema = json.loads((SCHEMA_DIR / "llm_summary.schema.v0.1.json").read_text(encoding="utf-8"))
    diff_schema = dict(diff_schema)
    diff_schema["properties"] = dict(diff_schema["properties"])
    diff_schema["properties"]["llm_summary"] = {"type": "object"}
    diff_validator = Draft202012Validator(diff_schema)
    llm_validator = Draft202012Validator(llm_schema)

    for case_dir in sorted(path for path in BENCHMARK_CASES.iterdir() if path.is_dir()):
        expected = json.loads((case_dir / "expected.diff.json").read_text(encoding="utf-8"))
        diff_validator.validate(expected)
        llm_validator.validate(expected["llm_summary"])


def test_scored_public_benchmark_passes() -> None:
    assert run_benchmark(["--cases-dir", str(BENCHMARK_CASES)]) == 0


def test_public_json_schemas_are_valid_json() -> None:
    schema_paths = sorted(SCHEMA_DIR.glob("*.json"))
    assert schema_paths, "No JSON schemas found."

    for schema_path in schema_paths:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        assert schema["$schema"].startswith("https://json-schema.org/")
        assert schema["$id"].startswith("https://github.com/salexashenko/xlsxdiff/")
