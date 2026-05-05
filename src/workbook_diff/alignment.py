from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from openpyxl.utils.cell import coordinate_to_tuple

from .utils import split_cell_id


def build_structural_alignment(baseline: Any, candidate: Any) -> Dict[str, Any]:
    old_to_new: Dict[str, str] = {}
    new_to_old: Dict[str, str] = {}
    matches: List[Dict[str, Any]] = []

    _match_by_semantic_id(baseline, candidate, old_to_new, new_to_old, matches)
    _match_by_address(baseline, candidate, old_to_new, new_to_old, matches)

    old_refs = set(baseline.cells)
    new_refs = set(candidate.cells)
    unmatched_old = sorted(old_refs - set(old_to_new), key=_ref_sort_key)
    unmatched_new = sorted(new_refs - set(new_to_old), key=_ref_sort_key)
    shifted = [match for match in matches if match["old_ref"] != match["new_ref"]]
    semantic = [match for match in matches if match["matched_by"] == "semantic_id"]
    return {
        "old_to_new": old_to_new,
        "new_to_old": new_to_old,
        "matches": sorted(matches, key=lambda item: (_ref_sort_key(item["new_ref"]), _ref_sort_key(item["old_ref"]))),
        "unmatched_old_refs": unmatched_old,
        "unmatched_new_refs": unmatched_new,
        "summary": {
            "matched_cells": len(matches),
            "semantic_matches": len(semantic),
            "shifted_semantic_matches": len(shifted),
            "unmatched_old_cells": len(unmatched_old),
            "unmatched_new_cells": len(unmatched_new),
        },
    }


def remap_graph_refs(graph: Dict[str, Any], old_to_new: Dict[str, str], edge_id_prefix: str = "remapped_") -> Dict[str, Any]:
    nodes: Dict[str, Dict[str, Any]] = {}
    for node_id, node in graph.get("nodes", {}).items():
        mapped_id = old_to_new.get(node_id, node_id)
        mapped_node = dict(node)
        if mapped_id != node_id:
            mapped_node["old_ref"] = node.get("ref", node_id)
            mapped_node["id"] = mapped_id
            mapped_node["ref"] = mapped_id
        nodes[mapped_id] = _merge_nodes(nodes.get(mapped_id), mapped_node)

    edges: List[Dict[str, Any]] = []
    seen_edges: Set[Tuple[str, str, str, str]] = set()
    for edge in graph.get("edges", []):
        mapped_from = old_to_new.get(edge["from"], edge["from"])
        mapped_to = old_to_new.get(edge["to"], edge["to"])
        if mapped_from == mapped_to:
            continue
        mapped_edge = dict(edge)
        mapped_edge["id"] = f"{edge_id_prefix}{edge['id']}"
        mapped_edge["from"] = mapped_from
        mapped_edge["to"] = mapped_to
        if mapped_edge.get("formula_ref") in old_to_new:
            mapped_edge["formula_ref"] = old_to_new[mapped_edge["formula_ref"]]
        key = (mapped_from, mapped_to, mapped_edge.get("edge_type", ""), mapped_edge.get("evidence", ""))
        if key in seen_edges:
            continue
        seen_edges.add(key)
        edges.append(mapped_edge)

    return {
        "nodes": nodes,
        "edges": edges,
        "adjacency": _adjacency(edges),
        "reverse_adjacency": _reverse_adjacency(edges),
    }


def _match_by_semantic_id(
    baseline: Any,
    candidate: Any,
    old_to_new: Dict[str, str],
    new_to_old: Dict[str, str],
    matches: List[Dict[str, Any]],
) -> None:
    old_unique = _unique_semantic_cells(baseline)
    new_unique = _unique_semantic_cells(candidate)
    for semantic_id in sorted(set(old_unique) & set(new_unique)):
        old_cell = old_unique[semantic_id]
        new_cell = new_unique[semantic_id]
        if old_cell.id in old_to_new or new_cell.id in new_to_old:
            continue
        confidence = min(
            float(old_cell.semantic_identity.get("confidence") or 0),
            float(new_cell.semantic_identity.get("confidence") or 0),
        )
        _add_match(
            old_cell.id,
            new_cell.id,
            "semantic_id",
            confidence,
            old_to_new,
            new_to_old,
            matches,
            semantic_id=semantic_id,
        )


def _match_by_address(
    baseline: Any,
    candidate: Any,
    old_to_new: Dict[str, str],
    new_to_old: Dict[str, str],
    matches: List[Dict[str, Any]],
) -> None:
    for ref in sorted(set(baseline.cells) & set(candidate.cells), key=_ref_sort_key):
        if ref in old_to_new or ref in new_to_old:
            continue
        _add_match(ref, ref, "address", 1.0, old_to_new, new_to_old, matches)


def _add_match(
    old_ref: str,
    new_ref: str,
    matched_by: str,
    confidence: float,
    old_to_new: Dict[str, str],
    new_to_old: Dict[str, str],
    matches: List[Dict[str, Any]],
    semantic_id: Optional[str] = None,
) -> None:
    old_to_new[old_ref] = new_ref
    new_to_old[new_ref] = old_ref
    match = {
        "old_ref": old_ref,
        "new_ref": new_ref,
        "matched_by": matched_by,
        "confidence": round(confidence, 3),
    }
    if semantic_id:
        match["semantic_id"] = semantic_id
    matches.append(match)


def _unique_semantic_cells(snapshot: Any) -> Dict[str, Any]:
    buckets: Dict[str, List[Any]] = defaultdict(list)
    for cell in snapshot.cells.values():
        semantic_id = cell.semantic_id
        confidence = float(cell.semantic_identity.get("confidence") or 0)
        if not semantic_id or confidence < 0.7:
            continue
        buckets[semantic_id].append(cell)
    return {semantic_id: cells[0] for semantic_id, cells in buckets.items() if len(cells) == 1}


def _merge_nodes(existing: Optional[Dict[str, Any]], incoming: Dict[str, Any]) -> Dict[str, Any]:
    if existing is None:
        return incoming
    merged = dict(existing)
    for key, value in incoming.items():
        if key not in merged or merged[key] in {None, "", []}:
            merged[key] = value
    return merged


def _adjacency(edges: Sequence[Dict[str, Any]]) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = defaultdict(list)
    for edge in edges:
        result[edge["from"]].append(edge["to"])
    return dict(result)


def _reverse_adjacency(edges: Sequence[Dict[str, Any]]) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = defaultdict(list)
    for edge in edges:
        result[edge["to"]].append(edge["from"])
    return dict(result)


def _ref_sort_key(ref: str) -> Tuple[str, int, int, str]:
    sheet, address = split_cell_id(ref)
    try:
        row, col = coordinate_to_tuple(address)
    except Exception:
        row, col = 0, 0
    return sheet, row, col, ref
