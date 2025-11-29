from __future__ import annotations

"""
Layout solver toolkit for PaperGraph.

Provides a unified entry `solve_layout` that attempts ELK-like precise layout.
If a real ELK integration is not available, falls back to a heuristic that:
- Clamps bboxes to canvas bounds
- Slightly shifts overlapping nodes (<= max_shift px)
- Ensures group bbox encloses its nodes and title_bbox sits at group top
- Generates orthogonal route_points based on flow and node centers

This module is intentionally dependency-light and self-contained.
You may later replace `solve_with_elk` with a true ELK binding.
"""

from typing import Any, Dict, List, Tuple


def clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _clamp_bbox(bbox: Dict[str, Any], cw: int, ch: int, default_w: int = 160, default_h: int = 64) -> Dict[str, int]:
    left = clamp(int(bbox.get("left", 0)), 0, cw - 1)
    top = clamp(int(bbox.get("top", 0)), 0, ch - 1)
    width = clamp(int(bbox.get("width", default_w)), 1, cw - left)
    height = clamp(int(bbox.get("height", default_h)), 1, ch - top)
    return {"left": left, "top": top, "width": width, "height": height}


def _bbox_overlap(a: Dict[str, int], b: Dict[str, int]) -> bool:
    return not (
        a["left"] + a["width"] <= b["left"]
        or b["left"] + b["width"] <= a["left"]
        or a["top"] + a["height"] <= b["top"]
        or b["top"] + b["height"] <= a["top"]
    )


def _shift_to_avoid_overlap(bboxes: List[Dict[str, int]], max_shift: int = 10) -> None:
    # naive n^2 micro-shift
    for i in range(len(bboxes)):
        for j in range(i + 1, len(bboxes)):
            a, b = bboxes[i], bboxes[j]
            if _bbox_overlap(a, b):
                # shift b by small amount to reduce overlap
                b["left"] += min(max_shift, a["width"] // 10)
                b["top"] += min(max_shift, a["height"] // 10)


def _center(b: Dict[str, int]) -> Tuple[int, int]:
    return (b["left"] + b["width"] // 2, b["top"] + b["height"] // 2)


def _orthogonal_route(src: Dict[str, int], tgt: Dict[str, int], flow: str) -> List[Dict[str, int]]:
    sx, sy = _center(src)
    tx, ty = _center(tgt)
    pts: List[Dict[str, int]] = []
    if flow == "top-to-bottom":
        # vertical then horizontal
        mid = {"x": sx, "y": ty}
        pts = [{"x": sx, "y": sy}, mid, {"x": tx, "y": ty}]
    else:  # default left-to-right
        # horizontal then vertical
        mid = {"x": tx, "y": sy}
        pts = [{"x": sx, "y": sy}, mid, {"x": tx, "y": ty}]
    return pts


def _group_bbox(nodes_in_group: List[Dict[str, Any]]) -> Dict[str, int]:
    if not nodes_in_group:
        return {"left": 0, "top": 0, "width": 1, "height": 1}
    lefts = [n["bbox"]["left"] for n in nodes_in_group]
    tops = [n["bbox"]["top"] for n in nodes_in_group]
    rights = [n["bbox"]["left"] + n["bbox"]["width"] for n in nodes_in_group]
    bottoms = [n["bbox"]["top"] + n["bbox"]["height"] for n in nodes_in_group]
    left, top = min(lefts), min(tops)
    width, height = max(rights) - left, max(bottoms) - top
    # add small padding
    pad = 8
    return {"left": left - pad, "top": top - pad, "width": width + 2 * pad, "height": height + 2 * pad}


def solve_with_elk(step1_positions: Dict[str, Any], semantic: Dict[str, Any], header_desc: Dict[str, Any]) -> Dict[str, Any]:
    """Call local Node elk_runner.js to produce refined positions via ELK.

    Requires that elkjs is available in node environment. We expect the runner
    to be installable in the project .venv (node usable), and callable via subprocess.
    """
    import json, subprocess, os
    runner = os.path.join(os.path.dirname(__file__), "elk_runner.js")
    payload = json.dumps({"semantic": semantic, "header": header_desc, "step1": {"positions": step1_positions}})
    # Ensure Node can resolve modules from project .venv/node_modules
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    node_path = os.path.join(root, ".venv", "node_modules")
    env = os.environ.copy()
    env["NODE_PATH"] = node_path
    proc = subprocess.run(["node", runner], input=payload.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8") or "ELK runner failed")
    out = json.loads(proc.stdout.decode("utf-8") or "{}")
    positions = out.get("positions", {})
    if not positions:
        raise RuntimeError("ELK runner returned empty positions")
    return positions


def solve_layout(
    step1_positions: Dict[str, Any],
    semantic_json_schema: Dict[str, Any],
    header_desc: Dict[str, Any] | None = None,
    max_shift: int = 10,
) -> Dict[str, Any]:
    """Return refined positions dict (ELK or heuristic).

    Args:
        step1_positions: positions from LLM
        semantic_json_schema: used for id alignment and graph structure
        header_desc: canvas/layout/grid info
        max_shift: max micro shift to avoid overlap
    """
    canvas = (header_desc or {}).get("canvas", {"width": 1920, "height": 1080})
    flow = (header_desc or {}).get("layout", {}).get("flow", "left-to-right")
    cw, ch = canvas.get("width", 1920), canvas.get("height", 1080)

    groups = step1_positions.get("groups", []) or []
    nodes = step1_positions.get("nodes", []) or []
    edges = step1_positions.get("edges", []) or []

    # Validate: must use existing groups (no new). If semantic has groups missing chunks -> error
    sem_groups = semantic_json_schema.get("groups", []) or []
    sem_group_ids = {g.get("group_id") for g in sem_groups}
    for g in groups:
        gid = g.get("group_id")
        if gid not in sem_group_ids:
            raise ValueError(f"unknown group in positions: {gid}")
    for sg in sem_groups:
        chunks = sg.get("chunks", []) or []
        if not chunks:
            raise ValueError(f"group {sg.get('group_id')} missing chunks in semantic layer")

    # Prefer ELK; if fails, raise error (no heuristic fallback per requirement)
    return solve_with_elk({"groups": groups, "nodes": nodes, "edges": edges}, semantic_json_schema, header_desc or {})
