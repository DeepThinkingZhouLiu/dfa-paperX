from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple


def _collect_ids(items: List[Dict[str, Any]], key: str) -> Tuple[bool, str]:
    seen: Set[str] = set()
    for it in items or []:
        v = it.get(key)
        if not isinstance(v, str) or not v:
            return False, f"missing or invalid '{key}' in item: {it}"
        if v in seen:
            return False, f"duplicated {key}: {v}"
        seen.add(v)
    return True, ""


def _index_by(items: List[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
    return {it.get(key): it for it in (items or []) if isinstance(it.get(key), str)}


def validate_semantic_schema(
    schema: Dict[str, Any],
    taxonomy: Dict[str, Any] | None = None,
    grid: Dict[str, Any] | None = None,
) -> Tuple[bool, List[str]]:
    """Lightweight validation for semantic_json_schema.

    Returns: (ok, errors)
    """
    errs: List[str] = []
    if not isinstance(schema, dict):
        return False, ["semantic_json_schema must be an object"]

    chunks = schema.get("chunks", [])
    groups = schema.get("groups", [])
    nodes = schema.get("nodes", [])
    edges = schema.get("edges", [])

    # required top-level keys
    for k in ("chunks", "groups", "nodes", "edges"):
        if k not in schema:
            errs.append(f"missing top-level key: {k}")

    # id uniqueness
    for items, key in ((chunks, "chunk_id"), (groups, "group_id"), (nodes, "node_id"), (edges, "edge_id")):
        ok, msg = _collect_ids(items, key)
        if not ok:
            errs.append(msg)

    chunk_index = _index_by(chunks, "chunk_id")
    node_index = _index_by(nodes, "node_id")

    # group->chunks reference
    for g in groups or []:
        for c in g.get("chunks", []) or []:
            if c not in chunk_index:
                errs.append(f"group {g.get('group_id')} references unknown chunk: {c}")

    # edges references
    for e in edges or []:
        s, t = e.get("source"), e.get("target")
        if s not in node_index:
            errs.append(f"edge {e.get('edge_id')} unknown source: {s}")
        if t not in node_index:
            errs.append(f"edge {e.get('edge_id')} unknown target: {t}")

    # port references
    for e in edges or []:
        sp, tp = e.get("source_port"), e.get("target_port")
        if sp or tp:
            src_node = node_index.get(e.get("source"))
            tgt_node = node_index.get(e.get("target"))
            if sp and not any(p.get("port_id") == sp for p in (src_node or {}).get("ports", [])):
                errs.append(f"edge {e.get('edge_id')} unknown source_port {sp} on node {e.get('source')}")
            if tp and not any(p.get("port_id") == tp for p in (tgt_node or {}).get("ports", [])):
                errs.append(f"edge {e.get('edge_id')} unknown target_port {tp} on node {e.get('target')}")

    # taxonomy checks
    tax_nodes = (taxonomy or {}).get("nodes", {})
    tax_edges = (taxonomy or {}).get("edges", {})
    node_types = set(tax_nodes.get("types", []) or [])
    node_roles = set(tax_nodes.get("roles", []) or [])
    edge_types = set(tax_edges.get("types", []) or [])
    multiplicities = set(((tax_edges.get("enums", {}) or {}).get("multiplicity", []) or []))
    port_dir_ok = {"input", "output"}

    for n in nodes or []:
        if node_types and n.get("type") not in node_types:
            errs.append(f"node {n.get('node_id')} invalid type: {n.get('type')}")
        if node_roles and n.get("role") not in node_roles:
            errs.append(f"node {n.get('node_id')} invalid role: {n.get('role')}")
        for p in n.get("ports", []) or []:
            if p.get("type") not in port_dir_ok:
                errs.append(f"node {n.get('node_id')} port {p.get('port_id')} invalid type: {p.get('type')}")

    for e in edges or []:
        if edge_types and e.get("type") not in edge_types:
            errs.append(f"edge {e.get('edge_id')} invalid type: {e.get('type')}")
        if multiplicities and e.get("multiplicity") and e.get("multiplicity") not in multiplicities:
            errs.append(f"edge {e.get('edge_id')} invalid multiplicity: {e.get('multiplicity')}")

    # grid checks
    if grid and isinstance(grid.get("rows"), int) and isinstance(grid.get("cols"), int):
        rows, cols = grid["rows"], grid["cols"]
        for ch in chunks or []:
            ga = ch.get("grid_area", {})
            r, c = ga.get("row"), ga.get("col")
            if not isinstance(r, int) or not isinstance(c, int) or r < 0 or c < 0 or r >= rows or c >= cols:
                errs.append(f"chunk {ch.get('chunk_id')} grid_area out of range: {ga} with rows={rows}, cols={cols}")

    return (len(errs) == 0), errs

