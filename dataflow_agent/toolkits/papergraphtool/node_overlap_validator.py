"""
Node Overlap Validator for Node Layout Planning
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

验证 chunk 内部 nodes 之间是否存在重叠，作为 p2g_node_layout_planner_agent 的验证工具。

主要功能：
1. 检测任意两个 node 的 rel_bbox 是否重叠
2. 计算重叠面积比例
3. 生成重叠修复建议
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple
from dataflow_agent.logger import get_logger

log = get_logger(__name__)


# ==================== 配置参数 ====================
# 重叠阈值：重叠面积占较小 node 面积的比例
OVERLAP_THRESHOLD = 0.10  # 超过 10% 视为重叠问题


def check_bbox_overlap(bbox1: Dict[str, float], bbox2: Dict[str, float]) -> float:
    """检查两个 rel_bbox 是否重叠，返回重叠面积比例。

    Args:
        bbox1: {x, y, w, h} 相对坐标 (0~1)
        bbox2: {x, y, w, h} 相对坐标 (0~1)

    Returns:
        重叠面积占较小 bbox 面积的比例 (0~1)
    """
    x1 = bbox1.get("x", 0)
    y1 = bbox1.get("y", 0)
    w1 = bbox1.get("w", 0)
    h1 = bbox1.get("h", 0)

    x2 = bbox2.get("x", 0)
    y2 = bbox2.get("y", 0)
    w2 = bbox2.get("w", 0)
    h2 = bbox2.get("h", 0)

    # 计算重叠区域
    overlap_x = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))
    overlap_y = max(0, min(y1 + h1, y2 + h2) - max(y1, y2))
    overlap_area = overlap_x * overlap_y

    if overlap_area == 0:
        return 0.0

    # 计算较小 bbox 的面积
    area1 = w1 * h1
    area2 = w2 * h2
    smaller_area = min(area1, area2) if min(area1, area2) > 0 else 1

    return overlap_area / smaller_area


def validate_nodes_overlap(
    chunk_layout: Dict[str, Any],
    threshold: float = OVERLAP_THRESHOLD,
) -> Tuple[bool, List[Dict[str, Any]], Dict[str, Any]]:
    """验证 chunk 内 nodes 是否存在重叠。

    Args:
        chunk_layout: chunk 布局结果，结构为:
            {
                "chunk_id": "c1",
                "nodes": [
                    {"node_id": "n1", "rel_bbox": {"x": 0.1, "y": 0.1, "w": 0.3, "h": 0.4}},
                    ...
                ]
            }
        threshold: 重叠比例阈值，超过此值视为重叠问题

    Returns:
        (has_overlap, overlap_info, metrics)
        - has_overlap: 是否存在重叠
        - overlap_info: 重叠详情列表
        - metrics: 统计指标
    """
    nodes = chunk_layout.get("nodes", [])
    chunk_id = chunk_layout.get("chunk_id", "unknown")

    overlap_info: List[Dict[str, Any]] = []
    total_checks = 0

    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            total_checks += 1
            node1 = nodes[i]
            node2 = nodes[j]

            bbox1 = node1.get("rel_bbox", {})
            bbox2 = node2.get("rel_bbox", {})

            if not bbox1 or not bbox2:
                continue

            overlap_ratio = check_bbox_overlap(bbox1, bbox2)

            if overlap_ratio > threshold:
                info = {
                    "node1": node1.get("node_id"),
                    "node2": node2.get("node_id"),
                    "overlap_ratio": overlap_ratio,
                    "bbox1": bbox1,
                    "bbox2": bbox2,
                }
                overlap_info.append(info)

                log.warning(
                    "chunk %s: nodes %s 和 %s 重叠，重叠比例 %.1f%%",
                    chunk_id,
                    info["node1"],
                    info["node2"],
                    overlap_ratio * 100,
                )

    has_overlap = len(overlap_info) > 0

    metrics = {
        "chunk_id": chunk_id,
        "node_count": len(nodes),
        "total_checks": total_checks,
        "overlap_count": len(overlap_info),
        "has_overlap": has_overlap,
    }

    if has_overlap:
        log.error(
            "chunk %s 存在 %d 对 nodes 重叠！",
            chunk_id,
            len(overlap_info),
        )
    else:
        log.info(
            "chunk %s 无 nodes 重叠，检查了 %d 对",
            chunk_id,
            total_checks,
        )

    return has_overlap, overlap_info, metrics


def validate_all_chunks_overlap(
    node_layout_plan: Dict[str, Any],
    threshold: float = OVERLAP_THRESHOLD,
) -> Tuple[bool, List[Dict[str, Any]], Dict[str, Any]]:
    """验证所有 chunks 的 nodes 重叠情况。

    Args:
        node_layout_plan: 完整的 node_layout_plan，结构为:
            {
                "chunks": [
                    {"chunk_id": "c1", "nodes": [...]},
                    {"chunk_id": "c2", "nodes": [...]},
                    ...
                ]
            }
        threshold: 重叠比例阈值

    Returns:
        (any_overlap, all_overlap_info, summary_metrics)
    """
    chunks = node_layout_plan.get("chunks", [])

    if not chunks:
        return False, [], {"error": "node_layout_plan.chunks 为空"}

    any_overlap = False
    all_overlap_info: List[Dict[str, Any]] = []
    chunk_metrics: List[Dict[str, Any]] = []

    for chunk_layout in chunks:
        has_overlap, overlap_info, metrics = validate_nodes_overlap(
            chunk_layout, threshold
        )

        if has_overlap:
            any_overlap = True
            all_overlap_info.extend(overlap_info)

        chunk_metrics.append(metrics)

    summary_metrics = {
        "chunk_count": len(chunks),
        "chunks_with_overlap": sum(1 for m in chunk_metrics if m["has_overlap"]),
        "total_overlap_pairs": len(all_overlap_info),
        "chunk_metrics": chunk_metrics,
    }

    return any_overlap, all_overlap_info, summary_metrics


def generate_overlap_fix_suggestions(
    overlap_info: List[Dict[str, Any]],
    chunk_id: str = "unknown",
) -> List[str]:
    """根据重叠信息生成修复建议。

    Args:
        overlap_info: validate_nodes_overlap 返回的 overlap_info
        chunk_id: chunk ID

    Returns:
        修复建议列表
    """
    if not overlap_info:
        return []

    suggestions: List[str] = [
        f"chunk {chunk_id} 存在 {len(overlap_info)} 对 nodes 重叠，建议："
    ]

    for info in overlap_info[:5]:  # 只处理前5对
        node1 = info["node1"]
        node2 = info["node2"]
        ratio = info["overlap_ratio"]
        bbox1 = info["bbox1"]
        bbox2 = info["bbox2"]

        # 分析重叠方向
        x1, y1, w1, h1 = bbox1["x"], bbox1["y"], bbox1["w"], bbox1["h"]
        x2, y2, w2, h2 = bbox2["x"], bbox2["y"], bbox2["w"], bbox2["h"]

        # 计算中心点
        cx1, cy1 = x1 + w1 / 2, y1 + h1 / 2
        cx2, cy2 = x2 + w2 / 2, y2 + h2 / 2

        # 判断相对位置
        if abs(cx1 - cx2) > abs(cy1 - cy2):
            # 水平方向重叠更多
            if cx1 < cx2:
                suggestions.append(
                    f"  - {node1} 和 {node2} 水平重叠 ({ratio:.0%})："
                    f"将 {node1} 左移或将 {node2} 右移"
                )
            else:
                suggestions.append(
                    f"  - {node1} 和 {node2} 水平重叠 ({ratio:.0%})："
                    f"将 {node2} 左移或将 {node1} 右移"
                )
        else:
            # 垂直方向重叠更多
            if cy1 < cy2:
                suggestions.append(
                    f"  - {node1} 和 {node2} 垂直重叠 ({ratio:.0%})："
                    f"将 {node1} 上移或将 {node2} 下移"
                )
            else:
                suggestions.append(
                    f"  - {node1} 和 {node2} 垂直重叠 ({ratio:.0%})："
                    f"将 {node2} 上移或将 {node1} 下移"
                )

    if len(overlap_info) > 5:
        suggestions.append(f"  - ... 还有 {len(overlap_info) - 5} 对重叠未列出")

    suggestions.append("  - 考虑减小 nodes 尺寸或重新规划布局")

    return suggestions


# ==================== LangChain Tool 包装 ====================
def create_node_overlap_validator_tool():
    """
    创建 LangChain Tool 实例，供 ToolManager 注册使用。
    """
    from langchain_core.tools import Tool
    import json

    def validate_overlap(layout_json: str) -> str:
        """验证 nodes 之间是否存在重叠"""
        try:
            layout = json.loads(layout_json)
        except json.JSONDecodeError as e:
            return f"JSON 解析失败: {e}"

        # 判断是单个 chunk 还是多个 chunks
        if "chunks" in layout:
            has_overlap, overlap_info, metrics = validate_all_chunks_overlap(layout)
        else:
            has_overlap, overlap_info, metrics = validate_nodes_overlap(layout)

        result = {
            "has_overlap": has_overlap,
            "overlap_count": len(overlap_info),
            "overlap_info": overlap_info,
            "metrics": metrics,
        }

        # 生成修复建议
        if has_overlap:
            chunk_id = layout.get("chunk_id", "unknown")
            result["suggestions"] = generate_overlap_fix_suggestions(
                overlap_info, chunk_id
            )

        return json.dumps(result, ensure_ascii=False, indent=2)

    return Tool(
        name="validate_nodes_overlap",
        description=(
            "验证 chunk 内部 nodes 之间是否存在重叠。"
            "输入为 JSON 格式的 node_layout_plan（单个 chunk 或包含 chunks 数组）。"
            "返回重叠检测结果、重叠详情和修复建议。"
        ),
        func=validate_overlap,
    )
