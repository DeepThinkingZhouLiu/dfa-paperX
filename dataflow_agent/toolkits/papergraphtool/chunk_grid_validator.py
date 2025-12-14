"""
Chunk Grid Validator for Layout Planning
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

验证 layout_plan 中 chunks 的网格位置是否存在冲突。

主要功能：
1. 检测 chunks 的 grid 位置是否重叠
2. 验证 span 区域是否超出网格边界
3. 生成冲突修复建议
"""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple
from dataflow_agent.logger import get_logger

log = get_logger(__name__)


def validate_chunk_grid_positions(
    layout_plan: Dict[str, Any],
) -> Tuple[bool, List[Dict[str, Any]], Dict[str, Any]]:
    """验证 layout_plan 中 chunks 的网格位置是否冲突。

    Args:
        layout_plan: 布局计划，结构为:
            {
                "global": {"grid_rows": 3, "grid_cols": 3, ...},
                "chunks": [
                    {"chunk_id": "c1", "row": 0, "col": 0, "span_row": 1, "span_col": 1},
                    ...
                ]
            }

    Returns:
        (has_conflict, conflict_info, metrics)
        - has_conflict: 是否存在冲突
        - conflict_info: 冲突详情列表
        - metrics: 统计指标
    """
    global_config = layout_plan.get("global", {})
    grid_rows = global_config.get("grid_rows", 3)
    grid_cols = global_config.get("grid_cols", 3)
    chunks = layout_plan.get("chunks", [])

    conflict_info: List[Dict[str, Any]] = []
    boundary_errors: List[Dict[str, Any]] = []

    # 记录每个网格单元被哪个 chunk 占用
    grid_occupancy: Dict[Tuple[int, int], str] = {}

    for chunk in chunks:
        chunk_id = chunk.get("chunk_id", "unknown")
        row = chunk.get("row", 0)
        col = chunk.get("col", 0)
        span_row = chunk.get("span_row", 1)
        span_col = chunk.get("span_col", 1)

        # 检查边界
        if row < 0 or row >= grid_rows:
            boundary_errors.append({
                "chunk_id": chunk_id,
                "error": f"row={row} 超出网格边界 [0, {grid_rows-1}]",
            })
            continue

        if col < 0 or col >= grid_cols:
            boundary_errors.append({
                "chunk_id": chunk_id,
                "error": f"col={col} 超出网格边界 [0, {grid_cols-1}]",
            })
            continue

        if row + span_row > grid_rows:
            boundary_errors.append({
                "chunk_id": chunk_id,
                "error": f"row={row} + span_row={span_row} = {row + span_row} 超出网格行数 {grid_rows}",
            })

        if col + span_col > grid_cols:
            boundary_errors.append({
                "chunk_id": chunk_id,
                "error": f"col={col} + span_col={span_col} = {col + span_col} 超出网格列数 {grid_cols}",
            })

        # 检查该 chunk 占用的所有单元格
        occupied_cells: List[Tuple[int, int]] = []
        for r in range(row, min(row + span_row, grid_rows)):
            for c in range(col, min(col + span_col, grid_cols)):
                cell = (r, c)
                occupied_cells.append(cell)

                if cell in grid_occupancy:
                    # 发现冲突
                    existing_chunk = grid_occupancy[cell]
                    conflict_info.append({
                        "chunk1": existing_chunk,
                        "chunk2": chunk_id,
                        "cell": cell,
                        "description": f"网格单元 ({r}, {c}) 被 {existing_chunk} 和 {chunk_id} 同时占用",
                    })
                    log.warning(
                        "网格冲突: 单元格 (%d, %d) 被 %s 和 %s 同时占用",
                        r, c, existing_chunk, chunk_id
                    )
                else:
                    grid_occupancy[cell] = chunk_id

    has_conflict = len(conflict_info) > 0 or len(boundary_errors) > 0

    # 计算网格利用率
    total_cells = grid_rows * grid_cols
    occupied_cells_count = len(grid_occupancy)
    utilization = occupied_cells_count / total_cells if total_cells > 0 else 0

    metrics = {
        "grid_rows": grid_rows,
        "grid_cols": grid_cols,
        "total_cells": total_cells,
        "occupied_cells": occupied_cells_count,
        "utilization": utilization,
        "chunk_count": len(chunks),
        "conflict_count": len(conflict_info),
        "boundary_error_count": len(boundary_errors),
        "has_conflict": has_conflict,
    }

    if has_conflict:
        log.error(
            "layout_plan 网格验证失败: %d 个冲突, %d 个边界错误",
            len(conflict_info), len(boundary_errors)
        )
    else:
        log.info(
            "layout_plan 网格验证通过: %d chunks, 利用率 %.1f%%",
            len(chunks), utilization * 100
        )

    # 合并边界错误到冲突信息
    all_issues = conflict_info + boundary_errors

    return has_conflict, all_issues, metrics


def generate_grid_fix_suggestions(
    conflict_info: List[Dict[str, Any]],
    metrics: Dict[str, Any],
) -> List[str]:
    """根据冲突信息生成修复建议。

    Args:
        conflict_info: validate_chunk_grid_positions 返回的冲突信息
        metrics: 验证指标

    Returns:
        修复建议列表
    """
    if not conflict_info:
        return []

    suggestions: List[str] = []
    grid_rows = metrics.get("grid_rows", 3)
    grid_cols = metrics.get("grid_cols", 3)

    # 分类处理冲突
    position_conflicts = [c for c in conflict_info if "cell" in c]
    boundary_errors = [c for c in conflict_info if "error" in c]

    if position_conflicts:
        suggestions.append(f"发现 {len(position_conflicts)} 处网格位置冲突：")

        # 找出冲突的 chunk 对
        conflict_pairs: Set[Tuple[str, str]] = set()
        for c in position_conflicts:
            pair = tuple(sorted([c["chunk1"], c["chunk2"]]))
            conflict_pairs.add(pair)

        for chunk1, chunk2 in list(conflict_pairs)[:5]:
            suggestions.append(f"  - {chunk1} 和 {chunk2} 占用了相同的网格单元")

        suggestions.append("建议：")
        suggestions.append("  - 调整其中一个 chunk 的 row/col 位置")
        suggestions.append("  - 减小 span_row 或 span_col 的值")
        suggestions.append(f"  - 当前网格大小为 {grid_rows}x{grid_cols}，考虑是否需要扩大")

    if boundary_errors:
        suggestions.append(f"发现 {len(boundary_errors)} 处边界错误：")
        for err in boundary_errors[:5]:
            suggestions.append(f"  - {err.get('chunk_id')}: {err.get('error')}")

        suggestions.append("建议：")
        suggestions.append(f"  - 确保所有 chunk 的位置在 [0, {grid_rows-1}] x [0, {grid_cols-1}] 范围内")
        suggestions.append("  - 确保 row + span_row <= grid_rows, col + span_col <= grid_cols")

    return suggestions


def visualize_grid_occupancy(
    layout_plan: Dict[str, Any],
) -> str:
    """生成网格占用情况的可视化字符串。

    Args:
        layout_plan: 布局计划

    Returns:
        ASCII 格式的网格可视化
    """
    global_config = layout_plan.get("global", {})
    grid_rows = global_config.get("grid_rows", 3)
    grid_cols = global_config.get("grid_cols", 3)
    chunks = layout_plan.get("chunks", [])

    # 构建网格
    grid: List[List[str]] = [["." for _ in range(grid_cols)] for _ in range(grid_rows)]

    for chunk in chunks:
        chunk_id = chunk.get("chunk_id", "?")
        row = chunk.get("row", 0)
        col = chunk.get("col", 0)
        span_row = chunk.get("span_row", 1)
        span_col = chunk.get("span_col", 1)

        # 使用 chunk_id 的最后一个字符作为标记
        marker = chunk_id[-1] if chunk_id else "?"

        for r in range(row, min(row + span_row, grid_rows)):
            for c in range(col, min(col + span_col, grid_cols)):
                if 0 <= r < grid_rows and 0 <= c < grid_cols:
                    if grid[r][c] == ".":
                        grid[r][c] = marker
                    else:
                        grid[r][c] = "X"  # 冲突标记

    # 生成可视化字符串
    lines = ["Grid Occupancy:"]
    lines.append("  " + " ".join(str(c) for c in range(grid_cols)))
    for r, row_data in enumerate(grid):
        lines.append(f"{r} " + " ".join(row_data))

    lines.append("")
    lines.append("Legend: . = empty, X = conflict, other = chunk marker")

    return "\n".join(lines)


# ==================== LangChain Tool 包装 ====================
def create_chunk_grid_validator_tool():
    """
    创建 LangChain Tool 实例，供 ToolManager 注册使用。
    """
    from langchain_core.tools import Tool
    import json

    def validate_grid(layout_plan_json: str) -> str:
        """验证 chunks 的网格位置是否冲突"""
        try:
            layout_plan = json.loads(layout_plan_json)
        except json.JSONDecodeError as e:
            return f"JSON 解析失败: {e}"

        has_conflict, conflict_info, metrics = validate_chunk_grid_positions(layout_plan)

        result = {
            "has_conflict": has_conflict,
            "conflict_count": len(conflict_info),
            "conflict_info": conflict_info,
            "metrics": metrics,
        }

        # 生成修复建议
        if has_conflict:
            result["suggestions"] = generate_grid_fix_suggestions(conflict_info, metrics)
            result["visualization"] = visualize_grid_occupancy(layout_plan)

        return json.dumps(result, ensure_ascii=False, indent=2)

    return Tool(
        name="validate_chunk_grid",
        description=(
            "验证 layout_plan 中 chunks 的网格位置是否存在冲突。"
            "输入为 JSON 格式的 layout_plan。"
            "返回冲突检测结果、冲突详情和修复建议。"
        ),
        func=validate_grid,
    )
