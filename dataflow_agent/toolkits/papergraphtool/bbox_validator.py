"""
BBox Validator for Layout Constructor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

验证 layout_json 中 bbox 的有效性，作为 p2g_layout_constructor_agent 的 post tool。

主要检查：
1. nodes 之间的重叠检测
2. nodes 是否溢出 chunk 边界
3. chunks 是否溢出画布边界
4. nodes 的最小尺寸约束
5. nodes 的宽高比约束
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional
from dataflow_agent.logger import get_logger

log = get_logger(__name__)


# ==================== 配置参数 ====================
# 最小尺寸约束
MIN_NODE_WIDTH = 50      # 最小宽度 50px
MIN_NODE_HEIGHT = 30     # 最小高度 30px

# 宽高比约束
MIN_ASPECT_RATIO = 0.15  # 最小宽高比 (w/h)
MAX_ASPECT_RATIO = 15.0  # 最大宽高比 (w/h)

# 重叠阈值
OVERLAP_THRESHOLD = 0.15  # 重叠面积超过较小 node 面积的 15% 视为问题

# 边界溢出容忍度
BOUNDARY_TOLERANCE = 5   # 允许 5px 的溢出容忍


def _calculate_overlap_area(bbox1: Dict[str, int], bbox2: Dict[str, int]) -> int:
    """计算两个 bbox 的重叠面积。

    Args:
        bbox1: {x, y, w, h}
        bbox2: {x, y, w, h}

    Returns:
        重叠面积（像素）
    """
    x1, y1, w1, h1 = bbox1["x"], bbox1["y"], bbox1["w"], bbox1["h"]
    x2, y2, w2, h2 = bbox2["x"], bbox2["y"], bbox2["w"], bbox2["h"]

    # 计算重叠区域
    overlap_x = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))
    overlap_y = max(0, min(y1 + h1, y2 + h2) - max(y1, y2))

    return overlap_x * overlap_y


def _is_inside(inner: Dict[str, int], outer: Dict[str, int], tolerance: int = 0) -> Tuple[bool, Dict[str, int]]:
    """检查 inner bbox 是否在 outer bbox 内部。

    Args:
        inner: 内部 bbox {x, y, w, h}
        outer: 外部 bbox {x, y, w, h}
        tolerance: 容忍度（像素）

    Returns:
        (是否在内部, 溢出量字典 {left, right, top, bottom})
    """
    overflow = {
        "left": max(0, outer["x"] - inner["x"] - tolerance),
        "right": max(0, (inner["x"] + inner["w"]) - (outer["x"] + outer["w"]) - tolerance),
        "top": max(0, outer["y"] - inner["y"] - tolerance),
        "bottom": max(0, (inner["y"] + inner["h"]) - (outer["y"] + outer["h"]) - tolerance),
    }

    is_inside = all(v == 0 for v in overflow.values())
    return is_inside, overflow


def validate_layout_json(
    layout_json: Dict[str, Any],
    semantic_json: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    验证 layout_json 中所有 bbox 的有效性。

    Args:
        layout_json: 完整的 layout_json，结构为:
            {
                "canvas": {"width": 1920, "height": 1080},
                "positions": {
                    "chunks": [{"chunk_id": "c1", "bbox": {...}}, ...],
                    "nodes": [{"node_id": "n1", "bbox": {...}}, ...]
                }
            }
        semantic_json: 可选的语义 JSON，用于获取 node 所属的 chunk

    Returns:
        (is_valid, errors, metrics)
    """
    errors: List[str] = []
    warnings: List[str] = []

    canvas = layout_json.get("canvas", {})
    canvas_w = canvas.get("width", 1920)
    canvas_h = canvas.get("height", 1080)
    canvas_bbox = {"x": 0, "y": 0, "w": canvas_w, "h": canvas_h}

    positions = layout_json.get("positions", {})
    chunks = positions.get("chunks", [])
    nodes = positions.get("nodes", [])

    # 构建索引
    chunk_bboxes: Dict[str, Dict[str, int]] = {}
    for ch in chunks:
        chunk_id = ch.get("chunk_id")
        bbox = ch.get("bbox", {})
        if chunk_id and bbox:
            chunk_bboxes[chunk_id] = bbox

    node_bboxes: Dict[str, Dict[str, int]] = {}
    for nd in nodes:
        node_id = nd.get("node_id")
        bbox = nd.get("bbox", {})
        if node_id and bbox:
            node_bboxes[node_id] = bbox

    # 构建 node -> chunk 映射
    node_to_chunk: Dict[str, str] = {}
    if semantic_json:
        for node in semantic_json.get("nodes", []):
            node_id = node.get("node_id")
            chunk_id = node.get("chunk_id")
            if node_id and chunk_id:
                node_to_chunk[node_id] = chunk_id

    # ==================== 1. 检查 chunks 是否溢出画布 ====================
    chunk_overflow_issues = []
    for chunk_id, bbox in chunk_bboxes.items():
        is_inside, overflow = _is_inside(bbox, canvas_bbox, BOUNDARY_TOLERANCE)
        if not is_inside:
            total_overflow = sum(overflow.values())
            chunk_overflow_issues.append({
                "chunk_id": chunk_id,
                "overflow": overflow,
                "total_overflow_px": total_overflow,
            })
            errors.append(
                f"chunk {chunk_id} 溢出画布边界: "
                f"左={overflow['left']}px, 右={overflow['right']}px, "
                f"上={overflow['top']}px, 下={overflow['bottom']}px"
            )

    # ==================== 2. 检查 nodes 是否溢出所属 chunk ====================
    node_overflow_issues = []
    for node_id, bbox in node_bboxes.items():
        chunk_id = node_to_chunk.get(node_id)
        if not chunk_id:
            continue

        chunk_bbox = chunk_bboxes.get(chunk_id)
        if not chunk_bbox:
            continue

        is_inside, overflow = _is_inside(bbox, chunk_bbox, BOUNDARY_TOLERANCE)
        if not is_inside:
            total_overflow = sum(overflow.values())
            node_overflow_issues.append({
                "node_id": node_id,
                "chunk_id": chunk_id,
                "overflow": overflow,
                "total_overflow_px": total_overflow,
            })
            if total_overflow > 20:  # 超过 20px 才报错
                errors.append(
                    f"node {node_id} 溢出 chunk {chunk_id} 边界: "
                    f"总溢出={total_overflow}px"
                )
            else:
                warnings.append(
                    f"node {node_id} 轻微溢出 chunk {chunk_id} 边界: "
                    f"总溢出={total_overflow}px"
                )

    # ==================== 3. 检查 nodes 之间的重叠 ====================
    overlap_issues = []
    node_ids = list(node_bboxes.keys())

    for i in range(len(node_ids)):
        for j in range(i + 1, len(node_ids)):
            node_id1, node_id2 = node_ids[i], node_ids[j]
            bbox1, bbox2 = node_bboxes[node_id1], node_bboxes[node_id2]

            # 只检查同一 chunk 内的 nodes
            chunk1 = node_to_chunk.get(node_id1)
            chunk2 = node_to_chunk.get(node_id2)
            if chunk1 != chunk2:
                continue

            overlap_area = _calculate_overlap_area(bbox1, bbox2)
            if overlap_area > 0:
                area1 = bbox1["w"] * bbox1["h"]
                area2 = bbox2["w"] * bbox2["h"]
                smaller_area = min(area1, area2)
                overlap_ratio = overlap_area / smaller_area if smaller_area > 0 else 0

                if overlap_ratio > OVERLAP_THRESHOLD:
                    overlap_issues.append({
                        "node1": node_id1,
                        "node2": node_id2,
                        "chunk_id": chunk1,
                        "overlap_area": overlap_area,
                        "overlap_ratio": overlap_ratio,
                    })
                    errors.append(
                        f"node {node_id1} 与 {node_id2} 在 chunk {chunk1} 中重叠: "
                        f"重叠面积={overlap_area}px², 重叠比例={overlap_ratio:.1%}"
                    )

    # ==================== 4. 检查 nodes 的最小尺寸 ====================
    size_issues = []
    for node_id, bbox in node_bboxes.items():
        w, h = bbox["w"], bbox["h"]
        issues = []

        if w < MIN_NODE_WIDTH:
            issues.append(f"宽度 {w}px < {MIN_NODE_WIDTH}px")
        if h < MIN_NODE_HEIGHT:
            issues.append(f"高度 {h}px < {MIN_NODE_HEIGHT}px")

        if issues:
            size_issues.append({
                "node_id": node_id,
                "width": w,
                "height": h,
                "issues": issues,
            })
            warnings.append(f"node {node_id} 尺寸过小: {', '.join(issues)}")

    # ==================== 5. 检查 nodes 的宽高比 ====================
    aspect_ratio_issues = []
    for node_id, bbox in node_bboxes.items():
        w, h = bbox["w"], bbox["h"]
        aspect_ratio = w / h if h > 0 else float('inf')

        if aspect_ratio < MIN_ASPECT_RATIO:
            aspect_ratio_issues.append({
                "node_id": node_id,
                "aspect_ratio": aspect_ratio,
                "issue": "过于细高",
            })
            errors.append(
                f"node {node_id} 宽高比 {aspect_ratio:.2f} < {MIN_ASPECT_RATIO}，过于细高"
            )
        elif aspect_ratio > MAX_ASPECT_RATIO:
            aspect_ratio_issues.append({
                "node_id": node_id,
                "aspect_ratio": aspect_ratio,
                "issue": "过于细长",
            })
            errors.append(
                f"node {node_id} 宽高比 {aspect_ratio:.2f} > {MAX_ASPECT_RATIO}，过于细长"
            )

    # ==================== 6. 汇总结果 ====================
    metrics = {
        "canvas": {"width": canvas_w, "height": canvas_h},
        "chunk_count": len(chunks),
        "node_count": len(nodes),
        "issues": {
            "chunk_overflow": chunk_overflow_issues,
            "node_overflow": node_overflow_issues,
            "overlaps": overlap_issues,
            "size_violations": size_issues,
            "aspect_ratio_violations": aspect_ratio_issues,
        },
        "summary": {
            "chunk_overflow_count": len(chunk_overflow_issues),
            "node_overflow_count": len(node_overflow_issues),
            "overlap_count": len(overlap_issues),
            "size_violation_count": len(size_issues),
            "aspect_ratio_violation_count": len(aspect_ratio_issues),
            "total_errors": len(errors),
            "total_warnings": len(warnings),
        }
    }

    is_valid = len(errors) == 0

    # 日志输出
    if is_valid:
        log.info(
            "✓ layout_json bbox 验证通过: %d chunks, %d nodes, %d warnings",
            len(chunks), len(nodes), len(warnings)
        )
    else:
        log.warning(
            "✗ layout_json bbox 验证失败: %d errors, %d warnings",
            len(errors), len(warnings)
        )
        for err in errors[:5]:  # 只显示前5个错误
            log.warning("  - %s", err)

    return is_valid, errors + warnings, metrics


def generate_bbox_fix_suggestions(
    metrics: Dict[str, Any],
) -> List[str]:
    """
    根据验证指标生成修复建议。

    Args:
        metrics: validate_layout_json 返回的 metrics

    Returns:
        修复建议列表
    """
    suggestions: List[str] = []
    issues = metrics.get("issues", {})

    # 重叠问题建议
    overlaps = issues.get("overlaps", [])
    if overlaps:
        suggestions.append(
            f"发现 {len(overlaps)} 处 node 重叠，建议："
        )
        suggestions.append("  - 检查 node_layout_planner 的 rel_bbox 是否有重叠")
        suggestions.append("  - 考虑减少 chunk 内的 node 数量")
        suggestions.append("  - 调整 nodes 的相对位置或尺寸")

    # 溢出问题建议
    node_overflows = issues.get("node_overflow", [])
    if node_overflows:
        suggestions.append(
            f"发现 {len(node_overflows)} 个 node 溢出 chunk 边界，建议："
        )
        suggestions.append("  - 检查 rel_bbox 的 x+w 和 y+h 是否超过 1.0")
        suggestions.append("  - 减小 node 的相对尺寸")

    # 尺寸问题建议
    size_violations = issues.get("size_violations", [])
    if size_violations:
        suggestions.append(
            f"发现 {len(size_violations)} 个 node 尺寸过小，建议："
        )
        suggestions.append(f"  - 确保 node 宽度 >= {MIN_NODE_WIDTH}px")
        suggestions.append(f"  - 确保 node 高度 >= {MIN_NODE_HEIGHT}px")
        suggestions.append("  - 考虑合并过小的 nodes")

    # 宽高比问题建议
    ar_violations = issues.get("aspect_ratio_violations", [])
    if ar_violations:
        suggestions.append(
            f"发现 {len(ar_violations)} 个 node 宽高比异常，建议："
        )
        for v in ar_violations[:3]:
            node_id = v.get("node_id")
            issue = v.get("issue")
            ar = v.get("aspect_ratio", 0)
            if issue == "过于细长":
                suggestions.append(f"  - node {node_id}: 增加高度或减少宽度 (当前比例 {ar:.1f}:1)")
            else:
                suggestions.append(f"  - node {node_id}: 增加宽度或减少高度 (当前比例 1:{1/ar:.1f})")

    return suggestions
