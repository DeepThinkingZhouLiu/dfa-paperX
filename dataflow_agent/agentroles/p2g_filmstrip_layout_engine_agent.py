"""p2g_filmstrip_layout_engine_agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Film-Strip Pipeline Stage 6: Layout Engine Agent

基于真实素材尺寸和语义图结构，计算最终布局（纯计算，不调用 LLM）。

输入：
- state.node_graph_json: 节点图结构
- state.render_plan_json: 渲染计划
- state.vlm_node_assets: VLM 节点资产（含真实尺寸）
- state.pptx_render_specs: PPTX 节点规格

输出：
- state.layout_json: 布局结果 {canvas, positions: {nodes: [{node_id, bbox}]}, meta}
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from dataflow_agent.state import FilmStripP2GState
from dataflow_agent.logger import get_logger

log = get_logger(__name__)


# ============================================================================
# 配置参数
# ============================================================================
@dataclass
class LayoutConfig:
    """布局配置参数"""
    # 画布边距
    margin_x: int = 60
    margin_y: int = 60

    # 列间距和行间距
    col_gap: int = 90
    lane_gap: int = 100
    node_gap_y: int = 30

    # VLM 节点目标高度
    vlm_input_height: int = 240
    vlm_output_height: int = 240
    vlm_other_height: int = 160

    # PPTX 节点默认尺寸
    pptx_default_width: int = 180
    pptx_default_height: int = 70
    pptx_min_height: int = 50

    # 泳道关键词
    top_keywords: List[str] = field(default_factory=lambda: [
        "class", "classification", "label", "supervision", "loss", "logit", "token", "cls"
    ])
    bottom_keywords: List[str] = field(default_factory=lambda: [
        "pseudo", "cluster", "clustering", "memory", "bank", "prototype", "update"
    ])

    # 碰撞消解
    max_collision_iterations: int = 80

    # 画布利用率
    min_utilization: float = 0.3
    max_utilization: float = 0.85


# ============================================================================
# 数据结构
# ============================================================================
@dataclass
class NodeInfo:
    """节点信息"""
    node_id: str
    label: str = ""
    role: str = "process"
    render_method: str = "pptx"

    # 尺寸
    width: int = 0
    height: int = 0

    # 布局属性
    rank: int = 0
    lane: str = "mid"  # top / mid / bottom
    anchor: Optional[str] = None
    is_spine: bool = False

    # 最终坐标
    x: int = 0
    y: int = 0


@dataclass
class EdgeInfo:
    """边信息"""
    edge_id: str
    from_node: str
    to_node: str
    edge_type: str = "data_flow"


# ============================================================================
# Layout Engine 核心类
# ============================================================================
class LayoutEngine:
    """布局引擎"""

    def __init__(self, config: Optional[LayoutConfig] = None):
        self.config = config or LayoutConfig()
        self.nodes: Dict[str, NodeInfo] = {}
        self.edges: List[EdgeInfo] = []
        self.adjacency: Dict[str, List[str]] = defaultdict(list)  # from -> [to]
        self.reverse_adj: Dict[str, List[str]] = defaultdict(list)  # to -> [from]
        self.spine: List[str] = []

    def compute_layout(
        self,
        node_graph_json: Dict[str, Any],
        render_plan_json: Dict[str, Any],
        vlm_node_assets: Dict[str, Any],
        pptx_render_specs: Dict[str, Any],
        canvas_width: int = 1920,
        canvas_height: int = 1080,
    ) -> Dict[str, Any]:
        """计算布局

        Returns:
            layout_json 结构
        """
        # Step 1: Build Graph Index
        self._build_graph_index(node_graph_json, render_plan_json)

        # Step 2: Size Solver
        self._solve_sizes(vlm_node_assets, pptx_render_specs, render_plan_json)

        # Step 3: Structure Planner (spine, rank, lane, anchor)
        self._plan_structure(node_graph_json)

        # Step 4: Box Layout Solver
        self._solve_layout(canvas_width, canvas_height)

        # Step 5: Collision Resolution
        self._resolve_collisions(canvas_width, canvas_height)

        # Step 6: Fit to Canvas
        scale = self._fit_to_canvas(canvas_width, canvas_height)

        # Step 7: Emit layout_json
        return self._emit_layout_json(canvas_width, canvas_height, scale)

    # ========================================================================
    # Step 1: Build Graph Index
    # ========================================================================
    def _build_graph_index(
        self,
        node_graph_json: Dict[str, Any],
        render_plan_json: Dict[str, Any],
    ):
        """构建图索引"""
        # 解析节点
        for node in node_graph_json.get("nodes", []):
            node_id = node["node_id"]
            render_method = render_plan_json.get("by_node", {}).get(node_id, {}).get("render_method", "pptx")

            self.nodes[node_id] = NodeInfo(
                node_id=node_id,
                label=node.get("label", ""),
                role=node.get("role", "process"),
                render_method=render_method,
            )

        # 解析边（只使用 data_flow）
        for edge in node_graph_json.get("edges", []):
            edge_type = edge.get("edge_type", "data_flow")
            from_node = edge.get("from", "")
            to_node = edge.get("to", "")

            if from_node and to_node:
                self.edges.append(EdgeInfo(
                    edge_id=edge.get("edge_id", ""),
                    from_node=from_node,
                    to_node=to_node,
                    edge_type=edge_type,
                ))

                if edge_type == "data_flow":
                    self.adjacency[from_node].append(to_node)
                    self.reverse_adj[to_node].append(from_node)

        log.info(f"[LayoutEngine] Built index: {len(self.nodes)} nodes, {len(self.edges)} edges")

    # ========================================================================
    # Step 2: Size Solver
    # ========================================================================
    def _solve_sizes(
        self,
        vlm_node_assets: Dict[str, Any],
        pptx_render_specs: Dict[str, Any],
        render_plan_json: Dict[str, Any],
    ):
        """求解节点尺寸"""
        # 按 group 分组 VLM 节点
        group_nodes: Dict[str, List[str]] = defaultdict(list)
        for node_id, asset in vlm_node_assets.items():
            group_id = asset.get("source_group_id", "")
            if group_id:
                group_nodes[group_id].append(node_id)

        # VLM 节点尺寸
        for node_id, asset in vlm_node_assets.items():
            if node_id not in self.nodes:
                continue

            node = self.nodes[node_id]
            intrinsic_w = asset.get("width_px", 200)
            intrinsic_h = asset.get("height_px", 200)

            # 根据 role 确定目标高度
            if node.role == "input":
                target_h = self.config.vlm_input_height
            elif node.role == "output":
                target_h = self.config.vlm_output_height
            else:
                target_h = self.config.vlm_other_height

            # 等比缩放
            if intrinsic_h > 0:
                scale = target_h / intrinsic_h
                node.width = int(intrinsic_w * scale)
                node.height = target_h
            else:
                node.width = 200
                node.height = target_h

        # PPTX 节点尺寸
        by_node = render_plan_json.get("by_node", {})
        for node_id, node in self.nodes.items():
            if node.render_method != "pptx":
                continue

            # 优先使用 size_hint
            size_hint = by_node.get(node_id, {}).get("size_hint", {})
            spec = pptx_render_specs.get(node_id, {})

            w = size_hint.get("w_px", 0)
            h = size_hint.get("h_px", 0)

            # 如果没有 size_hint，使用默认值
            if w <= 0:
                w = self.config.pptx_default_width
            if h <= 0:
                h = self.config.pptx_default_height

            # 确保最小高度
            h = max(h, self.config.pptx_min_height)

            node.width = w
            node.height = h

        log.info(f"[LayoutEngine] Solved sizes for {len(self.nodes)} nodes")

    # ========================================================================
    # Step 3: Structure Planner
    # ========================================================================
    def _plan_structure(self, node_graph_json: Dict[str, Any]):
        """规划结构：spine, rank, lane, anchor"""
        # 3.1 识别主干 (spine)
        self._find_spine()

        # 3.2 计算 rank
        self._compute_ranks()

        # 3.3 计算 anchor
        self._compute_anchors()

        # 3.4 分配 lane
        self._assign_lanes(node_graph_json)

        log.info(f"[LayoutEngine] Structure: spine={self.spine}, lanes assigned")

    def _find_spine(self):
        """识别主干路径（最长加权路径）"""
        # 找入口节点
        inputs = [nid for nid, n in self.nodes.items()
                  if n.role == "input" or not self.reverse_adj[nid]]

        if not inputs:
            inputs = list(self.nodes.keys())[:1]

        # 找出口节点
        outputs = [nid for nid, n in self.nodes.items()
                   if n.role == "output" or not self.adjacency[nid]]

        # DP 找最长路径
        best_path = []
        best_score = -1

        for start in inputs:
            # BFS/DFS 找所有路径到 outputs
            paths = self._find_all_paths(start, set(outputs))
            for path in paths:
                score = self._score_path(path)
                if score > best_score:
                    best_score = score
                    best_path = path

        self.spine = best_path
        for nid in self.spine:
            if nid in self.nodes:
                self.nodes[nid].is_spine = True

        log.debug(f"[LayoutEngine] Spine: {self.spine} (score={best_score})")

    def _find_all_paths(
        self,
        start: str,
        targets: Set[str],
        max_paths: int = 100,
    ) -> List[List[str]]:
        """找从 start 到 targets 的所有路径"""
        paths = []
        stack = [(start, [start], set([start]))]

        while stack and len(paths) < max_paths:
            node, path, visited = stack.pop()

            if node in targets:
                paths.append(path)
                continue

            for next_node in self.adjacency[node]:
                if next_node not in visited:
                    stack.append((next_node, path + [next_node], visited | {next_node}))

        # 如果没找到到 targets 的路径，返回最长的路径
        if not paths:
            paths = [self._find_longest_path_from(start)]

        return paths

    def _find_longest_path_from(self, start: str) -> List[str]:
        """从 start 开始找最长路径"""
        best_path = [start]
        stack = [(start, [start], set([start]))]

        while stack:
            node, path, visited = stack.pop()
            if len(path) > len(best_path):
                best_path = path

            for next_node in self.adjacency[node]:
                if next_node not in visited:
                    stack.append((next_node, path + [next_node], visited | {next_node}))

        return best_path

    def _score_path(self, path: List[str]) -> int:
        """计算路径得分"""
        score = 0
        for nid in path:
            node = self.nodes.get(nid)
            if not node:
                continue
            if node.role == "process":
                score += 2
            elif node.role == "output":
                score += 1
            elif node.role == "aux":
                score -= 1
            else:
                score += 1
        return score

    def _compute_ranks(self):
        """计算 rank（拓扑排序层级）"""
        # 初始化
        rank = {nid: 0 for nid in self.nodes}

        # 拓扑排序 DP
        in_degree = {nid: len(self.reverse_adj[nid]) for nid in self.nodes}
        queue = [nid for nid, deg in in_degree.items() if deg == 0]

        while queue:
            node = queue.pop(0)
            for next_node in self.adjacency[node]:
                rank[next_node] = max(rank[next_node], rank[node] + 1)
                in_degree[next_node] -= 1
                if in_degree[next_node] == 0:
                    queue.append(next_node)

        # 应用 rank
        for nid, r in rank.items():
            if nid in self.nodes:
                self.nodes[nid].rank = r

        log.debug(f"[LayoutEngine] Ranks: {rank}")

    def _compute_anchors(self):
        """计算锚点"""
        for nid, node in self.nodes.items():
            if node.is_spine:
                continue

            anchor = None

            # VLM input: anchor = 下游
            if node.role == "input" and node.render_method == "vlm":
                downstream = self.adjacency.get(nid, [])
                for d in downstream:
                    if d in self.nodes and self.nodes[d].role == "process":
                        anchor = d
                        break
                if not anchor and downstream:
                    anchor = downstream[0]

            # VLM output: anchor = 上游
            elif node.role == "output" and node.render_method == "vlm":
                upstream = self.reverse_adj.get(nid, [])
                for u in upstream:
                    if u in self.nodes and self.nodes[u].role == "process":
                        anchor = u
                        break
                if not anchor and upstream:
                    anchor = upstream[0]

            # aux: anchor = 相连的 process
            elif node.role == "aux":
                candidates = self.reverse_adj.get(nid, []) + self.adjacency.get(nid, [])
                for c in candidates:
                    if c in self.nodes and self.nodes[c].role == "process":
                        anchor = c
                        break
                if not anchor and candidates:
                    anchor = candidates[0]

            # 其他非 spine 节点
            else:
                upstream = self.reverse_adj.get(nid, [])
                if upstream:
                    anchor = upstream[0]

            node.anchor = anchor

    def _assign_lanes(self, node_graph_json: Dict[str, Any]):
        """分配泳道"""
        for nid, node in self.nodes.items():
            # spine 强制 mid
            if node.is_spine:
                node.lane = "mid"
                continue

            # 计算关键词得分
            text = (node.label + " " +
                    self._get_semantic_desc(nid, node_graph_json)).lower()

            top_score = sum(1 for kw in self.config.top_keywords if kw in text)
            bottom_score = sum(1 for kw in self.config.bottom_keywords if kw in text)

            if top_score > bottom_score:
                node.lane = "top"
            elif bottom_score > top_score:
                node.lane = "bottom"
            elif node.anchor and node.anchor in self.nodes:
                # 继承 anchor 的 lane
                node.lane = self.nodes[node.anchor].lane
            else:
                node.lane = "mid"

    def _get_semantic_desc(self, node_id: str, node_graph_json: Dict[str, Any]) -> str:
        """获取节点的语义描述"""
        for node in node_graph_json.get("nodes", []):
            if node.get("node_id") == node_id:
                return node.get("semantic_desc", "")
        return ""

    # ========================================================================
    # Step 4: Box Layout Solver
    # ========================================================================
    def _solve_layout(self, canvas_width: int, canvas_height: int):
        """求解布局坐标"""
        cfg = self.config

        # 按 rank 分组
        rank_nodes: Dict[int, List[str]] = defaultdict(list)
        for nid, node in self.nodes.items():
            rank_nodes[node.rank].append(nid)

        max_rank = max(rank_nodes.keys()) if rank_nodes else 0

        # 计算每列宽度
        col_widths = {}
        for r in range(max_rank + 1):
            nodes_in_rank = rank_nodes.get(r, [])
            if nodes_in_rank:
                col_widths[r] = max(self.nodes[nid].width for nid in nodes_in_rank)
            else:
                col_widths[r] = 100

        # 计算列起始 x
        col_x = {}
        x = cfg.margin_x
        for r in range(max_rank + 1):
            col_x[r] = x
            x += col_widths[r] + cfg.col_gap

        # 计算 lane 基线 y
        mid_y = canvas_height * 0.5
        top_y = mid_y - cfg.lane_gap - 100
        bottom_y = mid_y + cfg.lane_gap + 100

        lane_y = {
            "top": top_y,
            "mid": mid_y,
            "bottom": bottom_y,
        }

        # 按 lane 和 rank 分组
        lane_rank_nodes: Dict[str, Dict[int, List[str]]] = {
            "top": defaultdict(list),
            "mid": defaultdict(list),
            "bottom": defaultdict(list),
        }

        for nid, node in self.nodes.items():
            lane_rank_nodes[node.lane][node.rank].append(nid)

        # 放置节点
        for lane in ["top", "mid", "bottom"]:
            base_y = lane_y[lane]

            for r in range(max_rank + 1):
                nodes_in_cell = lane_rank_nodes[lane].get(r, [])
                if not nodes_in_cell:
                    continue

                # 计算该 cell 内节点的总高度
                total_h = sum(self.nodes[nid].height for nid in nodes_in_cell)
                total_h += cfg.node_gap_y * (len(nodes_in_cell) - 1)

                # 从 base_y 开始垂直居中排列
                start_y = base_y - total_h / 2

                for nid in nodes_in_cell:
                    node = self.nodes[nid]

                    # x: 列内居中
                    node.x = col_x[r] + (col_widths[r] - node.width) // 2

                    # y
                    node.y = int(start_y)
                    start_y += node.height + cfg.node_gap_y

    # ========================================================================
    # Step 5: Collision Resolution
    # ========================================================================
    def _resolve_collisions(self, canvas_width: int, canvas_height: int):
        """碰撞消解"""
        cfg = self.config

        for iteration in range(cfg.max_collision_iterations):
            collision_found = False

            node_list = list(self.nodes.values())
            for i, n1 in enumerate(node_list):
                for n2 in node_list[i+1:]:
                    if self._check_overlap(n1, n2):
                        collision_found = True
                        self._resolve_overlap(n1, n2)

            if not collision_found:
                log.debug(f"[LayoutEngine] Collision resolved in {iteration + 1} iterations")
                break
        else:
            log.warning(f"[LayoutEngine] Collision not fully resolved after {cfg.max_collision_iterations} iterations")

    def _check_overlap(self, n1: NodeInfo, n2: NodeInfo) -> bool:
        """检查两个节点是否重叠"""
        gap = 10  # 最小间隙

        return not (
            n1.x + n1.width + gap <= n2.x or
            n2.x + n2.width + gap <= n1.x or
            n1.y + n1.height + gap <= n2.y or
            n2.y + n2.height + gap <= n1.y
        )

    def _resolve_overlap(self, n1: NodeInfo, n2: NodeInfo):
        """解决重叠"""
        # 优先移动非 spine 节点
        if n1.is_spine and not n2.is_spine:
            mover = n2
            fixed = n1
        elif n2.is_spine and not n1.is_spine:
            mover = n1
            fixed = n2
        else:
            # 都是或都不是 spine，移动 rank 更大的
            mover = n1 if n1.rank > n2.rank else n2
            fixed = n2 if n1.rank > n2.rank else n1

        # 计算重叠量
        overlap_y = (min(fixed.y + fixed.height, mover.y + mover.height) -
                     max(fixed.y, mover.y))

        # 按 lane 方向移动
        if mover.lane == "top":
            mover.y -= overlap_y + self.config.node_gap_y
        elif mover.lane == "bottom":
            mover.y += overlap_y + self.config.node_gap_y
        else:
            # mid lane: 向下移动
            mover.y += overlap_y + self.config.node_gap_y

    # ========================================================================
    # Step 6: Fit to Canvas
    # ========================================================================
    def _fit_to_canvas(self, canvas_width: int, canvas_height: int) -> float:
        """适配画布，返回缩放因子"""
        cfg = self.config

        if not self.nodes:
            return 1.0

        # 计算包围盒
        min_x = min(n.x for n in self.nodes.values())
        max_x = max(n.x + n.width for n in self.nodes.values())
        min_y = min(n.y for n in self.nodes.values())
        max_y = max(n.y + n.height for n in self.nodes.values())

        content_w = max_x - min_x
        content_h = max_y - min_y

        usable_w = canvas_width - 2 * cfg.margin_x
        usable_h = canvas_height - 2 * cfg.margin_y

        # 计算缩放因子
        scale_x = usable_w / content_w if content_w > 0 else 1.0
        scale_y = usable_h / content_h if content_h > 0 else 1.0
        scale = min(scale_x, scale_y, 1.0)  # 不放大，只缩小

        # 如果需要缩放
        if scale < 1.0:
            for node in self.nodes.values():
                node.x = int((node.x - min_x) * scale + cfg.margin_x)
                node.y = int((node.y - min_y) * scale + cfg.margin_y)
                node.width = int(node.width * scale)
                node.height = int(node.height * scale)
            log.info(f"[LayoutEngine] Scaled down by {scale:.2f}")
        else:
            # 居中
            offset_x = (canvas_width - content_w) // 2 - min_x
            offset_y = (canvas_height - content_h) // 2 - min_y

            for node in self.nodes.values():
                node.x += offset_x
                node.y += offset_y

        return scale

    # ========================================================================
    # Step 7: Emit layout_json
    # ========================================================================
    def _emit_layout_json(
        self,
        canvas_width: int,
        canvas_height: int,
        scale: float,
    ) -> Dict[str, Any]:
        """输出 layout_json"""
        nodes_layout = []

        for nid, node in self.nodes.items():
            nodes_layout.append({
                "node_id": nid,
                "bbox": {
                    "x": node.x,
                    "y": node.y,
                    "w": node.width,
                    "h": node.height,
                },
            })

        # 按 rank 排序
        nodes_layout.sort(key=lambda n: self.nodes[n["node_id"]].rank)

        return {
            "canvas": {
                "width": canvas_width,
                "height": canvas_height,
                "unit": "px",
            },
            "positions": {
                "nodes": nodes_layout,
                "chunks": [],
            },
            "meta": {
                "flow_direction": "left_to_right",
                "lane_count": 3,
                "spine": self.spine,
                "scale_factor": scale,
            },
        }


# ============================================================================
# Agent 入口函数
# ============================================================================
async def p2g_filmstrip_layout_engine_agent(
    state: FilmStripP2GState,
    **kwargs,
) -> FilmStripP2GState:
    """Film-Strip Layout Engine Agent 入口函数

    纯计算，不调用 LLM。

    Args:
        state: FilmStripP2GState 状态对象

    Returns:
        更新后的 FilmStripP2GState
    """
    # 获取输入
    node_graph_json = getattr(state, "node_graph_json", {})
    render_plan_json = getattr(state, "render_plan_json", {})
    vlm_node_assets = getattr(state, "vlm_node_assets", {})
    pptx_render_specs = getattr(state, "pptx_render_specs", {})

    canvas_width = getattr(state.request, "canvas_width", 1920)
    canvas_height = getattr(state.request, "canvas_height", 1080)

    if not node_graph_json.get("nodes"):
        log.warning("[LayoutEngine] No nodes to layout")
        setattr(state, "layout_json", {
            "canvas": {"width": canvas_width, "height": canvas_height, "unit": "px"},
            "positions": {"nodes": [], "chunks": []},
            "meta": {},
        })
        return state

    log.info(f"[LayoutEngine] Starting layout for {len(node_graph_json.get('nodes', []))} nodes")

    # 创建布局引擎并计算
    engine = LayoutEngine()
    layout_json = engine.compute_layout(
        node_graph_json=node_graph_json,
        render_plan_json=render_plan_json,
        vlm_node_assets=vlm_node_assets,
        pptx_render_specs=pptx_render_specs,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
    )

    # 更新 state
    setattr(state, "layout_json", layout_json)

    # 记录结果
    state.agent_results["p2g_filmstrip_layout_engine_agent"] = {
        "status": "ok",
        "stats": {
            "node_count": len(layout_json["positions"]["nodes"]),
            "spine": layout_json["meta"].get("spine", []),
            "scale_factor": layout_json["meta"].get("scale_factor", 1.0),
        },
    }

    log.info(f"[LayoutEngine] Layout completed: {len(layout_json['positions']['nodes'])} nodes positioned")

    return state
