"""
ELK Node Layout Solver
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
使用 ELK (Eclipse Layout Kernel) 在 chunk 内部布局 nodes。

本模块基于 layout_solver.solve_layout 和 elk_runner.js, 不再提供
任何 fallback 布局；若 ELK 调用失败, 将直接抛出异常。
"""

from typing import Dict, Any, Optional, List, Set

from dataflow_agent.logger import get_logger
from dataflow_agent.toolkits.papergraphtool.layout_solver import solve_layout

log = get_logger(__name__)


def get_default_node_size(node_type: str) -> tuple[int, int]:
    """根据 node_type 返回默认的节点尺寸 (width, height)。"""
    size_map = {
        "text_block": (120, 40),
        "shape": (100, 80),
        "image_placeholder": (120, 120),
        "table_placeholder": (150, 100),
        "annotation": (80, 30),
    }
    return size_map.get(node_type, (100, 60))


def _collect_chunk_nodes(
    chunk_id: str,
    semantic_json: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """收集属于指定 chunk_id 的所有 nodes。"""
    return [
        n
        for n in (semantic_json.get("nodes", []) or [])
        if n.get("chunk_id") == chunk_id
    ]


def _collect_chunk_edges(
    node_ids: Set[str],
    semantic_json: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """从 semantic_json 中抽取与当前 chunk 相关的 edges, 并展开为
    {edge_id, source, target} 结构, 供 ELK 使用。
    """
    elk_edges: List[Dict[str, Any]] = []
    for e in (semantic_json.get("edges", []) or []):
        from_nodes = e.get("from", [])
        to_nodes = e.get("to", [])
        if isinstance(from_nodes, str):
            from_nodes = [from_nodes]
        if isinstance(to_nodes, str):
            to_nodes = [to_nodes]

        if not (
            any(n in node_ids for n in from_nodes)
            or any(n in node_ids for n in to_nodes)
        ):
            continue

        for f in from_nodes:
            for t in to_nodes:
                elk_edges.append(
                    {
                        "edge_id": e.get("edge_id", f"{f}-{t}"),
                        "source": f,
                        "target": t,
                    }
                )
    return elk_edges


def layout_nodes_in_chunk_with_elk(
    chunk_id: str,
    chunk_bbox: Dict[str, int],
    semantic_json: Dict[str, Any],
    elk_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, int]]:
    """使用 ELK 在 chunk_bbox 区域内布局属于 chunk_id 的 nodes。

    本函数不会使用任何 fallback 布局; 若 ELK 或 solve_layout 失败,
    将直接抛出异常, 由上游捕获并记录错误。
    """

    elk_config = elk_config or {}

    # 1. 提取当前 chunk 的 nodes
    nodes = _collect_chunk_nodes(chunk_id, semantic_json)
    if not nodes:
        log.info(f"chunk {chunk_id} has no nodes, skip ELK layout")
        return {}

    node_ids: Set[str] = {n["node_id"] for n in nodes if "node_id" in n}

    # 2. 提取相关 edges, 转为 ELK 期待的 {edge_id, source, target}
    elk_edges = _collect_chunk_edges(node_ids, semantic_json)

    # 3. 计算 chunk 内部可用画布
    padding_x = elk_config.get("inner_padding_x", 16)
    padding_y = elk_config.get("inner_padding_y", 16)

    inner_x = chunk_bbox["x"] + padding_x
    inner_y = chunk_bbox["y"] + padding_y
    inner_w = max(10, chunk_bbox["w"] - 2 * padding_x)
    inner_h = max(10, chunk_bbox["h"] - 2 * padding_y)

    # 4. 构造 semantic_json_schema 供 solve_layout 使用
    semantic_for_elk: Dict[str, Any] = {
        "groups": [
            {
                "group_id": chunk_id,
                "chunks": [chunk_id],
            }
        ],
        "edges": elk_edges,
    }

    # 5. 构造 step1.positions: 单一 group + 对应 nodes/edges
    step1_groups: List[Dict[str, Any]] = [
        {
            "group_id": chunk_id,
            "bbox": {
                "left": 0,
                "top": 0,
                "width": inner_w,
                "height": inner_h,
            },
            "chunk_id": chunk_id,
        }
    ]

    step1_nodes: List[Dict[str, Any]] = []
    for n in nodes:
        nid = n.get("node_id")
        if not nid:
            continue
        ntype = n.get("node_type", "shape")
        w, h = get_default_node_size(ntype)
        step1_nodes.append(
            {
                "node_id": nid,
                "bbox": {"left": 0, "top": 0, "width": w, "height": h},
                "group_id": chunk_id,
            }
        )

    step1_edges = elk_edges

    step1_positions = {
        "groups": step1_groups,
        "nodes": step1_nodes,
        "edges": step1_edges,
    }

    # 6. header_desc: 传递画布和 flow 信息
    header_desc: Dict[str, Any] = {
        "canvas": {"width": inner_w, "height": inner_h},
        "layout": {
            "flow": elk_config.get("flow_direction", "left-to-right"),
        },
    }

    # 7. 调用 solve_layout (内部调用 solve_with_elk -> elk_runner.js)
    positions = solve_layout(
        step1_positions=step1_positions,
        semantic_json_schema=semantic_for_elk,
        header_desc=header_desc,
        max_shift=0,
    )

    # 8. 从返回结果中提取 node bbox, 映射到全局坐标
    elk_nodes = positions.get("nodes", []) or []
    node_layout: Dict[str, Dict[str, int]] = {}

    for n in elk_nodes:
        nid = n.get("node_id")
        if not nid:
            continue
        bb = n.get("bbox", {}) or {}
        left = int(bb.get("left", 0))
        top = int(bb.get("top", 0))
        width = int(bb.get("width", 10))
        height = int(bb.get("height", 10))

        node_layout[nid] = {
            "x": inner_x + left,
            "y": inner_y + top,
            "w": width,
            "h": height,
        }

    log.info(f"ELK layout for chunk {chunk_id} produced {len(node_layout)} nodes")
    return node_layout

