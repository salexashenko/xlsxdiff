from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any, Dict, List, Tuple


MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 750 * 1024 * 1024
MAX_ZIP_EXPANSION_RATIO = 100


def inspect_workbook_package(path: Path, strict: bool = False) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    diagnostics: List[Dict[str, Any]] = []
    suffix = path.suffix.lower()
    if suffix not in {".xlsx", ".xlsm"}:
        raise ValueError(f"Unsupported workbook extension: {suffix}")
    if not path.exists():
        raise FileNotFoundError(str(path))
    size = path.stat().st_size
    if size > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"Workbook exceeds size limit: {path}")
    if not zipfile.is_zipfile(path):
        raise ValueError(f"Workbook is not a valid OOXML zip package or may be encrypted: {path}")

    total_uncompressed = 0
    has_macros = False
    external_link_parts: List[str] = []
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            total_uncompressed += info.file_size
            lower_name = info.filename.lower()
            if lower_name == "xl/vbaproject.bin":
                has_macros = True
            if lower_name.startswith("xl/externallinks/"):
                external_link_parts.append(info.filename)
            if info.compress_size and info.file_size / info.compress_size > MAX_ZIP_EXPANSION_RATIO:
                message = f"Zip member has high expansion ratio: {info.filename}"
                if strict:
                    raise ValueError(message)
                diagnostics.append({"severity": "warning", "code": "ZIP_EXPANSION_RATIO_HIGH", "message": message})
        if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
            raise ValueError(f"Workbook uncompressed contents exceed limit: {path}")

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

