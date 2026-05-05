from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from openpyxl.utils.cell import (
    absolute_coordinate,
    column_index_from_string,
    get_column_letter,
    range_boundaries,
)

from .utils import cell_id, quote_sheet_name, unquote_sheet_name


CELL_RE = r"\$?[A-Za-z]{1,3}\$?\d{1,7}"
RANGE_RE = rf"{CELL_RE}(?::{CELL_RE})?"
QUOTED_SHEET_RE = r"'(?:[^']|'')+'"
UNQUOTED_SHEET_RE = r"[A-Za-z_][A-Za-z0-9_ .]*"
SHEET_PREFIX_RE = rf"(?:(?P<external>\[[^\]]+\])?(?P<sheet>{QUOTED_SHEET_RE}|{UNQUOTED_SHEET_RE})!)?"
REFERENCE_RE = re.compile(rf"(?<![A-Za-z0-9_]){SHEET_PREFIX_RE}(?P<ref>{RANGE_RE})(?![A-Za-z0-9_])")
FUNCTION_RE = re.compile(r"(?<![A-Za-z0-9_\.])([A-Za-z_][A-Za-z0-9_\.]*)\s*\(")
NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_])[-+]?\d+(?:\.\d+)?(?:[Ee][-+]?\d+)?%?(?![A-Za-z0-9_])")
TABLE_RE = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z_][A-Za-z0-9_\.]*)\s*\[([^\]]+)\]")
NAMED_RE = re.compile(r"(?<![A-Za-z0-9_\.])([A-Za-z_\\][A-Za-z0-9_\\\.]*)(?![A-Za-z0-9_\.]|\s*\()")

VOLATILE_FUNCTIONS = {"NOW", "TODAY", "RAND", "RANDBETWEEN", "OFFSET", "INDIRECT"}
DYNAMIC_REFERENCE_FUNCTIONS = {"OFFSET", "INDIRECT"}
KNOWN_FUNCTIONS = {
    "SUM",
    "SUMIF",
    "SUMIFS",
    "COUNT",
    "COUNTIF",
    "COUNTIFS",
    "AVERAGE",
    "AVERAGEIF",
    "AVERAGEIFS",
    "MIN",
    "MAX",
    "IF",
    "IFS",
    "AND",
    "OR",
    "XLOOKUP",
    "VLOOKUP",
    "HLOOKUP",
    "INDEX",
    "MATCH",
    "ROUND",
    "ROUNDUP",
    "ROUNDDOWN",
    "NPV",
    "IRR",
    "XIRR",
    "PMT",
    "OFFSET",
    "INDIRECT",
    "TRUE",
    "FALSE",
}


@dataclass(frozen=True)
class ParsedReference:
    raw: str
    ref: str
    sheet_name: str
    kind: str
    target: str
    external_workbook: Optional[str] = None
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "raw": self.raw,
            "ref": self.ref,
            "sheet_name": self.sheet_name,
            "kind": self.kind,
            "target": self.target,
            "confidence": self.confidence,
        }
        if self.external_workbook:
            data["external_workbook"] = self.external_workbook
        return data


def normalize_formula(formula: Optional[str]) -> str:
    if formula is None:
        return ""
    text = str(formula).strip()
    if text.startswith("="):
        text = text[1:]
    out: List[str] = []
    in_double = False
    in_single = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '"' and not in_single:
            in_double = not in_double
            out.append(ch)
        elif ch == "'" and not in_double:
            in_single = not in_single
            out.append(ch)
        elif ch.isspace() and not in_double and not in_single:
            pass
        elif not in_double and not in_single:
            out.append(ch.upper())
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def formula_functions(formula: str) -> List[str]:
    cleaned = _strip_strings(formula)
    return sorted({match.group(1).upper() for match in FUNCTION_RE.finditer(cleaned)})


def numeric_constants(formula: str) -> List[str]:
    cleaned = _strip_strings(formula)
    numbers = []
    occupied = _reference_spans(cleaned)
    for match in NUMBER_RE.finditer(cleaned):
        if not _span_overlaps(match.span(), occupied):
            numbers.append(match.group(0).upper())
    return sorted(numbers)


def formula_operators(formula: str) -> List[str]:
    cleaned = _strip_strings(formula)
    return sorted([ch for ch in cleaned if ch in "+-*/^&=<>"])


def parse_formula_references(
    formula: Optional[str],
    current_sheet: str,
    sheet_names: Sequence[str],
    defined_names: Optional[Dict[str, str]] = None,
    tables: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Tuple[List[ParsedReference], List[Dict[str, Any]], List[str], str]:
    if not formula:
        return [], [], [], "ok"
    text = str(formula)
    cleaned = _strip_strings(text)
    defined_names = defined_names or {}
    tables = tables or {}
    sheet_lookup = {name.upper(): name for name in sheet_names}
    precedents: List[ParsedReference] = []
    tokens: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for match in TABLE_RE.finditer(cleaned):
        table_name = match.group(1)
        raw = match.group(0)
        table = tables.get(table_name.upper())
        if table:
            target = table["ref"]
            sheet = table["sheet_name"]
            kind = "table_reference"
            confidence = 0.8
        else:
            target = raw
            sheet = current_sheet
            kind = "table_reference"
            confidence = 0.4
            warnings.append(f"Could not resolve structured table reference {raw}.")
        precedents.append(ParsedReference(raw=raw, ref=raw, sheet_name=sheet, kind=kind, target=target, confidence=confidence))
        tokens.append({"type": "table_reference", "text": raw})

    for match in REFERENCE_RE.finditer(cleaned):
        raw = match.group(0)
        ref = _normalize_a1_ref(match.group("ref"))
        sheet_part = match.group("sheet")
        external = match.group("external")
        if sheet_part:
            sheet = unquote_sheet_name(sheet_part)
        else:
            sheet = current_sheet
        if external:
            target = f"{external}{quote_sheet_name(sheet)}!{ref}"
            precedents.append(
                ParsedReference(
                    raw=raw,
                    ref=ref,
                    sheet_name=sheet,
                    kind="external_reference",
                    target=target,
                    external_workbook=external.strip("[]"),
                    confidence=0.5,
                )
            )
            tokens.append({"type": "external_reference", "text": raw})
        elif sheet.upper() in sheet_lookup:
            canonical_sheet = sheet_lookup[sheet.upper()]
            target = cell_id(canonical_sheet, ref)
            kind = "range" if ":" in ref else "cell"
            precedents.append(ParsedReference(raw=raw, ref=ref, sheet_name=canonical_sheet, kind=kind, target=target))
            tokens.append({"type": "reference", "text": raw, "target": target})
        else:
            target = f"{quote_sheet_name(sheet)}!{ref}"
            precedents.append(ParsedReference(raw=raw, ref=ref, sheet_name=sheet, kind="external_reference", target=target, confidence=0.4))
            tokens.append({"type": "external_reference", "text": raw})
            warnings.append(f"Reference points at unknown sheet {sheet}.")

    occupied = _reference_spans(cleaned)
    functions = set(formula_functions(cleaned))
    for name, target in defined_names.items():
        pattern = re.compile(rf"(?<![A-Za-z0-9_\.]){re.escape(name)}(?![A-Za-z0-9_\.])", re.IGNORECASE)
        for match in pattern.finditer(cleaned):
            if _span_overlaps(match.span(), occupied):
                continue
            raw = match.group(0)
            precedents.append(
                ParsedReference(raw=raw, ref=raw, sheet_name=current_sheet, kind="defined_name_reference", target=target, confidence=0.9)
            )
            tokens.append({"type": "defined_name", "text": raw, "target": target})

    for function in functions:
        tokens.append({"type": "function", "text": function})
        if function in DYNAMIC_REFERENCE_FUNCTIONS:
            warnings.append(f"Formula uses {function}; dependency extraction is partial.")

    for number in numeric_constants(cleaned):
        tokens.append({"type": "number", "text": number})

    parse_status = "partial" if warnings else "ok"
    return _dedupe_precedents(precedents), tokens, warnings, parse_status


def classify_formula_change(old_formula: Optional[str], new_formula: Optional[str], current_sheet: str, sheet_names: Sequence[str]) -> Dict[str, Any]:
    old_norm = normalize_formula(old_formula)
    new_norm = normalize_formula(new_formula)
    old_refs, _, _, _ = parse_formula_references(old_formula, current_sheet, sheet_names)
    new_refs, _, _, _ = parse_formula_references(new_formula, current_sheet, sheet_names)
    old_ref_targets = sorted({ref.target for ref in old_refs})
    new_ref_targets = sorted({ref.target for ref in new_refs})
    old_functions = formula_functions(old_formula or "")
    new_functions = formula_functions(new_formula or "")
    old_numbers = numeric_constants(old_formula or "")
    new_numbers = numeric_constants(new_formula or "")
    old_ops = formula_operators(old_formula or "")
    new_ops = formula_operators(new_formula or "")

    if old_norm == new_norm:
        kind = "formula_normalization_only"
    elif any(ref.kind == "external_reference" for ref in old_refs + new_refs) and old_ref_targets != new_ref_targets:
        kind = "formula_external_reference_changed"
    elif old_ref_targets != new_ref_targets:
        if any(ref.kind == "defined_name_reference" for ref in old_refs + new_refs):
            kind = "formula_named_range_changed"
        else:
            kind = "formula_reference_changed"
    elif old_functions != new_functions:
        kind = "formula_function_changed"
    elif old_numbers != new_numbers:
        kind = "formula_constant_changed"
    elif old_ops != new_ops:
        kind = "formula_operator_changed"
    else:
        kind = "formula_text_changed"

    token_diff = []
    for diff_type, old_items, new_items in [
        ("reference", old_ref_targets, new_ref_targets),
        ("function", old_functions, new_functions),
        ("number", old_numbers, new_numbers),
        ("operator", old_ops, new_ops),
    ]:
        if old_items != new_items:
            token_diff.append({"type": diff_type, "old": old_items, "new": new_items})

    return {
        "kind": kind,
        "old_formula": old_formula,
        "new_formula": new_formula,
        "old_normalized": old_norm,
        "new_normalized": new_norm,
        "token_diff": token_diff,
    }


def expand_reference_cells(target: str, max_cells: int) -> Tuple[List[str], bool]:
    if "!" not in target:
        return [], False
    sheet, ref = target.rsplit("!", 1)
    sheet = unquote_sheet_name(sheet)
    if ":" not in ref:
        return [cell_id(sheet, _normalize_a1_ref(ref))], True
    try:
        min_col, min_row, max_col, max_row = range_boundaries(ref.replace("$", ""))
    except ValueError:
        return [], False
    count = (max_col - min_col + 1) * (max_row - min_row + 1)
    if count > max_cells:
        return [], False
    cells = []
    for row in range(min_row, max_row + 1):
        for col in range(min_col, max_col + 1):
            cells.append(cell_id(sheet, f"{get_column_letter(col)}{row}"))
    return cells, True


def references_equal(old_formula: Optional[str], new_formula: Optional[str], current_sheet: str, sheet_names: Sequence[str]) -> bool:
    old_refs, _, _, _ = parse_formula_references(old_formula, current_sheet, sheet_names)
    new_refs, _, _, _ = parse_formula_references(new_formula, current_sheet, sheet_names)
    return sorted(ref.target for ref in old_refs) == sorted(ref.target for ref in new_refs)


def _normalize_a1_ref(ref: str) -> str:
    parts = ref.split(":")
    normalized = []
    for part in parts:
        normalized.append(absolute_coordinate(part).replace("$", ""))
    return ":".join(normalized)


def _strip_strings(text: str) -> str:
    out = []
    in_double = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '"':
            in_double = not in_double
            out.append(" ")
        elif in_double:
            out.append(" ")
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def _reference_spans(text: str) -> List[Tuple[int, int]]:
    spans = [match.span() for match in REFERENCE_RE.finditer(text)]
    spans.extend(match.span() for match in TABLE_RE.finditer(text))
    return spans


def _span_overlaps(span: Tuple[int, int], occupied: Iterable[Tuple[int, int]]) -> bool:
    start, end = span
    return any(start < occupied_end and end > occupied_start for occupied_start, occupied_end in occupied)


def _dedupe_precedents(precedents: List[ParsedReference]) -> List[ParsedReference]:
    seen: Set[Tuple[str, str, str]] = set()
    result = []
    for precedent in precedents:
        key = (precedent.kind, precedent.target, precedent.raw.upper())
        if key in seen:
            continue
        seen.add(key)
        result.append(precedent)
    return result

