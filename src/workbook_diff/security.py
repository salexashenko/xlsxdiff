from __future__ import annotations

import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 750 * 1024 * 1024
MAX_ZIP_EXPANSION_RATIO = 100
DEFAULT_RESOURCE_BUDGETS = {
    "max_file_size_bytes": MAX_FILE_SIZE_BYTES,
    "max_uncompressed_bytes": MAX_UNCOMPRESSED_BYTES,
    "max_zip_expansion_ratio": MAX_ZIP_EXPANSION_RATIO,
    "max_zip_members": 25_000,
    "max_parsed_cells": 500_000,
    "max_formulas": 100_000,
    "max_formula_length": 8_192,
    "max_graph_nodes": 750_000,
    "max_graph_edges": 1_000_000,
    "max_virtual_membership_edges": 250_000,
    "max_report_rows": 500,
    "max_diff_seconds": None,
}


class ResourceBudgetExceeded(ValueError):
    """Raised when a workbook diff exceeds configured resource budgets."""


def resolve_resource_budgets(config: Optional[Dict[str, Any]] = None, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = config or {}
    options = options or {}
    nested = config.get("workbook_diff", config) if isinstance(config, dict) else {}
    configured = {}
    if isinstance(nested, dict):
        configured.update(nested.get("security", {}) or {})
        configured.update(nested.get("limits", {}) or {})
        graph = nested.get("graph", {}) or {}
        for key in ["max_graph_nodes", "max_graph_edges", "max_virtual_membership_edges", "max_range_expand_cells"]:
            if key in graph:
                configured[key] = graph[key]
    configured.update({key: value for key, value in options.items() if key in DEFAULT_RESOURCE_BUDGETS})
    budgets = dict(DEFAULT_RESOURCE_BUDGETS)
    for key, value in configured.items():
        if key not in budgets:
            continue
        budgets[key] = _coerce_budget_value(key, value)
    return budgets


def public_resource_budgets(budgets: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in budgets.items() if value is not None}


def make_deadline(budgets: Dict[str, Any]) -> Optional[float]:
    seconds = budgets.get("max_diff_seconds")
    if seconds is None:
        return None
    seconds = float(seconds)
    if seconds <= 0:
        return None
    return time.monotonic() + seconds


def check_deadline(deadline: Optional[float], stage: str) -> None:
    if deadline is not None and time.monotonic() > deadline:
        raise ResourceBudgetExceeded(f"Diff exceeded max_diff_seconds while {stage}.")


def enforce_budget(name: str, value: int, budgets: Dict[str, Any], subject: str) -> None:
    limit = budgets.get(name)
    if limit is None:
        return
    if int(value) > int(limit):
        raise ResourceBudgetExceeded(f"{subject} exceeded {name}: {value} > {limit}")


def inspect_workbook_package(path: Path, strict: bool = False, budgets: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    budgets = budgets or DEFAULT_RESOURCE_BUDGETS
    diagnostics: List[Dict[str, Any]] = []
    suffix = path.suffix.lower()
    if suffix not in {".xlsx", ".xlsm"}:
        raise ValueError(f"Unsupported workbook extension: {suffix}")
    if not path.exists():
        raise FileNotFoundError(str(path))
    size = path.stat().st_size
    enforce_budget("max_file_size_bytes", size, budgets, f"Workbook {path}")
    if not zipfile.is_zipfile(path):
        raise ValueError(f"Workbook is not a valid OOXML zip package or may be encrypted: {path}")

    total_uncompressed = 0
    has_macros = False
    external_link_parts: List[str] = []
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        enforce_budget("max_zip_members", len(infos), budgets, f"Workbook {path}")
        for info in infos:
            total_uncompressed += info.file_size
            lower_name = info.filename.lower()
            if lower_name == "xl/vbaproject.bin":
                has_macros = True
            if lower_name.startswith("xl/externallinks/"):
                external_link_parts.append(info.filename)
            max_ratio = budgets.get("max_zip_expansion_ratio")
            if max_ratio is not None and info.compress_size and info.file_size / info.compress_size > float(max_ratio):
                message = f"Zip member has high expansion ratio: {info.filename}"
                if strict:
                    raise ValueError(message)
                diagnostics.append({"severity": "warning", "code": "ZIP_EXPANSION_RATIO_HIGH", "message": message})
        enforce_budget("max_uncompressed_bytes", total_uncompressed, budgets, f"Workbook {path} uncompressed contents")

    if has_macros:
        diagnostics.append(
            {
                "severity": "info",
                "code": "MACROS_DETECTED",
                "message": "Workbook contains VBA macros. Macros were not executed.",
            }
        )
    if external_link_parts:
        diagnostics.append(
            {
                "severity": "warning",
                "code": "EXTERNAL_LINKS_DETECTED",
                "message": "Workbook contains external link parts. External workbooks were not fetched.",
                "details": {"parts": external_link_parts},
            }
        )

    return {
        "file_size_bytes": size,
        "workbook_type": suffix.lstrip("."),
        "has_macros": has_macros,
        "has_external_links": bool(external_link_parts),
        "external_link_parts": external_link_parts,
    }, diagnostics


def _coerce_budget_value(key: str, value: Any) -> Any:
    if value is None or value == "":
        return None
    if key == "max_diff_seconds":
        return float(value)
    return int(value)
