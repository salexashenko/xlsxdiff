from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .alignment import build_structural_alignment, remap_graph_refs
from .formulas import (
    classify_formula_change,
    expand_reference_cells,
    formula_functions,
    formula_operators,
    numeric_constants,
    normalize_formula,
    parse_formula_references,
)
from .snapshot import parse_workbook
from .utils import display_scalar, is_number, safe_float, split_cell_id


DIRECT_ROOT_KINDS = {
    "cell_added",
    "cell_deleted",
    "constant_changed",
    "formula_changed",
    "formula_reference_changed",
    "formula_function_changed",
    "formula_operator_changed",
    "formula_constant_changed",
    "formula_named_range_changed",
    "formula_external_reference_changed",
    "formula_anchor_changed_only",
    "formula_text_changed",
    "formula_to_constant",
    "constant_to_formula",
    "defined_name_added",
    "defined_name_deleted",
    "defined_name_changed",
    "table_added",
    "table_deleted",
    "table_range_changed",
    "sheet_added",
    "sheet_deleted",
    "sheet_visibility_changed",
    "macro_presence_changed",
    "external_link_changed",
    "calculation_mode_changed",
}


def diff_workbooks(
    baseline_path: Path,
    candidate_path: Path,
    config: Optional[Dict[str, Any]] = None,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    config = config or {}
    options = options or {}
    baseline = parse_workbook(baseline_path, config=config, strict=bool(options.get("strict")))
    candidate = parse_workbook(candidate_path, config=config, strict=bool(options.get("strict")))
    if not options.get("include_hidden_sheets", True):
        baseline = _without_hidden_sheets(baseline)
        candidate = _without_hidden_sheets(candidate)
    return diff_snapshots(baseline, candidate, config=config, options=options)


def diff_snapshots(baseline: Any, candidate: Any, config: Optional[Dict[str, Any]] = None, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = config or {}
    options = options or {}
    max_expand = int(_config_value(config, "graph.max_range_expand_cells", options.get("max_range_expand_cells", 1000)))
    baseline_graph_raw = build_dependency_graph(baseline, max_range_expand_cells=max_expand)
    candidate_graph = build_dependency_graph(candidate, max_range_expand_cells=max_expand)
    alignment = build_structural_alignment(baseline, candidate)
    baseline_graph = remap_graph_refs(baseline_graph_raw, alignment["old_to_new"], edge_id_prefix="baseline_")

    changes: List[Dict[str, Any]] = []
    diagnostics: List[Dict[str, Any]] = []
    diagnostics.extend(_with_workbook_ref("baseline", baseline.diagnostics))
    diagnostics.extend(_with_workbook_ref("candidate", candidate.diagnostics))
    diagnostics.extend(_alignment_diagnostics(alignment))

    change_counter = 1
    change_counter = _diff_sheets(baseline, candidate, changes, change_counter)
    change_counter = _diff_defined_names(baseline, candidate, changes, change_counter)
    change_counter = _diff_tables(baseline, candidate, changes, change_counter)
    change_counter = _diff_workbook_file_info(baseline, candidate, changes, change_counter)
    change_counter = _diff_cells(baseline, candidate, alignment, changes, change_counter, options)

    root_refs = {change["object_ref"] for change in changes if change["directness"] == "direct" and change["scope"] == "cell"}
    old_reachable = downstream_nodes(root_refs, baseline_graph)
    new_reachable = downstream_nodes(root_refs, candidate_graph)
    all_reachable = old_reachable | new_reachable
    root_change_ids_by_ref = defaultdict(list)
    for change in changes:
        if change["directness"] == "direct":
            root_change_ids_by_ref[change["object_ref"]].append(change["id"])

    for change in changes:
        if change["kind"] != "cached_value_changed":
            continue
        if change["object_ref"] in all_reachable:
            change["directness"] = "propagated"
            change["confidence"] = min(change["confidence"], 0.85)
        else:
            change["directness"] = "unexplained"
            change["confidence"] = min(change["confidence"], 0.45)
            change["warnings"].append(
                {
                    "severity": "warning",
                    "code": "UNEXPLAINED_VALUE_CHANGE",
                    "message": "Cached value changed without a detected upstream direct change.",
                    "object_ref": change["object_ref"],
                }
            )

    for change in changes:
        change["materiality_score"] = materiality_score(change, candidate_graph, config)

    changes.sort(key=lambda item: (-item["materiality_score"], item["id"]))
    grouped_changes = group_changes(changes)
    impacted_outputs = build_impacted_outputs(changes, baseline, candidate, baseline_graph, candidate_graph, root_change_ids_by_ref)
    impact_dag = build_change_impact_dag(changes, impacted_outputs, candidate_graph, baseline_graph)

    diagnostics.append(
        {
            "severity": "info",
            "code": "CACHED_VALUE_MODE",
            "message": "This report uses cached formula results. Numeric output deltas assume both workbooks were saved after recalculation.",
        }
    )
    diagnostics.extend(_result_diagnostics(changes))

    summary = build_summary(changes, impacted_outputs, baseline, candidate, diagnostics, alignment)
    llm_summary = build_llm_summary(changes, impacted_outputs, grouped_changes, summary, diagnostics, config)
    summary["one_sentence_summary"] = llm_summary["one_sentence_summary"]
    direct_changes = [change for change in changes if change["directness"] == "direct"]
    unexplained_changes = [change for change in changes if change["directness"] == "unexplained"]

    return {
        "schema_version": "0.1",
        "baseline": baseline.file,
        "candidate": candidate.file,
        "summary": summary,
        "llm_summary": llm_summary,
        "changes": changes,
        "grouped_changes": grouped_changes,
        "dependency_graph_stats": {
            "baseline_node_count": len(baseline_graph_raw["nodes"]),
            "baseline_edge_count": len(baseline_graph_raw["edges"]),
            "aligned_baseline_node_count": len(baseline_graph["nodes"]),
            "aligned_baseline_edge_count": len(baseline_graph["edges"]),
            "candidate_node_count": len(candidate_graph["nodes"]),
            "candidate_edge_count": len(candidate_graph["edges"]),
        },
        "structural_alignment": _public_alignment(alignment),
        "change_impact_dag": impact_dag,
        "top_direct_changes": direct_changes[:25],
        "top_impacted_outputs": impacted_outputs[:25],
        "unexplained_changes": unexplained_changes[:50],
        "diagnostics": diagnostics,
        "_artifacts": {
            "baseline_snapshot": baseline.to_dict(),
            "candidate_snapshot": candidate.to_dict(),
            "structural_alignment": alignment,
            "candidate_graph": candidate_graph,
        },
    }


def build_dependency_graph(snapshot: Any, max_range_expand_cells: int = 1000) -> Dict[str, Any]:
    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []
    edge_seen: Set[Tuple[str, str, str, str]] = set()
    edge_counter = 1

    for ref, cell in snapshot.cells.items():
        nodes[ref] = _dependency_node(ref, cell)

    for formula_ref, cell in snapshot.cells.items():
        if cell.kind != "formula" or not cell.formula:
            continue
        for precedent in cell.formula.precedents:
            target = precedent["target"]
            edge_type = _edge_type(precedent["kind"])
            expanded_cells, expanded = expand_reference_cells(target, max_range_expand_cells)
            if expanded and expanded_cells:
                for precedent_ref in expanded_cells:
                    if precedent_ref not in nodes:
                        nodes[precedent_ref] = _placeholder_node(precedent_ref)
                    key = (precedent_ref, formula_ref, edge_type, precedent.get("raw", ""))
                    if key in edge_seen:
                        continue
                    edge_seen.add(key)
                    edges.append(
                        {
                            "id": f"e{edge_counter:06d}",
                            "from": precedent_ref,
                            "to": formula_ref,
                            "edge_type": edge_type,
                            "formula_ref": formula_ref,
                            "evidence": precedent.get("raw"),
                            "confidence": precedent.get("confidence", 1.0),
                        }
                    )
                    edge_counter += 1
            else:
                if target not in nodes:
                    nodes[target] = _range_or_external_node(target, precedent)
                key = (target, formula_ref, edge_type, precedent.get("raw", ""))
                if key in edge_seen:
                    continue
                edge_seen.add(key)
                edges.append(
                    {
                        "id": f"e{edge_counter:06d}",
                        "from": target,
                        "to": formula_ref,
                        "edge_type": edge_type,
                        "formula_ref": formula_ref,
                        "evidence": precedent.get("raw"),
                        "confidence": precedent.get("confidence", 1.0),
                    }
                )
                edge_counter += 1

    return {
        "nodes": nodes,
        "edges": edges,
        "adjacency": _adjacency(edges),
        "reverse_adjacency": _reverse_adjacency(edges),
    }


def downstream_nodes(root_refs: Iterable[str], graph: Dict[str, Any]) -> Set[str]:
    seen: Set[str] = set()
    queue = deque(root_refs)
    while queue:
        node = queue.popleft()
        for neighbor in graph["adjacency"].get(node, []):
            if neighbor in seen:
                continue
            seen.add(neighbor)
            queue.append(neighbor)
    return seen


def representative_path(root: str, target: str, graph: Dict[str, Any], max_depth: int = 20) -> Optional[Dict[str, Any]]:
    if root == target:
        return {"nodes": [root], "edge_ids": [], "confidence": 1.0}
    queue = deque([(root, [root], [], 1.0)])
    visited = {root}
    edge_lookup = defaultdict(list)
    for edge in graph["edges"]:
        edge_lookup[(edge["from"], edge["to"])].append(edge)
    while queue:
        node, path, edge_ids, confidence = queue.popleft()
        if len(path) > max_depth:
            continue
        for neighbor in graph["adjacency"].get(node, []):
            if neighbor in path:
                continue
            best_edge = edge_lookup[(node, neighbor)][0]
            next_edge_ids = edge_ids + [best_edge["id"]]
            next_confidence = min(confidence, best_edge.get("confidence", 1.0))
            if neighbor == target:
                return {"nodes": path + [neighbor], "edge_ids": next_edge_ids, "confidence": next_confidence}
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor], next_edge_ids, next_confidence))
    return None


def materiality_score(change: Dict[str, Any], graph: Dict[str, Any], config: Dict[str, Any]) -> float:
    score = 0.0
    role = change.get("semantic_role")
    if role == "output":
        score += 50
    elif role == "assumption":
        score += 40
    elif role == "raw_data":
        score += 12
    if change["kind"].startswith("formula_") or change["kind"] in {"formula_changed", "constant_to_formula", "formula_to_constant"}:
        score += 35
    if change.get("directness") == "propagated":
        score += 20
    if change.get("directness") == "unexplained":
        score += 18
    score += min(len(downstream_nodes([change["object_ref"]], graph)) * 0.5, 30)
    if change.get("delta"):
        delta = change["delta"]
        if delta.get("relative_delta") is not None:
            score += min(abs(delta["relative_delta"]) * 100, 25)
        score += min(abs(delta.get("absolute_delta", 0)) / 1000, 20)
    if change.get("visibility_context", {}).get("sheet_visible", True):
        score += 10
    else:
        score += 3
    if change.get("confidence", 1.0) < 0.6:
        score -= 20
    if change["kind"] == "style_changed":
        score -= 50
    return round(score, 3)


def group_changes(changes: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: List[Dict[str, Any]] = []
    counter = _add_modeling_step_groups(changes, groups, 1)
    buckets: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for change in changes:
        if change["scope"] != "cell":
            continue
        sheet = change.get("sheet_name") or split_cell_id(change["object_ref"])[0]
        family = _change_family(change)
        buckets[(sheet, family, change.get("semantic_role", "unknown"))].append(change)

    for (sheet, family, role), bucket in buckets.items():
        if len(bucket) < 3:
            continue
        refs = [change["object_ref"] for change in bucket]
        range_ref = _bounding_range(refs)
        if role == "raw_data" and len(bucket) >= 20:
            group_type = "raw_data_update"
        elif family == "formula":
            group_type = "formula_block"
        elif role == "assumption":
            group_type = "assumption_block"
        else:
            group_type = "contiguous_range"
        groups.append(
            {
                "id": f"grp_{counter:03d}",
                "group_type": group_type,
                "range_ref": range_ref,
                "label": f"{len(bucket)} {family} changes on {sheet}",
                "change_count": len(bucket),
                "representative_changes": [change["id"] for change in bucket[:5]],
                "summary": f"{len(bucket)} {family} changes detected in {range_ref}.",
                "materiality_score": round(sum(change.get("materiality_score", 0) for change in bucket) / len(bucket), 3),
            }
        )
        counter += 1
    groups.sort(key=lambda item: (-item["materiality_score"], item["id"]))
    return groups


def _add_modeling_step_groups(changes: Sequence[Dict[str, Any]], groups: List[Dict[str, Any]], counter: int) -> int:
    buckets: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for change in changes:
        if change.get("scope") != "cell" or change.get("kind") not in {"cell_added", "cell_deleted"}:
            continue
        identity = change.get("semantic_identity") or {}
        row_headers = identity.get("row_headers") or []
        label = row_headers[0] if row_headers else _best_label_from_change(change)
        if not label:
            continue
        sheet = change.get("sheet_name") or split_cell_id(change["object_ref"])[0]
        buckets[(sheet, change["kind"], label)].append(change)

    for (sheet, kind, label), bucket in sorted(buckets.items(), key=lambda item: (item[0], _ref_sort_key(item[1][0]["object_ref"]))):
        if len(bucket) < 2:
            continue
        inserted = kind == "cell_added"
        group_type = "modeling_step_inserted" if inserted else "modeling_step_deleted"
        verb = "Inserted" if inserted else "Deleted"
        groups.append(
            {
                "id": f"grp_{counter:03d}",
                "group_type": group_type,
                "range_ref": _bounding_range([change["object_ref"] for change in bucket]),
                "label": f"{verb} modeling step: {label}",
                "change_count": len(bucket),
                "representative_changes": [change["id"] for change in bucket[:5]],
                "summary": f"{verb} modeling step '{label}' on {sheet}.",
                "materiality_score": round(sum(change.get("materiality_score", 0) for change in bucket) / len(bucket), 3),
            }
        )
        counter += 1
    return counter


def build_impacted_outputs(
    changes: Sequence[Dict[str, Any]],
    baseline: Any,
    candidate: Any,
    baseline_graph: Dict[str, Any],
    candidate_graph: Dict[str, Any],
    root_change_ids_by_ref: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    roots = [change for change in changes if change["directness"] == "direct" and change["scope"] == "cell"]
    root_refs = [change["object_ref"] for change in roots]
    outputs: List[Dict[str, Any]] = []
    for change in changes:
        if change["scope"] != "cell":
            continue
        if change.get("semantic_role") != "output" and change.get("directness") not in {"propagated", "unexplained"}:
            continue
        if change["kind"] not in {"cached_value_changed", "formula_changed", "formula_reference_changed", "formula_function_changed", "formula_operator_changed", "formula_constant_changed", "formula_named_range_changed", "formula_text_changed", "constant_to_formula", "formula_to_constant"}:
            continue
        ref = change["object_ref"]
        upstream_ids: List[str] = []
        paths: List[Dict[str, Any]] = []
        path_confidences: List[float] = []
        for root in root_refs:
            path = representative_path(root, ref, candidate_graph) or representative_path(root, ref, baseline_graph)
            if not path:
                continue
            upstream_ids.extend(root_change_ids_by_ref.get(root, []))
            path_id = f"path_{len(paths) + 1:03d}_{len(outputs) + 1:03d}"
            paths.append(
                {
                    "id": path_id,
                    "from": root,
                    "to": ref,
                    "nodes": path["nodes"],
                    "edges": path["edge_ids"],
                    "collapsed": False,
                    "confidence": path["confidence"],
                }
            )
            path_confidences.append(path["confidence"])
        upstream_ids = sorted(set(upstream_ids))
        if change["directness"] == "unexplained" or not upstream_ids:
            strength = "unexplained"
        elif len(upstream_ids) == 1 and min(path_confidences or [1.0]) >= 0.85 and change["kind"] == "cached_value_changed":
            strength = "strong"
        elif min(path_confidences or [1.0]) >= 0.65:
            strength = "moderate"
        else:
            strength = "weak"

        old_ref = change.get("old_ref") or ref
        new_ref = change.get("new_ref") or ref
        old_cell = baseline.cells.get(old_ref)
        new_cell = candidate.cells.get(new_ref)
        outputs.append(
            {
                "ref": ref,
                "old_ref": old_ref,
                "new_ref": new_ref,
                "address_changed": bool(change.get("address_changed")),
                "semantic_id": change.get("semantic_id"),
                "label": _best_label_from_change(change),
                "old_value": old_cell.value.to_dict() if old_cell else None,
                "new_value": new_cell.value.to_dict() if new_cell else None,
                "delta": change.get("delta"),
                "upstream_change_ids": upstream_ids,
                "representative_paths": paths[:5],
                "explanation_strength": strength,
                "explanation": _output_explanation(ref, change, upstream_ids, strength),
                "materiality_score": change.get("materiality_score", 0),
                "semantic_role": change.get("semantic_role", "unknown"),
            }
        )
    outputs.sort(key=lambda item: (-item["materiality_score"], item["ref"]))
    return outputs


def build_change_impact_dag(
    changes: Sequence[Dict[str, Any]],
    impacted_outputs: Sequence[Dict[str, Any]],
    candidate_graph: Dict[str, Any],
    baseline_graph: Dict[str, Any],
) -> Dict[str, Any]:
    included_nodes: Set[str] = set()
    included_edges: Set[str] = set()
    roots = [change["object_ref"] for change in changes if change["directness"] == "direct" and change["scope"] == "cell"][:40]
    outputs = [output["ref"] for output in impacted_outputs[:40]]
    for output in impacted_outputs[:40]:
        for path in output.get("representative_paths", []):
            included_nodes.update(path["nodes"])
            included_edges.update(path["edges"])
    included_nodes.update(roots)
    included_nodes.update(outputs)

    graph_edges_by_id = {edge["id"]: edge for edge in candidate_graph["edges"]}
    graph_edges_by_id.update({edge["id"]: edge for edge in baseline_graph["edges"] if edge["id"] not in graph_edges_by_id})
    nodes = {}
    for node_id in included_nodes:
        node = candidate_graph["nodes"].get(node_id) or baseline_graph["nodes"].get(node_id) or _placeholder_node_dict(node_id)
        node = dict(node)
        node["changes"] = [change["id"] for change in changes if change["object_ref"] == node_id]
        nodes[node_id] = node
    edges = [graph_edges_by_id[edge_id] for edge_id in included_edges if edge_id in graph_edges_by_id]
    return {
        "roots": [root for root in roots if root in nodes],
        "outputs": [output for output in outputs if output in nodes],
        "nodes": nodes,
        "edges": edges,
        "collapsed_node_count": 0,
        "omitted_node_count": max(0, len(candidate_graph["nodes"]) - len(nodes)),
    }


def build_summary(
    changes: Sequence[Dict[str, Any]],
    impacted_outputs: Sequence[Dict[str, Any]],
    baseline: Any,
    candidate: Any,
    diagnostics: Sequence[Dict[str, Any]],
    alignment: Dict[str, Any],
) -> Dict[str, Any]:
    direct_count = sum(1 for change in changes if change["directness"] == "direct")
    propagated_count = sum(1 for change in changes if change["directness"] == "propagated")
    unexplained_count = sum(1 for change in changes if change["directness"] == "unexplained")
    warning_count = sum(1 for diagnostic in diagnostics if diagnostic.get("severity") == "warning")
    confidence = "high"
    if warning_count or unexplained_count:
        confidence = "medium"
    if any(diagnostic.get("severity") == "error" for diagnostic in diagnostics) or warning_count > 20:
        confidence = "low"
    one_sentence = (
        f"Detected {direct_count} direct changes, {propagated_count} propagated value changes, "
        f"and {unexplained_count} unexplained value changes."
    )
    alignment_summary = alignment.get("summary", {})
    return {
        "direct_change_count": direct_count,
        "propagated_change_count": propagated_count,
        "unexplained_change_count": unexplained_count,
        "structural_matches": alignment_summary.get("matched_cells", 0),
        "semantic_matches": alignment_summary.get("semantic_matches", 0),
        "shifted_semantic_matches": alignment_summary.get("shifted_semantic_matches", 0),
        "unmatched_old_cells": alignment_summary.get("unmatched_old_cells", 0),
        "unmatched_new_cells": alignment_summary.get("unmatched_new_cells", 0),
        "sheets_added": sum(1 for change in changes if change["kind"] == "sheet_added"),
        "sheets_deleted": sum(1 for change in changes if change["kind"] == "sheet_deleted"),
        "formulas_changed": sum(1 for change in changes if change["kind"].startswith("formula_") or change["kind"] == "formula_changed"),
        "constants_changed": sum(1 for change in changes if change["kind"] == "constant_changed"),
        "cached_values_changed": sum(1 for change in changes if change["kind"] == "cached_value_changed"),
        "outputs_changed": len(impacted_outputs),
        "has_macros": bool(baseline.file.get("has_macros") or candidate.file.get("has_macros")),
        "has_external_links": any(diagnostic.get("code") == "EXTERNAL_LINKS_DETECTED" for diagnostic in diagnostics),
        "has_opaque_formulas": any(diagnostic.get("code") == "OPAQUE_DYNAMIC_REFERENCE" for diagnostic in diagnostics),
        "confidence": confidence,
        "one_sentence_summary": one_sentence,
    }


def build_llm_summary(
    changes: Sequence[Dict[str, Any]],
    impacted_outputs: Sequence[Dict[str, Any]],
    grouped_changes: Sequence[Dict[str, Any]],
    summary: Dict[str, Any],
    diagnostics: Sequence[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    direct_changes = [change for change in changes if change.get("directness") == "direct"]
    top_direct = direct_changes[:8]
    configured_output_refs = _configured_output_refs(config or {})
    llm_ranked_outputs = sorted(
        impacted_outputs,
        key=lambda output: (
            0 if output.get("ref") in configured_output_refs else 1,
            _summary_output_priority(output.get("ref", "")),
            0 if output.get("semantic_role") == "output" else 1,
            -_output_path_length(output),
            -float(output.get("materiality_score") or 0),
            output.get("ref", ""),
        ),
    )
    top_outputs = list(llm_ranked_outputs[:8])
    warning_codes = sorted({diagnostic.get("code", "") for diagnostic in diagnostics if diagnostic.get("severity") == "warning" and diagnostic.get("code")})
    caveats = [
        "Uses cached workbook formula values; numeric deltas assume both workbooks were saved after recalculation.",
    ]
    if summary.get("unexplained_change_count"):
        caveats.append(f"{summary['unexplained_change_count']} changed value(s) had no detected upstream explanation.")
    if warning_codes:
        caveats.append("Warnings present: " + ", ".join(warning_codes) + ".")

    one_sentence = _llm_one_sentence(summary, top_direct, top_outputs)
    return {
        "schema_version": "0.1",
        "intended_use": "A compact, deterministic context object for LLMs to answer a user with one sentence plus optional evidence.",
        "one_sentence_summary": one_sentence,
        "confidence": summary.get("confidence", "unknown"),
        "counts": {
            "direct_changes": summary.get("direct_change_count", 0),
            "propagated_changes": summary.get("propagated_change_count", 0),
            "unexplained_changes": summary.get("unexplained_change_count", 0),
            "formula_changes": summary.get("formulas_changed", 0),
            "outputs_changed": summary.get("outputs_changed", 0),
            "shifted_semantic_matches": summary.get("shifted_semantic_matches", 0),
        },
        "top_direct_changes": [_llm_change_fact(change) for change in top_direct],
        "top_change_groups": [_llm_group_fact(group) for group in grouped_changes[:8]],
        "top_impacted_outputs": [_llm_output_fact(output) for output in top_outputs],
        "caveats": caveats,
        "safe_response_rules": [
            "Use the one_sentence_summary verbatim or paraphrase it without adding unsupported causality.",
            "Say 'likely explains' only when explanation_strength is strong.",
            "Say 'associated with' for moderate or weak paths.",
            "Always include cell references for material claims.",
        ],
    }


def _llm_one_sentence(summary: Dict[str, Any], top_direct: Sequence[Dict[str, Any]], top_outputs: Sequence[Dict[str, Any]]) -> str:
    if summary.get("direct_change_count", 0) == 0 and summary.get("propagated_change_count", 0) == 0 and summary.get("unexplained_change_count", 0) == 0:
        return "No workbook changes were detected."
    if top_outputs:
        output = top_outputs[0]
        output_ref = output.get("ref", "an output")
        output_label = output.get("label") or output_ref
        old_display = (output.get("old_value") or {}).get("display_value", "")
        new_display = (output.get("new_value") or {}).get("display_value", "")
        delta = _delta_text(output)
        strength = output.get("explanation_strength", "unknown")
        direct_phrase = _direct_change_phrase(top_direct)
        explanation = "likely explained by" if strength == "strong" else "associated with"
        if strength == "unexplained":
            explanation = "without a detected upstream explanation despite"
        return (
            f"{output_ref} {output_label} changed from {old_display or 'blank'} to {new_display or 'blank'}"
            f"{f' ({delta})' if delta else ''}, {explanation} {direct_phrase}; "
            f"{summary.get('unexplained_change_count', 0)} unexplained value changes were detected."
        )
    if top_direct:
        return (
            f"Detected {summary.get('direct_change_count', 0)} direct changes, led by {_change_short(top_direct[0])}, "
            f"with {summary.get('propagated_change_count', 0)} propagated value changes and "
            f"{summary.get('unexplained_change_count', 0)} unexplained value changes."
        )
    return (
        f"Detected {summary.get('direct_change_count', 0)} direct changes, "
        f"{summary.get('propagated_change_count', 0)} propagated value changes, and "
        f"{summary.get('unexplained_change_count', 0)} unexplained value changes."
    )


def _output_path_length(output: Dict[str, Any]) -> int:
    paths = output.get("representative_paths") or []
    if not paths:
        return 0
    return max(len(path.get("nodes", [])) for path in paths)


def _configured_output_refs(config: Dict[str, Any]) -> Set[str]:
    nested = config.get("workbook_diff", config)
    refs: Set[str] = set()
    for output in nested.get("outputs", []) or []:
        if isinstance(output, dict) and output.get("ref"):
            refs.add(output["ref"])
        elif isinstance(output, str):
            refs.add(output)
    return refs


def _summary_output_priority(ref: str) -> int:
    sheet, address = split_cell_id(ref)
    digits = "".join(ch for ch in address if ch.isdigit())
    row = int(digits) if digits else 10_000
    if sheet.upper() in {"SUMMARY", "DASHBOARD", "OUTPUT", "BOARD", "KPIS", "REPORT"} and row <= 15:
        return 0
    return 1


def _llm_change_fact(change: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": change.get("id"),
        "kind": change.get("kind"),
        "ref": change.get("object_ref"),
        "old_ref": change.get("old_ref"),
        "new_ref": change.get("new_ref"),
        "address_changed": change.get("address_changed"),
        "semantic_id": change.get("semantic_id"),
        "label": _best_label_from_change(change),
        "old": change.get("old_display"),
        "new": change.get("new_display"),
        "delta": _delta_text(change),
        "semantic_role": change.get("semantic_role"),
        "materiality_score": change.get("materiality_score"),
        "confidence": change.get("confidence"),
    }


def _llm_group_fact(group: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": group.get("id"),
        "group_type": group.get("group_type"),
        "label": group.get("label"),
        "range_ref": group.get("range_ref"),
        "change_count": group.get("change_count"),
        "summary": group.get("summary"),
        "materiality_score": group.get("materiality_score"),
    }


def _llm_output_fact(output: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ref": output.get("ref"),
        "old_ref": output.get("old_ref"),
        "new_ref": output.get("new_ref"),
        "address_changed": output.get("address_changed"),
        "semantic_id": output.get("semantic_id"),
        "label": output.get("label"),
        "old": (output.get("old_value") or {}).get("display_value"),
        "new": (output.get("new_value") or {}).get("display_value"),
        "delta": _delta_text(output),
        "explanation_strength": output.get("explanation_strength"),
        "upstream_change_ids": output.get("upstream_change_ids", []),
        "representative_paths": output.get("representative_paths", [])[:3],
        "explanation": output.get("explanation"),
    }


def _direct_change_phrase(top_direct: Sequence[Dict[str, Any]]) -> str:
    if not top_direct:
        return "the detected direct changes"
    if len(top_direct) == 1:
        return _change_short(top_direct[0])
    return f"{_change_short(top_direct[0])} and {len(top_direct) - 1} other top direct change(s)"


def _change_short(change: Dict[str, Any]) -> str:
    ref = change.get("object_ref", "a changed cell")
    label = _best_label_from_change(change)
    old_display = change.get("old_display", "")
    new_display = change.get("new_display", "")
    if label and label != ref:
        return f"{ref} {label} changing from {old_display or 'blank'} to {new_display or 'blank'}"
    return f"{ref} changing from {old_display or 'blank'} to {new_display or 'blank'}"


def _delta_text(item: Dict[str, Any]) -> str:
    delta = item.get("delta")
    if not delta:
        return ""
    parts = [delta.get("display_point_delta") or delta.get("display_delta"), delta.get("display_relative_delta")]
    return " / ".join(part for part in parts if part)


def _diff_sheets(baseline: Any, candidate: Any, changes: List[Dict[str, Any]], counter: int) -> int:
    old_by_name = {sheet["name"]: sheet for sheet in baseline.sheets}
    new_by_name = {sheet["name"]: sheet for sheet in candidate.sheets}
    for name in sorted(set(old_by_name) - set(new_by_name)):
        changes.append(_workbook_change(counter, "sheet_deleted", name, old_by_name[name], None))
        counter += 1
    for name in sorted(set(new_by_name) - set(old_by_name)):
        changes.append(_workbook_change(counter, "sheet_added", name, None, new_by_name[name]))
        counter += 1
    for name in sorted(set(old_by_name) & set(new_by_name)):
        if old_by_name[name]["visibility"] != new_by_name[name]["visibility"]:
            changes.append(_workbook_change(counter, "sheet_visibility_changed", name, old_by_name[name]["visibility"], new_by_name[name]["visibility"]))
            counter += 1
    return counter


def _diff_defined_names(baseline: Any, candidate: Any, changes: List[Dict[str, Any]], counter: int) -> int:
    old = {item["name"].upper(): item for item in baseline.defined_names}
    new = {item["name"].upper(): item for item in candidate.defined_names}
    for name in sorted(set(old) - set(new)):
        changes.append(_name_change(counter, "defined_name_deleted", old[name]["name"], old[name], None))
        counter += 1
    for name in sorted(set(new) - set(old)):
        changes.append(_name_change(counter, "defined_name_added", new[name]["name"], None, new[name]))
        counter += 1
    for name in sorted(set(old) & set(new)):
        if old[name].get("ref") != new[name].get("ref"):
            changes.append(_name_change(counter, "defined_name_changed", new[name]["name"], old[name].get("ref"), new[name].get("ref")))
            counter += 1
    return counter


def _diff_tables(baseline: Any, candidate: Any, changes: List[Dict[str, Any]], counter: int) -> int:
    old = {item["name"].upper(): item for item in baseline.tables}
    new = {item["name"].upper(): item for item in candidate.tables}
    for name in sorted(set(old) - set(new)):
        changes.append(_table_change(counter, "table_deleted", old[name]["name"], old[name], None))
        counter += 1
    for name in sorted(set(new) - set(old)):
        changes.append(_table_change(counter, "table_added", new[name]["name"], None, new[name]))
        counter += 1
    for name in sorted(set(old) & set(new)):
        if old[name].get("ref") != new[name].get("ref"):
            changes.append(_table_change(counter, "table_range_changed", new[name]["name"], old[name].get("ref"), new[name].get("ref")))
            counter += 1
    return counter


def _diff_workbook_file_info(baseline: Any, candidate: Any, changes: List[Dict[str, Any]], counter: int) -> int:
    if bool(baseline.file.get("has_macros")) != bool(candidate.file.get("has_macros")):
        changes.append(_workbook_change(counter, "macro_presence_changed", "workbook", baseline.file.get("has_macros"), candidate.file.get("has_macros")))
        counter += 1
    if baseline.file.get("calc_mode") != candidate.file.get("calc_mode"):
        changes.append(_workbook_change(counter, "calculation_mode_changed", "workbook", baseline.file.get("calc_mode"), candidate.file.get("calc_mode")))
        counter += 1
    return counter


def _diff_cells(
    baseline: Any,
    candidate: Any,
    alignment: Dict[str, Any],
    changes: List[Dict[str, Any]],
    counter: int,
    options: Dict[str, Any],
) -> int:
    old_sheet_names = [sheet["name"] for sheet in baseline.sheets]
    new_sheet_names = [sheet["name"] for sheet in candidate.sheets]
    for match in alignment["matches"]:
        old_cell = baseline.cells.get(match["old_ref"])
        new_cell = candidate.cells.get(match["new_ref"])
        if old_cell is None or new_cell is None:
            continue
        counter = _diff_matched_cell(old_cell, new_cell, old_sheet_names, new_sheet_names, alignment, changes, counter, options)

    for ref in alignment["unmatched_new_refs"]:
        new_cell = candidate.cells.get(ref)
        if new_cell is None:
            continue
        changes.append(_cell_change(counter, "cell_added", ref, None, new_cell.value.to_dict(), new_cell, None, new_cell, directness="direct"))
        counter += 1

    for ref in alignment["unmatched_old_refs"]:
        old_cell = baseline.cells.get(ref)
        if old_cell is None:
            continue
        changes.append(_cell_change(counter, "cell_deleted", ref, old_cell.value.to_dict(), None, old_cell, old_cell, None, directness="direct"))
        counter += 1
    return counter


def _diff_matched_cell(
    old_cell: Any,
    new_cell: Any,
    old_sheet_names: Sequence[str],
    new_sheet_names: Sequence[str],
    alignment: Dict[str, Any],
    changes: List[Dict[str, Any]],
    counter: int,
    options: Dict[str, Any],
) -> int:
    ref = new_cell.id
    if old_cell.kind != new_cell.kind:
        if old_cell.kind == "formula" and new_cell.kind == "constant":
            kind = "formula_to_constant"
        elif old_cell.kind == "constant" and new_cell.kind == "formula":
            kind = "constant_to_formula"
        else:
            kind = "cell_changed"
        changes.append(
            _cell_change(
                counter,
                kind,
                ref,
                _cell_payload(old_cell),
                _cell_payload(new_cell),
                new_cell,
                old_cell,
                new_cell,
                directness="direct",
            )
        )
        counter += 1
        return counter

    if old_cell.kind == "formula" and new_cell.kind == "formula":
        old_formula = old_cell.formula.raw if old_cell.formula else None
        new_formula = new_cell.formula.raw if new_cell.formula else None
        if normalize_formula(old_formula) != normalize_formula(new_formula):
            if not _formula_equal_after_alignment(old_formula, new_formula, old_cell, new_cell, old_sheet_names, new_sheet_names, alignment):
                formula_diff = classify_formula_change(old_formula, new_formula, new_cell.sheet_name, new_sheet_names)
                changes.append(
                    _cell_change(
                        counter,
                        formula_diff["kind"],
                        ref,
                        old_formula,
                        new_formula,
                        new_cell,
                        old_cell,
                        new_cell,
                        directness="direct",
                        evidence=[{"type": "formula_diff", **formula_diff}],
                    )
                )
                counter += 1
        elif _value_changed(old_cell.value.to_dict(), new_cell.value.to_dict()):
            changes.append(
                _cell_change(
                    counter,
                    "cached_value_changed",
                    ref,
                    old_cell.value.to_dict(),
                    new_cell.value.to_dict(),
                    new_cell,
                    old_cell,
                    new_cell,
                    directness="unexplained",
                )
            )
            counter += 1
    elif old_cell.kind == "constant" and new_cell.kind == "constant":
        if _value_changed(old_cell.value.to_dict(), new_cell.value.to_dict()):
            kind = "error_changed" if old_cell.value.value_type == "error" or new_cell.value.value_type == "error" else "constant_changed"
            changes.append(
                _cell_change(
                    counter,
                    kind,
                    ref,
                    old_cell.value.to_dict(),
                    new_cell.value.to_dict(),
                    new_cell,
                    old_cell,
                    new_cell,
                    directness="direct",
                )
            )
            counter += 1

    if options.get("include_style_changes") and old_cell.style != new_cell.style:
        changes.append(_cell_change(counter, "style_changed", ref, old_cell.style, new_cell.style, new_cell, old_cell, new_cell, directness="direct"))
        counter += 1
    if options.get("include_comments") and old_cell.comment != new_cell.comment:
        changes.append(_cell_change(counter, "comment_changed", ref, old_cell.comment, new_cell.comment, new_cell, old_cell, new_cell, directness="direct"))
        counter += 1
    if old_cell.hyperlink != new_cell.hyperlink:
        changes.append(_cell_change(counter, "hyperlink_changed", ref, old_cell.hyperlink, new_cell.hyperlink, new_cell, old_cell, new_cell, directness="direct"))
        counter += 1
    return counter


def _formula_equal_after_alignment(
    old_formula: Optional[str],
    new_formula: Optional[str],
    old_cell: Any,
    new_cell: Any,
    old_sheet_names: Sequence[str],
    new_sheet_names: Sequence[str],
    alignment: Dict[str, Any],
) -> bool:
    old_refs, _, _, _ = parse_formula_references(old_formula, old_cell.sheet_name, old_sheet_names)
    new_refs, _, _, _ = parse_formula_references(new_formula, new_cell.sheet_name, new_sheet_names)
    remapped_old_targets = sorted(_remap_formula_target(ref.target, alignment["old_to_new"]) for ref in old_refs)
    new_targets = sorted(ref.target for ref in new_refs)
    if remapped_old_targets != new_targets:
        return False
    return (
        formula_functions(old_formula or "") == formula_functions(new_formula or "")
        and numeric_constants(old_formula or "") == numeric_constants(new_formula or "")
        and formula_operators(old_formula or "") == formula_operators(new_formula or "")
    )


def _remap_formula_target(target: str, old_to_new: Dict[str, str]) -> str:
    if target in old_to_new:
        return old_to_new[target]
    if "!" not in target or ":" not in target:
        return target
    sheet, cells = split_cell_id(target)
    start, end = cells.split(":", 1)
    mapped_start = old_to_new.get(f"{sheet}!{start}")
    mapped_end = old_to_new.get(f"{sheet}!{end}")
    if not mapped_start or not mapped_end:
        return target
    mapped_start_sheet, mapped_start_address = split_cell_id(mapped_start)
    mapped_end_sheet, mapped_end_address = split_cell_id(mapped_end)
    if mapped_start_sheet != mapped_end_sheet:
        return target
    return f"{mapped_start_sheet}!{mapped_start_address}:{mapped_end_address}"


def _cell_change(
    counter: int,
    kind: str,
    ref: str,
    old: Any,
    new: Any,
    display_cell: Any,
    old_cell: Any,
    new_cell: Any,
    directness: str,
    evidence: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    old_value = old_cell.value.to_dict() if old_cell else None
    new_value = new_cell.value.to_dict() if new_cell else None
    delta = numeric_delta(old_value, new_value)
    evidence = list(evidence or [])
    display_identity = (display_cell.semantic_identity if display_cell else {}) or {}
    semantic_id = (display_cell.semantic_id if display_cell else None) or (old_cell.semantic_id if old_cell else None)
    old_ref = old_cell.id if old_cell else None
    new_ref = new_cell.id if new_cell else None
    semantic_role = display_cell.semantic_role if display_cell else "unknown"
    if semantic_role == "unknown" and old_cell is not None:
        semantic_role = old_cell.semantic_role
    if old_ref and new_ref and old_ref != new_ref:
        evidence.insert(
            0,
            {
                "type": "structural_alignment",
                "old_ref": old_ref,
                "new_ref": new_ref,
                "semantic_id": semantic_id,
                "confidence": display_identity.get("confidence"),
            },
        )
    return {
        "id": f"chg_{counter:04d}",
        "kind": kind,
        "scope": "cell",
        "object_ref": ref,
        "old_ref": old_ref,
        "new_ref": new_ref,
        "address_changed": bool(old_ref and new_ref and old_ref != new_ref),
        "semantic_id": semantic_id,
        "semantic_identity": display_identity,
        "sheet_name": display_cell.sheet_name if display_cell else split_cell_id(ref)[0],
        "range_ref": ref,
        "old": old,
        "new": new,
        "old_display": _display_from_value(old),
        "new_display": _display_from_value(new),
        "delta": delta,
        "labels": display_cell.labels if display_cell else [],
        "semantic_role": semantic_role,
        "directness": directness,
        "materiality_score": 0,
        "confidence": 0.95 if directness == "direct" else 0.7,
        "evidence": evidence,
        "warnings": [],
        "visibility_context": display_cell.visibility_context if display_cell else {},
    }


def _workbook_change(counter: int, kind: str, ref: str, old: Any, new: Any) -> Dict[str, Any]:
    return {
        "id": f"chg_{counter:04d}",
        "kind": kind,
        "scope": "workbook" if ref == "workbook" else "sheet",
        "object_ref": ref,
        "old": old,
        "new": new,
        "old_display": display_scalar(old),
        "new_display": display_scalar(new),
        "labels": [],
        "semantic_role": "metadata",
        "directness": "direct",
        "materiality_score": 0,
        "confidence": 0.95,
        "evidence": [],
        "warnings": [],
    }


def _name_change(counter: int, kind: str, ref: str, old: Any, new: Any) -> Dict[str, Any]:
    return {
        "id": f"chg_{counter:04d}",
        "kind": kind,
        "scope": "name",
        "object_ref": ref,
        "old": old,
        "new": new,
        "old_display": display_scalar(old),
        "new_display": display_scalar(new),
        "labels": [{"text": ref, "source": "defined_name", "confidence": 0.95}],
        "semantic_role": "unknown",
        "directness": "direct",
        "materiality_score": 0,
        "confidence": 0.9,
        "evidence": [],
        "warnings": [],
    }


def _table_change(counter: int, kind: str, ref: str, old: Any, new: Any) -> Dict[str, Any]:
    return {
        "id": f"chg_{counter:04d}",
        "kind": kind,
        "scope": "table",
        "object_ref": ref,
        "old": old,
        "new": new,
        "old_display": display_scalar(old),
        "new_display": display_scalar(new),
        "labels": [{"text": ref, "source": "table_header", "confidence": 0.85}],
        "semantic_role": "raw_data",
        "directness": "direct",
        "materiality_score": 0,
        "confidence": 0.9,
        "evidence": [],
        "warnings": [],
    }


def numeric_delta(old_value: Optional[Dict[str, Any]], new_value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not old_value or not new_value:
        return None
    old_number = safe_float(old_value.get("typed_value"))
    new_number = safe_float(new_value.get("typed_value"))
    if old_number is None or new_number is None:
        return None
    absolute_delta = new_number - old_number
    delta = {
        "old_number": old_number,
        "new_number": new_number,
        "absolute_delta": absolute_delta,
        "display_delta": _signed_number(absolute_delta),
    }
    if old_number != 0:
        relative = new_number / old_number - 1
        delta["relative_delta"] = relative
        delta["display_relative_delta"] = _signed_percent(relative)
    number_format = (new_value.get("number_format") or old_value.get("number_format") or "").lower()
    if "%" in number_format or (abs(old_number) <= 1 and abs(new_number) <= 1):
        delta["display_point_delta"] = _signed_number(absolute_delta * 100, suffix=" pp")
    return delta


def _value_changed(old: Dict[str, Any], new: Dict[str, Any]) -> bool:
    return old.get("typed_value") != new.get("typed_value") or old.get("value_type") != new.get("value_type")


def _cell_payload(cell: Any) -> Dict[str, Any]:
    payload = {"kind": cell.kind, "value": cell.value.to_dict()}
    if cell.formula:
        payload["formula"] = cell.formula.to_dict()
    return payload


def _dependency_node(ref: str, cell: Any) -> Dict[str, Any]:
    return {
        "id": ref,
        "ref": ref,
        "node_type": "cell",
        "label": _best_label(cell.labels, ref),
        "semantic_id": cell.semantic_id,
        "semantic_identity": cell.semantic_identity,
        "semantic_role": cell.semantic_role,
        "sheet_name": cell.sheet_name,
        "old_value": None,
        "new_value": cell.value.to_dict(),
        "old_formula": None,
        "new_formula": cell.formula.to_dict() if cell.formula else None,
        "changes": [],
        "materiality_score": 0,
        "confidence": 1.0 if not cell.formula or cell.formula.parse_status == "ok" else 0.6,
    }


def _placeholder_node(ref: str) -> Dict[str, Any]:
    return _placeholder_node_dict(ref)


def _placeholder_node_dict(ref: str) -> Dict[str, Any]:
    sheet, _ = split_cell_id(ref)
    return {
        "id": ref,
        "ref": ref,
        "node_type": "cell",
        "label": ref,
        "semantic_role": "unknown",
        "sheet_name": sheet or None,
        "changes": [],
        "materiality_score": 0,
        "confidence": 0.7,
    }


def _range_or_external_node(target: str, precedent: Dict[str, Any]) -> Dict[str, Any]:
    kind = precedent.get("kind", "range")
    node_type = "range"
    if kind == "external_reference":
        node_type = "external_reference"
    elif kind == "table_reference":
        node_type = "table_column"
    elif kind == "defined_name_reference":
        node_type = "defined_name"
    return {
        "id": target,
        "ref": target,
        "node_type": node_type,
        "label": target,
        "semantic_role": "unknown",
        "changes": [],
        "materiality_score": 0,
        "confidence": precedent.get("confidence", 0.7),
    }


def _adjacency(edges: Sequence[Dict[str, Any]]) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = defaultdict(list)
    for edge in edges:
        result[edge["from"]].append(edge["to"])
    return result


def _reverse_adjacency(edges: Sequence[Dict[str, Any]]) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = defaultdict(list)
    for edge in edges:
        result[edge["to"]].append(edge["from"])
    return result


def _edge_type(kind: str) -> str:
    if kind == "cell":
        return "cell_reference"
    if kind == "range":
        return "range_reference"
    if kind == "defined_name_reference":
        return "defined_name_reference"
    if kind == "table_reference":
        return "table_reference"
    if kind == "external_reference":
        return "external_reference"
    return "dynamic_reference"


def _alignment_diagnostics(alignment: Dict[str, Any]) -> List[Dict[str, Any]]:
    shifted = alignment.get("summary", {}).get("shifted_semantic_matches", 0)
    if not shifted:
        return []
    return [
        {
            "severity": "info",
            "code": "STRUCTURAL_ALIGNMENT_APPLIED",
            "message": f"{shifted} cell(s) were aligned by semantic row/column identity at shifted addresses.",
        }
    ]


def _public_alignment(alignment: Dict[str, Any]) -> Dict[str, Any]:
    shifted_matches = [match for match in alignment.get("matches", []) if match.get("old_ref") != match.get("new_ref")]
    return {
        "summary": alignment.get("summary", {}),
        "shifted_matches": shifted_matches[:100],
        "shifted_matches_omitted": max(0, len(shifted_matches) - 100),
    }


def _with_workbook_ref(which: str, diagnostics: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = []
    for diagnostic in diagnostics:
        item = dict(diagnostic)
        item.setdefault("details", {})
        item["details"] = dict(item["details"])
        item["details"]["workbook"] = which
        result.append(item)
    return result


def _result_diagnostics(changes: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    diagnostics = []
    for change in changes:
        diagnostics.extend(change.get("warnings", []))
    return diagnostics


def _display_from_value(value: Any) -> str:
    if isinstance(value, dict) and "display_value" in value:
        return value.get("display_value", "")
    if isinstance(value, dict) and "value" in value:
        return _display_from_value(value["value"])
    return display_scalar(value)


def _signed_number(value: float, suffix: str = "") -> str:
    sign = "+" if value > 0 else ""
    if abs(value) >= 1000:
        text = f"{value:,.0f}"
    elif abs(value) >= 10:
        text = f"{value:,.1f}"
    else:
        text = f"{value:,.2f}"
    return f"{sign}{text}{suffix}"


def _signed_percent(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value * 100:.1f}%"


def _change_family(change: Dict[str, Any]) -> str:
    if change["kind"].startswith("formula_") or change["kind"] in {"formula_changed", "constant_to_formula", "formula_to_constant"}:
        return "formula"
    if change["kind"] == "cached_value_changed":
        return "cached-value"
    if "constant" in change["kind"] or change["kind"] in {"cell_added", "cell_deleted"}:
        return "cell"
    return change["kind"].replace("_", " ")


def _bounding_range(refs: Sequence[str]) -> str:
    from openpyxl.utils.cell import coordinate_to_tuple, get_column_letter

    sheet_names = {split_cell_id(ref)[0] for ref in refs}
    if len(sheet_names) != 1:
        return f"{len(refs)} cells"
    sheet = next(iter(sheet_names))
    rows = []
    cols = []
    for ref in refs:
        _, address = split_cell_id(ref)
        try:
            row, col = coordinate_to_tuple(address)
            rows.append(row)
            cols.append(col)
        except Exception:
            pass
    if not rows or not cols:
        return f"{sheet}!{len(refs)} cells"
    start = f"{get_column_letter(min(cols))}{min(rows)}"
    end = f"{get_column_letter(max(cols))}{max(rows)}"
    return f"{sheet}!{start}" if start == end else f"{sheet}!{start}:{end}"


def _ref_sort_key(ref: str) -> Tuple[str, int, int, str]:
    from openpyxl.utils.cell import coordinate_to_tuple

    sheet, address = split_cell_id(ref)
    try:
        row, col = coordinate_to_tuple(address)
    except Exception:
        row, col = 0, 0
    return sheet, row, col, ref


def _best_label(labels: Sequence[Dict[str, Any]], fallback: str) -> str:
    if not labels:
        return fallback
    return max(labels, key=lambda item: item.get("confidence", 0)).get("text") or fallback


def _best_label_from_change(change: Dict[str, Any]) -> str:
    return _best_label(change.get("labels", []), change["object_ref"])


def _output_explanation(ref: str, change: Dict[str, Any], upstream_ids: Sequence[str], strength: str) -> str:
    if strength == "unexplained":
        return f"{ref} changed without a detected upstream explanation."
    if strength == "strong":
        return f"{ref} changed and has one detected upstream direct change on a dependency path; this likely explains the movement."
    if strength == "moderate":
        return f"{ref} changed and is associated with {len(upstream_ids)} upstream direct change(s)."
    return f"{ref} changed and may be related to {len(upstream_ids)} upstream direct change(s), but dependency evidence is partial."


def _config_value(config: Dict[str, Any], dotted_key: str, default: Any) -> Any:
    nested = config.get("workbook_diff", config)
    current: Any = nested
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def _without_hidden_sheets(snapshot: Any) -> Any:
    visible_sheets = {sheet["name"] for sheet in snapshot.sheets if sheet.get("visibility") == "visible"}
    if len(visible_sheets) == len(snapshot.sheets):
        return snapshot
    filtered_cells = {
        ref: cell
        for ref, cell in snapshot.cells.items()
        if cell.sheet_name in visible_sheets
    }
    filtered_tables = [table for table in snapshot.tables if table.get("sheet_name") in visible_sheets]
    filtered_names = []
    for name in snapshot.defined_names:
        ref = name.get("ref", "")
        if "!" not in ref or split_cell_id(ref)[0] in visible_sheets:
            filtered_names.append(name)
    diagnostics = list(snapshot.diagnostics)
    diagnostics.append(
        {
            "severity": "info",
            "code": "HIDDEN_SHEETS_IGNORED",
            "message": "Hidden and very-hidden sheets were excluded by request.",
        }
    )
    return type(snapshot)(
        schema_version=snapshot.schema_version,
        file=snapshot.file,
        sheets=[sheet for sheet in snapshot.sheets if sheet["name"] in visible_sheets],
        defined_names=filtered_names,
        tables=filtered_tables,
        external_links=snapshot.external_links,
        cells=filtered_cells,
        diagnostics=diagnostics,
    )
