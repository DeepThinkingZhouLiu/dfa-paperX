"""p2g_node_render_design_agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

为每个 node 设计渲染方式（pptx 或 vlm）和对应的渲染规格。

外层通过遍历 semantic_json.chunks，按 chunk 调用本 agent，
最终汇总为 state.node_render_design。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional, Set

from dataflow_agent.state import MainState, Paper2GraphState
from dataflow_agent.toolkits.tool_manager import ToolManager
from dataflow_agent.logger import get_logger
from dataflow_agent.agentroles.base_agent import BaseAgent
from dataflow_agent.agentroles.registry import register

log = get_logger(__name__)


@register("p2g_node_render_design_agent")
class P2gNodeRenderDesignAgent(BaseAgent):
    """针对单个 chunk 设计 nodes 的渲染方式和规格。"""

    def __init__(self, tool_manager: Optional[ToolManager] = None, **kwargs):
        super().__init__(tool_manager=tool_manager, **kwargs)
        self._current_chunk_ctx: Dict[str, Any] = {}

    @classmethod
    def create(cls, tool_manager: Optional[ToolManager] = None, **kwargs):
        return cls(tool_manager=tool_manager, **kwargs)

    def set_chunk_ctx(self, chunk_ctx: Dict[str, Any]):
        """设置当前要处理的 chunk 上下文，供 get_task_prompt_params 使用。"""
        self._current_chunk_ctx = chunk_ctx

    @property
    def role_name(self) -> str:
        return "p2g_node_render_design_agent"

    @property
    def system_prompt_template_name(self) -> str:
        return "system_prompt_for_p2g_node_render_design_agent"

    @property
    def task_prompt_template_name(self) -> str:
        return "task_prompt_for_p2g_node_render_design_agent"

    def get_default_pre_tool_results(self) -> Dict[str, Any]:
        return {"chunk_ctx": self._current_chunk_ctx}

    def get_task_prompt_params(self, pre_tool_results: Dict[str, Any]) -> Dict[str, Any]:
        """从 pre_tool_results 中读取当前 chunk 的上下文。

        期望 pre_tool_results["chunk_ctx"] 结构为:
        {
          "chunk_id": str,
          "chunk_summary": str,
          "nodes_info": list[dict],  # 包含 node_id, node_type, desc, role
          "semantic_desc": str,
          "global_style": dict,  # 全局样式配置
        }
        """
        chunk_ctx: Dict[str, Any] = pre_tool_results.get("chunk_ctx", {}) or {}

        nodes_info = chunk_ctx.get("nodes_info", [])
        global_style = chunk_ctx.get("global_style", {})

        # 转换为格式化的 JSON 字符串
        nodes_info_str = json.dumps(nodes_info, ensure_ascii=False, indent=2) if nodes_info else "[]"
        global_style_str = json.dumps(global_style, ensure_ascii=False, indent=2) if global_style else "{}"

        params = {
            "chunk_id": chunk_ctx.get("chunk_id", ""),
            "chunk_summary": chunk_ctx.get("chunk_summary", ""),
            "nodes_info": nodes_info_str,
            "semantic_desc": chunk_ctx.get("semantic_desc", ""),
            "global_style": global_style_str,
        }

        log.info("[node_render_design] Processing chunk: %s with %d nodes",
                 params["chunk_id"], len(nodes_info))
        return params

    def update_state_result(
        self,
        state: MainState,
        result: Dict[str, Any],
        pre_tool_results: Dict[str, Any],
    ):
        """记录单个 chunk 的渲染设计结果到 agent_results。

        真正的 node_render_design 汇总由外层 helper 完成。
        """
        state.agent_results.setdefault(self.role_name, {"chunks": []})

        chunk_res: Dict[str, Any] = {}
        if isinstance(result, dict):
            # 兼容可能的包裹层
            if "chunk_id" in result:
                chunk_res = result
            elif "render_design" in result and isinstance(result["render_design"], dict):
                chunk_res = result["render_design"]
            else:
                chunk_res = result

        # 验证结果有效性
        chunk_id = chunk_res.get("chunk_id")
        nodes = chunk_res.get("nodes", [])
        
        if chunk_id and isinstance(nodes, list):
            # 验证 chunk_id 不是占位符
            if chunk_id == "{chunk_id}" or chunk_id.startswith("placeholder"):
                log.warning(
                    "node_render_design for chunk returned placeholder chunk_id: %s; "
                    "attempting to use chunk_ctx chunk_id instead",
                    chunk_id,
                )
                chunk_ctx = pre_tool_results.get("chunk_ctx", {})
                real_chunk_id = chunk_ctx.get("chunk_id")
                if real_chunk_id:
                    chunk_res["chunk_id"] = real_chunk_id
                    chunk_id = real_chunk_id
            
            if not nodes:
                log.warning(
                    "node_render_design for chunk %s has empty nodes; raw result=%s",
                    chunk_id, result,
                )
            
            state.agent_results[self.role_name]["chunks"].append(chunk_res)
            log.info("Saved node_render_design for chunk %s with %d nodes", chunk_id, len(nodes))
        else:
            log.warning("p2g_node_render_design_agent got unexpected result: %s", result)


# ----------------------------------------------------------------------
# Helper functions for parallel execution
# ----------------------------------------------------------------------

async def _process_single_chunk(
    agent: P2gNodeRenderDesignAgent,
    state: Paper2GraphState,
    chunk_ctx: Dict[str, Any],
) -> Dict[str, Any]:
    """处理单个 chunk 的节点渲染设计（供并行执行使用）。
    
    Returns:
        包含 chunk_id、nodes 和 chunk_style_hints 的渲染设计结果字典
    """
    chunk_id = chunk_ctx.get("chunk_id", "unknown")
    
    try:
        # 创建一个新的 agent 实例以避免并发状态冲突
        single_agent = P2gNodeRenderDesignAgent.create(
            tool_manager=agent.tool_manager,
            model_name=agent.model_name,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
            parser_type=agent.parser_type,
            parser_config=agent.parser_config,
            use_vlm=agent.use_vlm,
            vlm_config=agent.vlm_config,
        )
        
        # 设置 chunk 上下文
        single_agent.set_chunk_ctx(chunk_ctx)
        
        # 执行 agent
        await single_agent.execute(
            state,
            use_agent=False,
        )
        
        # 从 agent_results 中获取最新添加的结果
        chunks_results = state.agent_results.get(single_agent.role_name, {}).get("chunks", [])
        
        # 找到当前 chunk_id 对应的结果
        for res in reversed(chunks_results):
            if res.get("chunk_id") == chunk_id:
                return res
        
        log.warning("Could not find result for chunk %s in agent_results", chunk_id)
        return {"chunk_id": chunk_id, "nodes": []}
        
    except Exception as e:
        log.error("Failed to process chunk %s: %s", chunk_id, e)
        return {"chunk_id": chunk_id, "nodes": [], "error": str(e)}


def _get_default_global_style() -> Dict[str, Any]:
    """获取默认的全局样式配置。

    Returns:
        全局样式字典，包含主题、配色指导、字体、背景等信息
    """
    return {
        "theme": "Top-tier CS conference scientific illustration style (NeurIPS, ICML, CVPR, ACL). Clean, professional, publication-ready diagrams with clear visual hierarchy.",
        "color_guidance": {
            "primary": "Use calm, professional blues as the primary color for main modules and processing blocks.",
            "secondary": "Use soft warm tones (peach, coral, light orange) for attention mechanisms, special operations, or highlighted elements.",
            "accent": "Use muted greens or teals for data inputs, datasets, and source elements.",
            "neutral": "Use light grays and off-whites for backgrounds, containers, and less important elements.",
            "text": "Use dark gray or navy blue for text to ensure high contrast and readability.",
            "overall": "Prefer Morandi-style muted, desaturated colors that look professional in academic papers. Avoid overly saturated or neon colors.",
        },
        "visual_style": {
            "design": "Flat 2D vector style, clean lines, no photorealism, no heavy 3D effects.",
            "shapes": "Use rounded rectangles for modules, circles for states/nodes, straight arrows with clean arrowheads.",
            "layout": "Prefer horizontal left-to-right flow for main pipelines. Use Manhattan-style routing (90-degree turns) for arrows when needed.",
            "spacing": "Maintain consistent spacing between elements. Avoid cluttered layouts.",
        },
        "background": "Solid white or very light gray. No gradients, no shadows, no textures on background.",
        "font_family": "Sans-serif fonts (Arial, Helvetica) for clean readability.",
    }


def _build_chunk_context(
    chunk: Dict[str, Any],
    all_nodes: List[Dict[str, Any]],
    node_layout_plan: Dict[str, Any],
    semantic_desc: str,
    global_style: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """为单个 chunk 构建上下文信息。

    Args:
        chunk: semantic_json 中的 chunk 对象
        all_nodes: semantic_json 中的所有 nodes
        node_layout_plan: node_layout_plan 结果，包含 nodes 的 role 信息
        semantic_desc: 整体语义描述
        global_style: 全局样式配置

    Returns:
        chunk 上下文字典
    """
    chunk_id = chunk.get("chunk_id", "")
    
    # 获取属于该 chunk 的 nodes
    chunk_node_ids = set(chunk.get("node_ids", []))
    chunk_nodes = [n for n in all_nodes if n.get("node_id") in chunk_node_ids]
    
    # 从 node_layout_plan 中获取 nodes 的 role 信息
    role_map: Dict[str, str] = {}
    for chunk_plan in node_layout_plan.get("chunks", []):
        if chunk_plan.get("chunk_id") == chunk_id:
            for node_plan in chunk_plan.get("nodes", []):
                node_id = node_plan.get("node_id")
                role = node_plan.get("role", "")
                if node_id and role:
                    role_map[node_id] = role
            break
    
    # 构建 nodes_info，包含 role 信息
    nodes_info = []
    for node in chunk_nodes:
        node_id = node.get("node_id", "")
        node_info = {
            "node_id": node_id,
            "node_type": node.get("node_type", ""),
            "desc": node.get("desc", ""),
            "role": role_map.get(node_id, ""),
        }
        nodes_info.append(node_info)
    
    return {
        "chunk_id": chunk_id,
        "chunk_summary": chunk.get("summary", ""),
        "nodes_info": nodes_info,
        "semantic_desc": semantic_desc,
        "global_style": global_style or _get_default_global_style(),
    }


async def p2g_node_render_design_agent(
    state: Paper2GraphState,
    model_name: Optional[str] = "gpt-4o",
    tool_manager: Optional[ToolManager] = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    parser_type: str = "json",
    parser_config: Optional[Dict[str, Any]] = None,
    use_vlm: bool = False,
    vlm_config: Optional[Dict[str, Any]] = None,
    parallel: bool = True,
    **kwargs,
) -> Paper2GraphState:
    """遍历 semantic_json.chunks，针对每个 chunk 调用一次 node_render_design agent，
    汇总为 state.node_render_design。
    
    Args:
        state: Paper2GraphState 状态对象
        model_name: LLM 模型名称
        tool_manager: 工具管理器
        temperature: 采样温度
        max_tokens: 最大 token 数
        parser_type: 解析器类型
        parser_config: 解析器配置
        use_vlm: 是否使用 VLM
        vlm_config: VLM 配置
        parallel: 是否并行执行（默认 True）
        **kwargs: 其他参数
        
    Returns:
        更新后的 Paper2GraphState
    """
    semantic_json = getattr(state, "semantic_json", {}) or {}
    chunks: List[Dict[str, Any]] = semantic_json.get("chunks", []) or []
    all_nodes: List[Dict[str, Any]] = semantic_json.get("nodes", []) or []
    
    node_layout_plan = getattr(state, "node_layout_plan", {}) or {}
    
    if not chunks:
        log.warning("semantic_json.chunks is empty, skip node render design")
        setattr(state, "node_render_design", {"chunks": [], "global_style": {}})
        return state

    # 全局 semantic_desc
    enriched = getattr(state, "enriched_description", {}) or {}
    semantic_desc = ""
    if isinstance(enriched, dict):
        sd = enriched.get("semantic_desc")
        if isinstance(sd, str):
            semantic_desc = sd

    # 创建主 agent 实例
    agent = P2gNodeRenderDesignAgent.create(
        tool_manager=tool_manager,
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        parser_type=parser_type,
        parser_config=parser_config,
        use_vlm=use_vlm,
        vlm_config=vlm_config,
    )

    # 清空之前的结果容器
    state.agent_results[agent.role_name] = {"chunks": []}

    # 准备所有 chunk 的上下文
    chunk_contexts: List[Dict[str, Any]] = []
    for ch in chunks:
        cid = ch.get("chunk_id")
        if not cid:
            continue
        
        chunk_ctx = _build_chunk_context(
            chunk=ch,
            all_nodes=all_nodes,
            node_layout_plan=node_layout_plan,
            semantic_desc=semantic_desc,
        )
        chunk_contexts.append(chunk_ctx)

    log.info("Starting node render design for %d chunks (parallel=%s)", 
             len(chunk_contexts), parallel)

    if parallel and len(chunk_contexts) > 1:
        # 并行执行所有 chunk 的渲染设计
        tasks = [
            _process_single_chunk(agent, state, ctx)
            for ctx in chunk_contexts
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        chunks_result = []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                log.error("Chunk %s failed with exception: %s", 
                         chunk_contexts[i].get("chunk_id"), res)
                chunks_result.append({
                    "chunk_id": chunk_contexts[i].get("chunk_id"),
                    "nodes": [],
                    "error": str(res),
                })
            elif isinstance(res, dict):
                chunks_result.append(res)
            else:
                log.warning("Unexpected result type for chunk %s: %s", 
                           chunk_contexts[i].get("chunk_id"), type(res))
    else:
        # 串行执行
        chunks_result = []
        for ctx in chunk_contexts:
            agent.set_chunk_ctx(ctx)
            await agent.execute(
                state,
                use_agent=False,
            )
        
        chunks_result = state.agent_results.get(agent.role_name, {}).get("chunks", []) or []

    # 汇总结果，构建 node_render_design
    node_render_design = {
        "chunks": [],
        "global_style": _get_default_global_style(),
    }
    
    for ch_res in chunks_result:
        if isinstance(ch_res, dict) and ch_res.get("chunk_id"):
            chunk_id = ch_res.get("chunk_id")
            if chunk_id and chunk_id != "{chunk_id}" and not chunk_id.startswith("placeholder"):
                node_render_design["chunks"].append(ch_res)
            else:
                log.warning("Skipping chunk with invalid chunk_id: %s", chunk_id)

    setattr(state, "node_render_design", node_render_design)
    
    log.info("Node render design completed: %d chunks processed", 
             len(node_render_design["chunks"]))
    
    return state
