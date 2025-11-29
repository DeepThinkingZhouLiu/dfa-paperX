"""
P2gLayoutConstructorAgent agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
生成时间: 2025-11-24

本 agent 负责根据 layout_plan + node_layout_plan + semantic_json 生成最终的 layout_json（包含 bbox 坐标）。
核心逻辑：
1. 使用 grid_layout_solver 根据 layout_plan 计算 chunk bbox
2. 使用 node_layout_plan 中的 rel_bbox 计算每个 node 的绝对 bbox
3. 组装成完整的 layout_json
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from dataflow_agent.state import MainState, Paper2GraphState
from dataflow_agent.toolkits.tool_manager import ToolManager
from dataflow_agent.logger import get_logger
from dataflow_agent.agentroles.base_agent import BaseAgent
from dataflow_agent.agentroles.registry import register

log = get_logger(__name__)

# ----------------------------------------------------------------------
# Agent Definition
# ----------------------------------------------------------------------
@register("p2g_layout_constructor_agent")
class P2gLayoutConstructorAgent(BaseAgent):
    """根据 layout_plan + node_layout_plan + semantic_json 生成 layout_json（包含所有 bbox 坐标）"""

    # ---------- 工厂 ----------
    @classmethod
    def create(cls, tool_manager: Optional[ToolManager] = None, **kwargs):
        return cls(tool_manager=tool_manager, **kwargs)

    # ---------- 基本配置 ----------
    @property
    def role_name(self) -> str:  # noqa: D401
        return "p2g_layout_constructor_agent"

    @property
    def system_prompt_template_name(self) -> str:
        # 返回模板名称字符串，供 PromptsTemplateGenerator 渲染
        return "system_prompt_for_p2g_layout_constructor_agent"

    @property
    def task_prompt_template_name(self) -> str:
        # 返回模板名称字符串，供 PromptsTemplateGenerator 渲染
        return "task_prompt_for_p2g_layout_constructor_agent"

    # ---------- 核心布局计算逻辑 ----------
    def _compute_node_bboxes_from_plan(
        self,
        chunk_bboxes: Dict[str, Dict[str, int]],
        node_layout_plan: Dict[str, Any],
        semantic_json: Dict[str, Any],
    ) -> Dict[str, Dict[str, int]]:
        """根据 node_layout_plan 的 rel_bbox 计算节点绝对坐标。
        
        Args:
            chunk_bboxes: chunk_id -> {x, y, w, h} 的映射
            node_layout_plan: 包含 chunks 数组，每个 chunk 有 chunk_id 和 nodes 数组
            semantic_json: 语义 JSON，用于获取缺失节点的默认信息
            
        Returns:
            node_id -> {x, y, w, h} 的映射
        """
        node_bboxes: Dict[str, Dict[str, int]] = {}
        
        # 获取所有 nodes 信息，用于查找缺失的节点
        all_nodes_by_id: Dict[str, Dict[str, Any]] = {}
        for node in semantic_json.get("nodes", []):
            node_id = node.get("node_id")
            if node_id:
                all_nodes_by_id[node_id] = node
        
        # 记录已处理的节点
        processed_node_ids: set = set()
        
        # 从 node_layout_plan 中提取节点布局
        for chunk_plan in node_layout_plan.get("chunks", []):
            chunk_id = chunk_plan.get("chunk_id")
            if not chunk_id:
                continue
                
            chunk_bbox = chunk_bboxes.get(chunk_id)
            if not chunk_bbox:
                log.warning("Chunk %s not found in chunk_bboxes, skipping its nodes", chunk_id)
                continue
            
            # 计算 chunk 内部可用区域（添加 padding）
            padding = 16  # 内边距
            inner_x = chunk_bbox["x"] + padding
            inner_y = chunk_bbox["y"] + padding
            inner_w = max(10, chunk_bbox["w"] - 2 * padding)
            inner_h = max(10, chunk_bbox["h"] - 2 * padding)
            
            for node_plan in chunk_plan.get("nodes", []):
                node_id = node_plan.get("node_id")
                if not node_id:
                    continue
                    
                rel_bbox = node_plan.get("rel_bbox", {})
                if not rel_bbox:
                    log.warning("Node %s has no rel_bbox, skipping", node_id)
                    continue
                
                # 获取相对坐标（0-1 范围）
                rel_x = float(rel_bbox.get("x", 0))
                rel_y = float(rel_bbox.get("y", 0))
                rel_w = float(rel_bbox.get("w", 0.1))
                rel_h = float(rel_bbox.get("h", 0.1))
                
                # 确保值在合理范围内
                rel_x = max(0, min(1, rel_x))
                rel_y = max(0, min(1, rel_y))
                rel_w = max(0.01, min(1 - rel_x, rel_w))
                rel_h = max(0.01, min(1 - rel_y, rel_h))
                
                # 计算绝对坐标
                abs_bbox = {
                    "x": inner_x + int(rel_x * inner_w),
                    "y": inner_y + int(rel_y * inner_h),
                    "w": max(20, int(rel_w * inner_w)),  # 最小宽度 20px
                    "h": max(15, int(rel_h * inner_h)),  # 最小高度 15px
                }
                
                node_bboxes[node_id] = abs_bbox
                processed_node_ids.add(node_id)
                
                log.debug(
                    "Node %s: rel_bbox=(%.2f, %.2f, %.2f, %.2f) -> abs_bbox=(%d, %d, %d, %d)",
                    node_id, rel_x, rel_y, rel_w, rel_h,
                    abs_bbox["x"], abs_bbox["y"], abs_bbox["w"], abs_bbox["h"]
                )
        
        # 处理 node_layout_plan 中未覆盖的节点（fallback 布局）
        for node in semantic_json.get("nodes", []):
            node_id = node.get("node_id")
            chunk_id = node.get("chunk_id")
            
            if not node_id or node_id in processed_node_ids:
                continue
            
            # 获取该节点所属 chunk 的 bbox
            chunk_bbox = chunk_bboxes.get(chunk_id) if chunk_id else None
            if not chunk_bbox:
                log.warning("Node %s has no valid chunk_bbox, using default position", node_id)
                # 使用默认位置
                node_bboxes[node_id] = {"x": 100, "y": 100, "w": 100, "h": 60}
                continue
            
            # 使用简单的 fallback 布局：在 chunk 内部随机分布
            padding = 16
            inner_x = chunk_bbox["x"] + padding
            inner_y = chunk_bbox["y"] + padding
            inner_w = max(10, chunk_bbox["w"] - 2 * padding)
            inner_h = max(10, chunk_bbox["h"] - 2 * padding)
            
            # 获取节点类型，决定默认尺寸
            node_type = node.get("node_type", "shape")
            default_sizes = {
                "text_block": (120, 40),
                "shape": (100, 80),
                "image_placeholder": (120, 120),
                "table_placeholder": (150, 100),
                "annotation": (80, 30),
            }
            default_w, default_h = default_sizes.get(node_type, (100, 60))
            
            # 计算一个简单的位置（居中偏移）
            offset_x = (hash(node_id) % 100) / 100 * 0.5  # 0-0.5 的随机偏移
            offset_y = (hash(node_id + "y") % 100) / 100 * 0.5
            
            node_bboxes[node_id] = {
                "x": inner_x + int(offset_x * (inner_w - default_w)),
                "y": inner_y + int(offset_y * (inner_h - default_h)),
                "w": min(default_w, inner_w),
                "h": min(default_h, inner_h),
            }
            
            log.warning(
                "Node %s not in node_layout_plan, using fallback position in chunk %s",
                node_id, chunk_id
            )
        
        return node_bboxes

    def build_layout_json(self, state: MainState) -> Dict[str, Any]:
        """
        基于确定性算法构建 layout_json。
        
        步骤：
        1. 从 state 中获取 semantic_json, layout_plan, node_layout_plan
        2. 使用 grid_layout_solver 计算 chunk bbox
        3. 使用 node_layout_plan 的 rel_bbox 计算每个 node 的绝对 bbox
        4. 组装成完整的 layout_json
        
        Args:
            state: 包含 semantic_json, layout_plan, node_layout_plan 等信息的状态对象
            
        Returns:
            完整的 layout_json
        """
        from dataflow_agent.toolkits.papergraphtool.grid_layout_solver import compute_chunk_bboxes

        # 1. 取输入
        semantic = getattr(state, "semantic_json", {}) or {}
        layout_plan = getattr(state, "layout_plan", {}) or {}
        node_layout_plan = getattr(state, "node_layout_plan", {}) or {}
        req = getattr(state, "request", None)

        if not semantic:
            raise ValueError("semantic_json 为空，无法构建布局")
        if not layout_plan:
            raise ValueError("layout_plan 为空，无法构建布局")

        # 2. 画布尺寸（可从 schema 中取，也可以使用默认值）
        canvas_w = 1920
        canvas_h = 1080
        
        layout_schema = getattr(req, "layout_json_schema", None) or {}
        canvas_schema = layout_schema.get("canvas") if isinstance(layout_schema, dict) else None
        if isinstance(canvas_schema, dict):
            canvas_w = canvas_schema.get("width", canvas_w)
            canvas_h = canvas_schema.get("height", canvas_h)

        log.info(f"画布尺寸: {canvas_w}x{canvas_h}")

        # 3. 计算 chunk bbox
        log.info("开始计算 chunk bbox...")
        chunk_bboxes = compute_chunk_bboxes(
            canvas_size=(canvas_w, canvas_h),
            layout_plan=layout_plan,
            semantic_json=semantic,
        )
        log.info(f"完成 {len(chunk_bboxes)} 个 chunk 的 bbox 计算")

        # 4. 使用 node_layout_plan 计算 node bbox
        log.info("开始使用 node_layout_plan 计算 node bbox...")
        
        if not node_layout_plan or not node_layout_plan.get("chunks"):
            log.warning("node_layout_plan 为空或无有效 chunks，将使用 fallback 布局")
        
        node_bboxes = self._compute_node_bboxes_from_plan(
            chunk_bboxes=chunk_bboxes,
            node_layout_plan=node_layout_plan,
            semantic_json=semantic,
        )
        
        log.info(f"完成 {len(node_bboxes)} 个 node 的布局")

        # 5. 组装 layout_json
        positions_chunks = [
            {"chunk_id": cid, "bbox": cbbox} 
            for cid, cbbox in chunk_bboxes.items()
        ]
        positions_nodes = [
            {"node_id": nid, "bbox": nbbox} 
            for nid, nbbox in node_bboxes.items()
        ]

        # 获取 flow_direction
        flow_direction = layout_plan.get("global", {}).get("flow_direction", "left-to-right")

        layout_json = {
            "version": "0.5",
            "canvas": {
                "width": canvas_w,
                "height": canvas_h,
                "unit": "px"
            },
            "layout_flow": flow_direction,
            "positions": {
                "chunks": positions_chunks,
                "nodes": positions_nodes,
            },
        }
        
        log.info("layout_json 构建完成")
        return layout_json

    def get_default_pre_tool_results(self) -> Dict[str, Any]:
        """若调用方未显式传入，返回默认前置工具结果"""
        return {}

    # ---------- 结果写回 ----------
    def update_state_result(
        self,
        state: MainState,
        result: Dict[str, Any],
        pre_tool_results: Dict[str, Any],
    ):
        """
        对于 layout_constructor，我们忽略 LLM 的 result，直接在代码中构建 layout_json。
        """
        try:
            pstate: Paper2GraphState = state  # 类型别名
            
            # 直接调用布局计算逻辑，不使用 LLM 结果
            layout_json = self.build_layout_json(state)
            
            # 写入 state
            setattr(pstate, "layout_json", layout_json)

            # 统计信息
            stats = {
                "chunks": len(layout_json.get("positions", {}).get("chunks", [])),
                "nodes": len(layout_json.get("positions", {}).get("nodes", [])),
                "canvas": f"{layout_json.get('canvas', {}).get('width')}x{layout_json.get('canvas', {}).get('height')}",
            }
            
            # 记录到 agent_results
            state.agent_results[self.role_name] = {
                "status": "ok",
                "stats": stats,
            }
            
        except Exception as e:
            log.exception("Failed to build layout_json in p2g_layout_constructor_agent")
            
            # 记录错误信息到 state
            setattr(state, "layout_error_info", str(e))
            state.agent_results[self.role_name] = {
                "status": "failed",
                "error": str(e),
            }
            raise


# ----------------------------------------------------------------------
# Helper APIs
# ----------------------------------------------------------------------
async def p2g_layout_constructor_agent(
    state: MainState,
    model_name: Optional[str] = None,
    tool_manager: Optional[ToolManager] = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    tool_mode: str = "auto",
    react_mode: bool = False,
    react_max_retries: int = 3,
    parser_type: str = "json",
    parser_config: Optional[Dict[str, Any]] = None,
    use_vlm: bool = False,
    vlm_config: Optional[Dict[str, Any]] = None,
    use_agent: bool = False,
    **kwargs,
) -> MainState:
    """p2g_layout_constructor_agent 的异步入口
    
    注意：虽然接受 model_name 等参数，但实际布局计算不依赖 LLM。
    
    Args:
        state: 主状态对象
        model_name: 模型名称（本 agent 不使用 LLM，仅为保持接口一致）
        tool_manager: 工具管理器实例
        temperature: 采样温度
        max_tokens: 最大生成token数
        tool_mode: 工具调用模式
        react_mode: 是否启用ReAct推理模式
        react_max_retries: ReAct模式下最大重试次数
        parser_type: 解析器类型
        parser_config: 解析器配置字典
        use_vlm: 是否使用视觉语言模型
        vlm_config: VLM配置字典
        use_agent: 是否使用agent模式
        **kwargs: 其他传递给execute的参数
        
    Returns:
        更新后的MainState对象
    """
    agent = P2gLayoutConstructorAgent(
        tool_manager=tool_manager,
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        tool_mode=tool_mode,
        react_mode=react_mode,
        react_max_retries=react_max_retries,
        parser_type=parser_type,
        parser_config=parser_config,
        use_vlm=use_vlm,
        vlm_config=vlm_config,
    )
    # 空的 pre_tool_results，因为不需要从外部传入工具结果
    pre_tool_results = {}
    return await agent.execute(state, use_agent=use_agent, pre_tool_results=pre_tool_results, **kwargs)


def create_p2g_layout_constructor_agent(
    tool_manager: Optional[ToolManager] = None,
    model_name: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    tool_mode: str = "auto",
    react_mode: bool = False,
    react_max_retries: int = 3,
    parser_type: str = "json",
    parser_config: Optional[Dict[str, Any]] = None,
    use_vlm: bool = False,
    vlm_config: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> P2gLayoutConstructorAgent:
    """创建 P2gLayoutConstructorAgent 实例的工厂函数
    
    Args:
        tool_manager: 工具管理器实例
        model_name: 模型名称
        temperature: 采样温度
        max_tokens: 最大生成token数
        tool_mode: 工具调用模式
        react_mode: 是否启用ReAct推理模式
        react_max_retries: ReAct模式下最大重试次数
        parser_type: 解析器类型
        parser_config: 解析器配置字典
        use_vlm: 是否使用视觉语言模型
        vlm_config: VLM配置字典
        **kwargs: 其他参数
        
    Returns:
        P2gLayoutConstructorAgent实例
    """
    return P2gLayoutConstructorAgent.create(
        tool_manager=tool_manager,
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        tool_mode=tool_mode,
        react_mode=react_mode,
        react_max_retries=react_max_retries,
        parser_type=parser_type,
        parser_config=parser_config,
        use_vlm=use_vlm,
        vlm_config=vlm_config,
        **kwargs,
    )
