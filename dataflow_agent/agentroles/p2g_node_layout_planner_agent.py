"""p2g_node_layout_planner_agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

为单个 chunk 规划 chunk 内部 nodes 的相对布局 (rel_bbox)。

外层通过遍历 semantic_json.chunks, 并行调用本 agent, 最终汇总为
state.node_layout_plan。
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


@register("p2g_node_layout_planner_agent")
class P2gNodeLayoutPlannerAgent(BaseAgent):
    """针对单个 chunk 规划 nodes 的相对布局 (rel_bbox)。"""

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
    def role_name(self) -> str:  # noqa: D401
        return "p2g_node_layout_planner_agent"

    @property
    def system_prompt_template_name(self) -> str:
        return "system_prompt_for_p2g_node_layout_planner_agent"

    @property
    def task_prompt_template_name(self) -> str:
        return "task_prompt_for_p2g_node_layout_planner_agent"

    def get_default_pre_tool_results(self) -> Dict[str, Any]:
        # 返回通过 set_chunk_ctx 设置的 chunk 上下文
        return {"chunk_ctx": self._current_chunk_ctx}

    def get_task_prompt_params(self, pre_tool_results: Dict[str, Any]) -> Dict[str, Any]:
        """从 pre_tool_results 中读取当前 chunk 的上下文.

        期望 pre_tool_results["chunk_ctx"] 结构为:
        {
          "chunk_id": str,
          "chunk_summary": str,
          "chunk_nodes": list[dict],
          "chunk_edges": list[dict],
          "semantic_desc": str,
        }

        返回的参数将直接填充到 prompt 模板的占位符中。
        """
        chunk_ctx: Dict[str, Any] = pre_tool_results.get("chunk_ctx", {}) or {}
        
        # 确保 chunk_nodes 和 chunk_edges 是 JSON 字符串格式，便于 LLM 阅读
        chunk_nodes = chunk_ctx.get("chunk_nodes", [])
        chunk_edges = chunk_ctx.get("chunk_edges", [])
        
        # 转换为格式化的 JSON 字符串
        chunk_nodes_str = json.dumps(chunk_nodes, ensure_ascii=False, indent=2) if chunk_nodes else "[]"
        chunk_edges_str = json.dumps(chunk_edges, ensure_ascii=False, indent=2) if chunk_edges else "[]"
        
        params = {
            "chunk_id": chunk_ctx.get("chunk_id", ""),
            "chunk_summary": chunk_ctx.get("chunk_summary", ""),
            "chunk_nodes": chunk_nodes_str,
            "chunk_edges": chunk_edges_str,
            "semantic_desc": chunk_ctx.get("semantic_desc", ""),
        }
        
        log.info("[node_layout_planner] Processing chunk: %s with %d nodes", 
                 params["chunk_id"], len(chunk_nodes))
        return params

    def update_state_result(
        self,
        state: MainState,
        result: Dict[str, Any],
        pre_tool_results: Dict[str, Any],
    ):
        """记录单个 chunk 的布局结果到 agent_results.

        真正的 node_layout_plan 汇总由外层 helper 完成, 这里不直接写回 state.node_layout_plan。
        """
        state.agent_results.setdefault(self.role_name, {"chunks": []})

        chunk_res: Dict[str, Any] = {}
        if isinstance(result, dict):
            # 兼容可能的包裹层: node_layout_plan_for_chunk / node_layout_plan
            if "node_layout_plan_for_chunk" in result and isinstance(result["node_layout_plan_for_chunk"], dict):
                chunk_res = result["node_layout_plan_for_chunk"]
            elif "node_layout_plan" in result and isinstance(result["node_layout_plan"], dict):
                chunk_res = result["node_layout_plan"]
            else:
                # 直接是 {chunk_id, nodes} 结构
                chunk_res = result

        # 验证结果有效性
        chunk_id = chunk_res.get("chunk_id")
        nodes = chunk_res.get("nodes", [])
        
        if chunk_id and isinstance(nodes, list):
            # 验证 chunk_id 不是占位符
            if chunk_id == "{chunk_id}" or chunk_id.startswith("placeholder"):
                log.warning(
                    "node_layout_plan for chunk returned placeholder chunk_id: %s; "
                    "attempting to use chunk_ctx chunk_id instead",
                    chunk_id,
                )
                # 尝试从 chunk_ctx 获取真实的 chunk_id
                chunk_ctx = pre_tool_results.get("chunk_ctx", {})
                real_chunk_id = chunk_ctx.get("chunk_id")
                if real_chunk_id:
                    chunk_res["chunk_id"] = real_chunk_id
                    chunk_id = real_chunk_id
            
            if not nodes:
                log.warning(
                    "node_layout_plan for chunk %s has empty nodes; raw result=%s",
                    chunk_id, result,
                )
            
            state.agent_results[self.role_name]["chunks"].append(chunk_res)
            log.info("Saved node_layout_plan for chunk %s with %d nodes", chunk_id, len(nodes))
        else:
            log.warning("p2g_node_layout_planner_agent got unexpected result: %s", result)


# ----------------------------------------------------------------------
# Helper functions for parallel execution
# ----------------------------------------------------------------------

async def _process_single_chunk(
    agent: P2gNodeLayoutPlannerAgent,
    state: Paper2GraphState,
    chunk_ctx: Dict[str, Any],
) -> Dict[str, Any]:
    """处理单个 chunk 的节点布局规划（供并行执行使用）。
    
    Returns:
        包含 chunk_id 和 nodes 的布局结果字典
    """
    chunk_id = chunk_ctx.get("chunk_id", "unknown")
    
    try:
        # 创建一个新的 agent 实例以避免并发状态冲突
        # 注意：这里我们复用传入的 agent 配置，但设置独立的 chunk_ctx
        single_agent = P2gNodeLayoutPlannerAgent.create(
            tool_manager=agent.tool_manager,
            model_name=agent.model_name,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
            parser_type=agent.parser_type,
            parser_config=agent.parser_config,
            use_vlm=agent.use_vlm,
            vlm_config=agent.vlm_config,
        )
        
        # 设置 chunk 上下文，使 get_default_pre_tool_results() 能返回正确的数据
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


async def p2g_node_layout_planner_agent(
    state: Paper2GraphState,
    model_name: Optional[str] = "gpt-5",
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
    """遍历 semantic_json.chunks, 针对每个 chunk 调用一次 node_layout_planner agent,
    汇总为 state.node_layout_plan。
    
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
    edges: List[Dict[str, Any]] = semantic_json.get("edges", []) or []

    if not chunks:
        log.warning("semantic_json.chunks is empty, skip node layout planning")
        setattr(state, "node_layout_plan", {"chunks": []})
        return state

    # 根据 chunk_id 索引 nodes
    nodes_by_chunk: Dict[str, List[Dict[str, Any]]] = {}
    for n in all_nodes:
        cid = n.get("chunk_id")
        if not cid:
            continue
        nodes_by_chunk.setdefault(cid, []).append(n)

    # 全局 semantic_desc (可选)
    enriched = getattr(state, "enriched_description", {}) or {}
    semantic_desc = ""
    if isinstance(enriched, dict):
        sd = enriched.get("semantic_desc")
        if isinstance(sd, str):
            semantic_desc = sd

    # 创建主 agent 实例（用于获取配置）
    agent = P2gNodeLayoutPlannerAgent.create(
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
        
        chunk_nodes = nodes_by_chunk.get(cid, [])
        
        # 过滤与当前 chunk 相关的 edges
        node_ids: Set[str] = {n["node_id"] for n in chunk_nodes if "node_id" in n}
        chunk_edges: List[Dict[str, Any]] = []
        for e in edges:
            frm = e.get("from", [])
            to = e.get("to", [])
            if isinstance(frm, str):
                frm = [frm]
            if isinstance(to, str):
                to = [to]
            if any(n in node_ids for n in frm) or any(n in node_ids for n in to):
                chunk_edges.append(e)

        chunk_ctx = {
            "chunk_id": cid,
            "chunk_summary": ch.get("summary", ""),
            "chunk_nodes": chunk_nodes,
            "chunk_edges": chunk_edges,
            "semantic_desc": semantic_desc,
        }
        chunk_contexts.append(chunk_ctx)

    log.info("Starting node layout planning for %d chunks (parallel=%s)", 
             len(chunk_contexts), parallel)

    if parallel and len(chunk_contexts) > 1:
        # 并行执行所有 chunk 的布局规划
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
        # 串行执行（用于调试或单个 chunk 的情况）
        chunks_result = []
        for ctx in chunk_contexts:
            # 设置 chunk 上下文
            agent.set_chunk_ctx(ctx)
            await agent.execute(
                state,
                use_agent=False,
            )
        
        # 从 agent_results 中获取结果
        chunks_result = state.agent_results.get(agent.role_name, {}).get("chunks", []) or []

    # 汇总结果，构建 node_layout_plan
    node_layout_plan = {"chunks": []}
    for ch_res in chunks_result:
        if isinstance(ch_res, dict) and ch_res.get("chunk_id"):
            # 再次验证不是占位符
            chunk_id = ch_res.get("chunk_id")
            if chunk_id and chunk_id != "{chunk_id}" and not chunk_id.startswith("placeholder"):
                node_layout_plan["chunks"].append(ch_res)
            else:
                log.warning("Skipping chunk with invalid chunk_id: %s", chunk_id)

    setattr(state, "node_layout_plan", node_layout_plan)
    
    log.info("Node layout planning completed: %d chunks processed", 
             len(node_layout_plan["chunks"]))
    
    return state
