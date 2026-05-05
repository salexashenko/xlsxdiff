from __future__ import annotations

import hashlib
import html
import json
import math
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cell_id(sheet_name: str, address: str) -> str:
    return f"{sheet_name}!{address}"


def split_cell_id(ref: str) -> Tuple[str, str]:
    if "!" not in ref:
        return "", ref
    sheet, address = ref.rsplit("!", 1)
    return unquote_sheet_name(sheet), address


def quote_sheet_name(sheet_name: str) -> str:
    if any(ch in sheet_name for ch in " !'"):
        return "'" + sheet_name.replace("'", "''") + "'"
    return sheet_name


def unquote_sheet_name(sheet_name: str) -> str:
    sheet_name = sheet_name.strip()
    if len(sheet_name) >= 2 and sheet_name[0] == "'" and sheet_name[-1] == "'":
        return sheet_name[1:-1].replace("''", "'")
    return sheet_name


def json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    return str(value)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=False, default=json_default) + "\n",
        encoding="utf-8",
    )


def escape_html(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def display_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.12g}"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def safe_float(value: Any) -> Optional[float]:
    if is_number(value):
        return float(value)
    return None


def first_present(items: Iterable[Optional[str]]) -> Optional[str]:
    for item in items:
        if item:
            return item
    return None

