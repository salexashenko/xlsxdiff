from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


Diagnostic = Dict[str, Any]


@dataclass
class CellValue:
    raw: Any
    typed_value: Any
    display_value: str
    value_type: str
    number_format: Optional[str] = None
    error_code: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "raw": self.raw,
            "typed_value": self.typed_value,
            "display_value": self.display_value,
            "value_type": self.value_type,
        }
        if self.number_format:
            data["number_format"] = self.number_format
        if self.error_code:
            data["error_code"] = self.error_code
        return data


@dataclass
class FormulaSnapshot:
    raw: str
    normalized: str
    formula_type: str
    tokens: List[Dict[str, Any]]
    precedents: List[Dict[str, Any]]
    has_volatile_function: bool
    has_dynamic_reference: bool
    has_external_reference: bool
    parse_status: str
    parse_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw": self.raw,
            "normalized": self.normalized,
            "formula_type": self.formula_type,
            "tokens": self.tokens,
            "precedents": self.precedents,
            "has_volatile_function": self.has_volatile_function,
            "has_dynamic_reference": self.has_dynamic_reference,
            "has_external_reference": self.has_external_reference,
            "parse_status": self.parse_status,
            "parse_warnings": self.parse_warnings,
        }


@dataclass
class CellSnapshot:
    id: str
    sheet_name: str
    address: str
    row: int
    col: int
    kind: str
    value: CellValue
    formula: Optional[FormulaSnapshot]
    style: Optional[Dict[str, Any]]
    comment: Optional[Dict[str, Any]]
    hyperlink: Optional[Dict[str, Any]]
    labels: List[Dict[str, Any]]
    semantic_id: Optional[str]
    semantic_identity: Dict[str, Any]
    semantic_role: str
    visibility_context: Dict[str, bool]

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "id": self.id,
            "sheet_name": self.sheet_name,
            "address": self.address,
            "row": self.row,
            "col": self.col,
            "kind": self.kind,
            "value": self.value.to_dict(),
            "labels": self.labels,
            "semantic_id": self.semantic_id,
            "semantic_identity": self.semantic_identity,
            "semantic_role": self.semantic_role,
            "visibility_context": self.visibility_context,
        }
        if self.formula:
            data["formula"] = self.formula.to_dict()
        if self.style:
            data["style"] = self.style
        if self.comment:
            data["comment"] = self.comment
        if self.hyperlink:
            data["hyperlink"] = self.hyperlink
        return data


@dataclass
class WorkbookSnapshot:
    schema_version: str
    file: Dict[str, Any]
    sheets: List[Dict[str, Any]]
    defined_names: List[Dict[str, Any]]
    tables: List[Dict[str, Any]]
    external_links: List[Dict[str, Any]]
    cells: Dict[str, CellSnapshot]
    diagnostics: List[Diagnostic]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "file": self.file,
            "sheets": self.sheets,
            "defined_names": self.defined_names,
            "tables": self.tables,
            "external_links": self.external_links,
            "cells": {key: value.to_dict() for key, value in self.cells.items()},
            "diagnostics": self.diagnostics,
        }
