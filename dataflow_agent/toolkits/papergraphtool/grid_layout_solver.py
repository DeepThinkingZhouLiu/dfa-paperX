"""
Grid Layout Solver
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
基于 layout_plan 的 grid (row/col/span) 和 semantic_json 的内容权重，
计算每个 chunk 的 bbox（全局坐标）。
"""

from typing import Dict, Any, Tuple, List
from dataflow_agent.logger import get_logger

log = get_logger(__name__)


def compute_chunk_weight(
    chunk_id: str,
    chunk_nodes: List[Dict[str, Any]],
    chunk_summary: str = "",
) -> float:
    """
    计算 chunk 的内容权重，用于分配布局空间。
    
    权重计算规则：
    - 每个 node: +1.0
    - 每个非 annotation node: +1.5
    - summary 长度: +0.2 * (len/50)
    
    Args:
        chunk_id: chunk ID
        chunk_nodes: 该 chunk 包含的所有 nodes
        chunk_summary: chunk 的摘要文本
        
    Returns:
        权重值（float）
    """
    node_count = len(chunk_nodes)
    non_annot_count = sum(
        1 for n in chunk_nodes 
        if n.get("node_type") != "annotation"
    )
    summary_len = len(chunk_summary or "")
    
    weight = (
        1.0 * node_count +
        1.5 * non_annot_count +
        0.2 * (summary_len / 50.0)
    )
    
    return max(weight, 0.5)  # 最小权重 0.5，避免过小


def compute_chunk_bboxes(
    canvas_size: Tuple[int, int],
    layout_plan: Dict[str, Any],
    semantic_json: Dict[str, Any],
    outer_margin_x: int = 80,
    outer_margin_y: int = 60,
    cell_gap_x: int = 40,
    cell_gap_y: int = 40,
) -> Dict[str, Dict[str, int]]:
    """
    基于 layout_plan 的 grid 和 semantic_json 的内容权重，计算每个 chunk 的 bbox。
    
    算法步骤：
    1. 读取 grid 规模及 chunk 布局信息
    2. 基于 semantic_json 计算每个 chunk 的内容权重
    3. 汇总每行/列的权重
    4. 将权重映射到实际高度/宽度
    5. 为每个 chunk 计算全局坐标 bbox
    
    Args:
        canvas_size: (width, height) 画布尺寸
        layout_plan: 包含 global 和 chunks 的布局规划
        semantic_json: 语义结构 JSON
        outer_margin_x: 画布左右边距
        outer_margin_y: 画布上下边距
        cell_gap_x: 列间距
        cell_gap_y: 行间距
        
    Returns:
        {chunk_id: {"x": int, "y": int, "w": int, "h": int}}
    """
    canvas_w, canvas_h = canvas_size
    
    # 1. 读取 grid 规模及 chunk 布局
    global_info = layout_plan.get("global", {})
    chunks_layout = layout_plan.get("chunks", [])
    
    if not chunks_layout:
        log.warning("layout_plan.chunks 为空，返回空 bbox 字典")
        return {}
    
    # 推断 grid 规模
    grid_rows = global_info.get("grid_rows", 0)
    grid_cols = global_info.get("grid_cols", 0)
    
    if grid_rows <= 0 or grid_cols <= 0:
        # 从 chunks 中推断
        max_row = 0
        max_col = 0
        for chunk_layout in chunks_layout:
            r = chunk_layout.get("row", 0)
            c = chunk_layout.get("col", 0)
            r_span = chunk_layout.get("span_row", 1)
            c_span = chunk_layout.get("span_col", 1)
            max_row = max(max_row, r + r_span)
            max_col = max(max_col, c + c_span)
        grid_rows = max_row
        grid_cols = max_col
        log.info(f"从 chunks 推断 grid 规模: {grid_rows}x{grid_cols}")
    
    if grid_rows <= 0 or grid_cols <= 0:
        raise ValueError(f"无效的 grid 规模: {grid_rows}x{grid_cols}")
    
    # 2. 计算每个 chunk 的内容权重
    # 构建 chunk_id -> nodes 的映射
    chunk_nodes_map: Dict[str, List[Dict[str, Any]]] = {}
    for node in semantic_json.get("nodes", []):
        cid = node.get("chunk_id")
        if cid:
            if cid not in chunk_nodes_map:
                chunk_nodes_map[cid] = []
            chunk_nodes_map[cid].append(node)
    
    # 构建 chunk_id -> chunk_info 的映射
    chunk_info_map: Dict[str, Dict[str, Any]] = {}
    for chunk in semantic_json.get("chunks", []):
        cid = chunk.get("chunk_id")
        if cid:
            chunk_info_map[cid] = chunk
    
    # 计算权重
    chunk_weight: Dict[str, float] = {}
    for chunk_layout in chunks_layout:
        cid = chunk_layout.get("chunk_id")
        if not cid:
            continue
        
        nodes = chunk_nodes_map.get(cid, [])
        chunk_info = chunk_info_map.get(cid, {})
        summary = chunk_info.get("summary", "")
        
        weight = compute_chunk_weight(cid, nodes, summary)
        chunk_weight[cid] = weight
    
    # 3. 汇总到每一行/每一列的权重
    base_weight = 1.0  # 基础权重，避免为 0
    row_weight = [base_weight for _ in range(grid_rows)]
    col_weight = [base_weight for _ in range(grid_cols)]
    
    for chunk_layout in chunks_layout:
        cid = chunk_layout.get("chunk_id")
        if not cid or cid not in chunk_weight:
            continue
        
        w = chunk_weight[cid]
        r0 = chunk_layout.get("row", 0)
        c0 = chunk_layout.get("col", 0)
        r_span = chunk_layout.get("span_row", 1)
        c_span = chunk_layout.get("span_col", 1)
        r1 = r0 + r_span - 1
        c1 = c0 + c_span - 1
        
        # 把权重平均分配到覆盖的行/列
        row_span_count = r1 - r0 + 1
        col_span_count = c1 - c0 + 1
        
        for r in range(r0, min(r1 + 1, grid_rows)):
            row_weight[r] += w / row_span_count
        for c in range(c0, min(c1 + 1, grid_cols)):
            col_weight[c] += w / col_span_count
    
    # 4. 将行/列权重映射到实际高度/宽度
    avail_w = canvas_w - 2 * outer_margin_x - (grid_cols - 1) * cell_gap_x
    avail_h = canvas_h - 2 * outer_margin_y - (grid_rows - 1) * cell_gap_y
    
    # 最小尺寸
    min_row_h = 80
    min_col_w = 160
    
    base_rows_h = min_row_h * grid_rows
    base_cols_w = min_col_w * grid_cols
    
    extra_h = max(0, avail_h - base_rows_h)
    extra_w = max(0, avail_w - base_cols_w)
    
    sum_row_weight = sum(row_weight)
    sum_col_weight = sum(col_weight)
    
    # 计算每行高度和每列宽度
    row_heights = [
        min_row_h + extra_h * (w / sum_row_weight)
        for w in row_weight
    ]
    col_widths = [
        min_col_w + extra_w * (w / sum_col_weight)
        for w in col_weight
    ]
    
    # 累积出每一行/列的起始坐标
    row_tops = [outer_margin_y]
    for i in range(1, grid_rows):
        row_tops.append(row_tops[-1] + row_heights[i - 1] + cell_gap_y)
    
    col_lefts = [outer_margin_x]
    for j in range(1, grid_cols):
        col_lefts.append(col_lefts[-1] + col_widths[j - 1] + cell_gap_x)
    
    # 5. 为每个 chunk 计算 bbox
    chunk_bboxes: Dict[str, Dict[str, int]] = {}
    
    for chunk_layout in chunks_layout:
        cid = chunk_layout.get("chunk_id")
        if not cid:
            continue
        
        r0 = chunk_layout.get("row", 0)
        c0 = chunk_layout.get("col", 0)
        r_span = chunk_layout.get("span_row", 1)
        c_span = chunk_layout.get("span_col", 1)
        
        # 确保索引不越界
        if r0 >= grid_rows or c0 >= grid_cols:
            log.warning(f"chunk {cid} 的位置 ({r0}, {c0}) 超出 grid ({grid_rows}x{grid_cols})")
            continue
        
        x = col_lefts[c0]
        y = row_tops[r0]
        
        # 计算宽度：包含跨越的列及其间的 gap
        r1 = min(r0 + r_span, grid_rows)
        c1 = min(c0 + c_span, grid_cols)
        
        w = sum(col_widths[c0:c1]) + cell_gap_x * (c1 - c0 - 1)
        h = sum(row_heights[r0:r1]) + cell_gap_y * (r1 - r0 - 1)
        
        chunk_bboxes[cid] = {
            "x": int(x),
            "y": int(y),
            "w": int(max(w, 10)),  # 最小宽度 10
            "h": int(max(h, 10)),  # 最小高度 10
        }
    
    log.info(f"计算完成 {len(chunk_bboxes)} 个 chunk 的 bbox")
    return chunk_bboxes
