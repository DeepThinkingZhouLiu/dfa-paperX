"""
Space Utilization Validator for Node Layout Planning
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

验证 chunk 内部 nodes 布局的空间利用率，作为 p2g_node_layout_planner_agent 的 post tool。

主要检查：
1. 空间利用率（nodes 总面积占 chunk 面积的比例）
2. 边缘留白（确保 nodes 不会过于集中在中心）
3. 单个 node 的宽高比约束
4. 单个 node 的最小尺寸约束
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple
from dataflow_agent.logger import get_logger

log = get_logger(__name__)


# ==================== 配置参数 ====================
# 空间利用率范围
MIN_UTILIZATION = 0.65  # 最小利用率 65%
MAX_UTILIZATION = 0.90  # 最大利用率 90%

# 边缘留白约束
MAX_LEFT_MARGIN = 0.20   # 左边缘最大留白
MAX_RIGHT_MARGIN = 0.20  # 右边缘最大留白（即 x+w 最小值为 1-0.12=0.88）
MAX_TOP_MARGIN = 0.20    # 上边缘最大留白
MAX_BOTTOM_MARGIN = 0.20 # 下边缘最大留白（即 y+h 最小值为 1-0.18=0.82）

# 单个 node 的约束
MIN_NODE_WIDTH = 0.10    # 最小宽度
MIN_NODE_HEIGHT = 0.10   # 最小高度
MIN_ASPECT_RATIO = 0.20  # 最小宽高比 (w/h)
MAX_ASPECT_RATIO = 8.0   # 最大宽高比 (w/h)


def validate_space_utilization(
    node_layout_plan: Dict[str, Any],
    strict: bool = False,
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    验证单个 chunk 的 node 布局空间利用率。

    Args:
        node_layout_plan: 单个 chunk 的布局计划，结构为:
            {
                "chunk_id": "c1",
                "nodes": [
                    {"node_id": "n1", "role": "...", "rel_bbox": {"x": 0.1, "y": 0.1, "w": 0.3, "h": 0.4}},
                    ...
                ]
            }
        strict: 是否严格模式（严格模式下警告也会导致验证失败）

    Returns:
        (is_valid, errors, metrics)
        - is_valid: 是否通过验证
        - errors: 错误/警告信息列表
        - metrics: 计算得到的指标字典
    """
    errors: List[str] = []
    warnings: List[str] = []

    chunk_id = node_layout_plan.get("chunk_id", "unknown")
    nodes = node_layout_plan.get("nodes", [])

    if not nodes:
        errors.append(f"chunk {chunk_id}: nodes 列表为空")
        return False, errors, {}

    # ==================== 1. 计算空间利用率 ====================
    total_area = 0.0
    min_x, min_y = 1.0, 1.0
    max_x_plus_w, max_y_plus_h = 0.0, 0.0

    node_metrics: List[Dict[str, Any]] = []

    for node in nodes:
        node_id = node.get("node_id", "unknown")
        rel_bbox = node.get("rel_bbox", {})

        x = rel_bbox.get("x", 0)
        y = rel_bbox.get("y", 0)
        w = rel_bbox.get("w", 0)
        h = rel_bbox.get("h", 0)

        # 计算面积
        area = w * h
        total_area += area

        # 更新边界
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x_plus_w = max(max_x_plus_w, x + w)
        max_y_plus_h = max(max_y_plus_h, y + h)

        # 计算宽高比
        aspect_ratio = w / h if h > 0 else float('inf')

        node_metrics.append({
            "node_id": node_id,
            "area": area,
            "aspect_ratio": aspect_ratio,
            "w": w,
            "h": h,
        })

        # ==================== 2. 检查单个 node 约束 ====================
        # 最小尺寸检查
        if w < MIN_NODE_WIDTH:
            warnings.append(
                f"chunk {chunk_id}, node {node_id}: 宽度 {w:.3f} < {MIN_NODE_WIDTH}，可能导致内容显示不全"
            )

        if h < MIN_NODE_HEIGHT:
            warnings.append(
                f"chunk {chunk_id}, node {node_id}: 高度 {h:.3f} < {MIN_NODE_HEIGHT}，可能导致内容显示不全"
            )

        # 宽高比检查
        if aspect_ratio < MIN_ASPECT_RATIO:
            errors.append(
                f"chunk {chunk_id}, node {node_id}: 宽高比 {aspect_ratio:.2f} < {MIN_ASPECT_RATIO}，节点过于细高"
            )
        elif aspect_ratio > MAX_ASPECT_RATIO:
            errors.append(
                f"chunk {chunk_id}, node {node_id}: 宽高比 {aspect_ratio:.2f} > {MAX_ASPECT_RATIO}，节点过于细长"
            )

    # ==================== 3. 检查空间利用率 ====================
    utilization = total_area

    if utilization < MIN_UTILIZATION:
        errors.append(
            f"chunk {chunk_id}: 空间利用率 {utilization:.1%} < {MIN_UTILIZATION:.0%}，"
            f"空白区域过多，建议扩大 nodes 尺寸或减少间距"
        )
    elif utilization > MAX_UTILIZATION:
        warnings.append(
            f"chunk {chunk_id}: 空间利用率 {utilization:.1%} > {MAX_UTILIZATION:.0%}，"
            f"布局可能过于拥挤"
        )

    # ==================== 4. 检查边缘留白 ====================
    left_margin = min_x
    right_margin = 1.0 - max_x_plus_w
    top_margin = min_y
    bottom_margin = 1.0 - max_y_plus_h

    if left_margin > MAX_LEFT_MARGIN:
        warnings.append(
            f"chunk {chunk_id}: 左边缘留白 {left_margin:.1%} > {MAX_LEFT_MARGIN:.0%}，"
            f"建议将 nodes 向左移动"
        )

    if right_margin > MAX_RIGHT_MARGIN:
        warnings.append(
            f"chunk {chunk_id}: 右边缘留白 {right_margin:.1%} > {MAX_RIGHT_MARGIN:.0%}，"
            f"建议将 nodes 向右扩展或移动"
        )

    if top_margin > MAX_TOP_MARGIN:
        warnings.append(
            f"chunk {chunk_id}: 上边缘留白 {top_margin:.1%} > {MAX_TOP_MARGIN:.0%}，"
            f"建议将 nodes 向上移动"
        )

    if bottom_margin > MAX_BOTTOM_MARGIN:
        warnings.append(
            f"chunk {chunk_id}: 下边缘留白 {bottom_margin:.1%} > {MAX_BOTTOM_MARGIN:.0%}，"
            f"建议将 nodes 向下扩展或移动"
        )

    # ==================== 5. 汇总结果 ====================
    metrics = {
        "chunk_id": chunk_id,
        "node_count": len(nodes),
        "total_area": total_area,
        "utilization": utilization,
        "margins": {
            "left": left_margin,
            "right": right_margin,
            "top": top_margin,
            "bottom": bottom_margin,
        },
        "bounding_box": {
            "min_x": min_x,
            "min_y": min_y,
            "max_x_plus_w": max_x_plus_w,
            "max_y_plus_h": max_y_plus_h,
        },
        "node_metrics": node_metrics,
    }

    # 合并 warnings 到 errors（如果是严格模式）
    all_issues = errors + (warnings if strict else [])

    is_valid = len(errors) == 0 if not strict else len(all_issues) == 0

    # 日志输出
    if is_valid:
        log.info(
            f"✓ chunk {chunk_id} 空间利用率验证通过: "
            f"利用率={utilization:.1%}, nodes={len(nodes)}"
        )
    else:
        log.warning(
            f"✗ chunk {chunk_id} 空间利用率验证失败: "
            f"利用率={utilization:.1%}, 错误数={len(errors)}, 警告数={len(warnings)}"
        )

    return is_valid, errors + warnings, metrics


def validate_all_chunks(
    node_layout_plan: Dict[str, Any],
    strict: bool = False,
) -> Tuple[bool, List[str], List[Dict[str, Any]]]:
    """
    验证所有 chunks 的空间利用率。

    Args:
        node_layout_plan: 完整的 node_layout_plan，结构为:
            {
                "chunks": [
                    {"chunk_id": "c1", "nodes": [...]},
                    {"chunk_id": "c2", "nodes": [...]},
                    ...
                ]
            }
        strict: 是否严格模式

    Returns:
        (all_valid, all_errors, all_metrics)
    """
    chunks = node_layout_plan.get("chunks", [])

    if not chunks:
        return False, ["node_layout_plan.chunks 为空"], []

    all_valid = True
    all_errors: List[str] = []
    all_metrics: List[Dict[str, Any]] = []

    for chunk_plan in chunks:
        is_valid, errors, metrics = validate_space_utilization(chunk_plan, strict=strict)

        if not is_valid:
            all_valid = False

        all_errors.extend(errors)
        all_metrics.append(metrics)

    # 汇总统计
    if all_metrics:
        avg_utilization = sum(m["utilization"] for m in all_metrics) / len(all_metrics)
        log.info(
            f"空间利用率验证完成: {len(chunks)} chunks, "
            f"平均利用率={avg_utilization:.1%}, "
            f"通过={all_valid}"
        )

    return all_valid, all_errors, all_metrics


def generate_improvement_suggestions(
    metrics: Dict[str, Any],
) -> List[str]:
    """
    根据验证指标生成改进建议。

    Args:
        metrics: validate_space_utilization 返回的 metrics

    Returns:
        改进建议列表
    """
    suggestions: List[str] = []

    chunk_id = metrics.get("chunk_id", "unknown")
    utilization = metrics.get("utilization", 0)
    margins = metrics.get("margins", {})
    node_metrics = metrics.get("node_metrics", [])

    # 利用率过低的建议
    if utilization < MIN_UTILIZATION:
        deficit = MIN_UTILIZATION - utilization
        suggestions.append(
            f"chunk {chunk_id}: 需要增加约 {deficit:.1%} 的面积覆盖。"
            f"可以通过以下方式实现："
        )

        # 找出最小的 nodes，建议扩大
        sorted_nodes = sorted(node_metrics, key=lambda x: x["area"])
        small_nodes = [n for n in sorted_nodes if n["area"] < 0.05]

        if small_nodes:
            node_ids = [n["node_id"] for n in small_nodes[:3]]
            suggestions.append(
                f"  - 扩大较小的 nodes: {', '.join(node_ids)}"
            )

        # 检查边缘留白
        if margins.get("left", 0) > 0.08 or margins.get("right", 0) > 0.08:
            suggestions.append(
                f"  - 减少左右边缘留白，将 nodes 向边缘扩展"
            )

        if margins.get("top", 0) > 0.10 or margins.get("bottom", 0) > 0.10:
            suggestions.append(
                f"  - 减少上下边缘留白，将 nodes 向边缘扩展"
            )

    # 宽高比异常的建议
    for nm in node_metrics:
        ar = nm.get("aspect_ratio", 1)
        if ar > MAX_ASPECT_RATIO:
            suggestions.append(
                f"chunk {chunk_id}, node {nm['node_id']}: "
                f"宽高比 {ar:.1f} 过大，建议增加高度或减少宽度"
            )
        elif ar < MIN_ASPECT_RATIO:
            suggestions.append(
                f"chunk {chunk_id}, node {nm['node_id']}: "
                f"宽高比 {ar:.2f} 过小，建议增加宽度或减少高度"
            )

    return suggestions


# ==================== LangChain Tool 包装 ====================
def create_space_utilization_validator_tool():
    """
    创建 LangChain Tool 实例，供 ToolManager 注册使用。
    """
    from langchain_core.tools import Tool

    def validate_layout(layout_json: str) -> str:
        """验证 node 布局的空间利用率"""
        import json

        try:
            layout = json.loads(layout_json)
        except json.JSONDecodeError as e:
            return f"JSON 解析失败: {e}"

        # 判断是单个 chunk 还是多个 chunks
        if "chunks" in layout:
            is_valid, errors, metrics = validate_all_chunks(layout)
        else:
            is_valid, errors, metrics = validate_space_utilization(layout)
            metrics = [metrics] if isinstance(metrics, dict) else metrics

        result = {
            "is_valid": is_valid,
            "errors": errors,
            "metrics_summary": {
                "chunk_count": len(metrics) if isinstance(metrics, list) else 1,
                "avg_utilization": (
                    sum(m["utilization"] for m in metrics) / len(metrics)
                    if metrics else 0
                ),
            }
        }

        # 生成改进建议
        if not is_valid and metrics:
            suggestions = []
            for m in (metrics if isinstance(metrics, list) else [metrics]):
                suggestions.extend(generate_improvement_suggestions(m))
            result["suggestions"] = suggestions

        return json.dumps(result, ensure_ascii=False, indent=2)

    return Tool(
        name="validate_space_utilization",
        description=(
            "验证 chunk 内部 nodes 布局的空间利用率。"
            "输入为 JSON 格式的 node_layout_plan（单个 chunk 或包含 chunks 数组）。"
            "返回验证结果、错误信息和改进建议。"
        ),
        func=validate_layout,
    )
