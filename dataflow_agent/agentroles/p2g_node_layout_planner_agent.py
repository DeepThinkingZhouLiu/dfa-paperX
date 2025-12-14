"""p2g_node_layout_planner_agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

为单个 chunk 规划 chunk 内部 nodes 的相对布局 (rel_bbox)。

外层通过遍历 semantic_json.chunks, 并行调用本 agent, 最终汇总为
state.node_layout_plan。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from dataflow_agent.state import MainState, Paper2GraphState
from dataflow_agent.toolkits.tool_manager import ToolManager
from dataflow_agent.toolkits.papergraphtool.space_utilization_validator import (
    validate_space_utilization,
    generate_improvement_suggestions,
)
from dataflow_agent.toolkits.papergraphtool.node_overlap_validator import (
    validate_nodes_overlap,
    generate_overlap_fix_suggestions,
    check_bbox_overlap,
)
from dataflow_agent.logger import get_logger
from dataflow_agent.agentroles.base_agent import BaseAgent
from dataflow_agent.agentroles.registry import register

log = get_logger(__name__)

# 类型别名
ValidatorFunc = Callable[[str, Dict[str, Any]], Tuple[bool, Optional[str]]]


@register("p2g_node_layout_planner_agent")
class P2gNodeLayoutPlannerAgent(BaseAgent):
    """针对单个 chunk 规划 nodes 的相对布局 (rel_bbox)。"""

    def __init__(self, tool_manager: Optional[ToolManager] = None, **kwargs):
        # 默认启用 react_mode，最多重试 3 次
        kwargs.setdefault("react_mode", True)
        kwargs.setdefault("react_max_retries", 3)
        super().__init__(tool_manager=tool_manager, **kwargs)
        self._current_chunk_ctx: Dict[str, Any] = {}

    @classmethod
    def create(cls, tool_manager: Optional[ToolManager] = None, **kwargs):
        return cls(tool_manager=tool_manager, **kwargs)

    def get_react_validators(self) -> List[ValidatorFunc]:
        """返回 ReAct 模式的验证器列表。"""
        return [
            self._default_json_validator,
            self._validate_no_overlap,
            self._validate_space_utilization,
        ]

    def _validate_no_overlap(
        self, content: str, parsed_result: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """验证 nodes 之间没有重叠。"""
        # 解析 chunk 结果
        chunk_res = self._extract_chunk_result(parsed_result)
        if not chunk_res:
            return True, None  # 无法验证，跳过

        nodes = chunk_res.get("nodes", [])
        if len(nodes) < 2:
            return True, None  # 少于 2 个 node，无需检测重叠

        # 检测重叠
        has_overlap, overlap_info, _ = validate_nodes_overlap(chunk_res, threshold=0.05)

        if has_overlap:
            # 构建详细的反馈信息，包含当前布局和重叠详情
            feedback = self._build_overlap_feedback(chunk_res, overlap_info)
            return False, feedback

        return True, None

    def _validate_space_utilization(
        self, content: str, parsed_result: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """验证空间利用率在合理范围内。"""
        chunk_res = self._extract_chunk_result(parsed_result)
        if not chunk_res:
            return True, None

        nodes = chunk_res.get("nodes", [])
        if not nodes:
            return True, None

        # 计算空间利用率
        is_valid, errors, metrics = validate_space_utilization(chunk_res, strict=False)
        utilization = metrics.get("utilization", 0)

        # 利用率过低时给出警告
        if utilization < 0.60:
            feedback = self._build_utilization_feedback(chunk_res, metrics)
            return False, feedback

        return True, None

    def _build_overlap_feedback(
        self, chunk_res: Dict[str, Any], overlap_info: List[Dict[str, Any]]
    ) -> str:
        """构建重叠检测的详细反馈信息。"""
        chunk_id = chunk_res.get("chunk_id", "unknown")
        nodes = chunk_res.get("nodes", [])

        # 构建当前布局信息
        layout_lines = []
        for node in nodes:
            node_id = node.get("node_id", "?")
            bbox = node.get("rel_bbox", {})
            x, y, w, h = bbox.get("x", 0), bbox.get("y", 0), bbox.get("w", 0), bbox.get("h", 0)
            right = x + w
            bottom = y + h
            layout_lines.append(
                f"  - {node_id}: x={x:.2f}, y={y:.2f}, w={w:.2f}, h={h:.2f} (右边界={right:.2f}, 下边界={bottom:.2f})"
            )

        # 构建重叠详情
        overlap_lines = []
        for info in overlap_info:
            n1, n2 = info["node1"], info["node2"]
            ratio = info["overlap_ratio"]
            # 找到两个 node 的 bbox
            bbox1 = next((n.get("rel_bbox", {}) for n in nodes if n.get("node_id") == n1), {})
            bbox2 = next((n.get("rel_bbox", {}) for n in nodes if n.get("node_id") == n2), {})

            overlap_lines.append(
                f"  - {n1} 与 {n2} 重叠 {ratio:.0%}:\n"
                f"    {n1}: x={bbox1.get('x', 0):.2f}~{bbox1.get('x', 0) + bbox1.get('w', 0):.2f}, "
                f"y={bbox1.get('y', 0):.2f}~{bbox1.get('y', 0) + bbox1.get('h', 0):.2f}\n"
                f"    {n2}: x={bbox2.get('x', 0):.2f}~{bbox2.get('x', 0) + bbox2.get('w', 0):.2f}, "
                f"y={bbox2.get('y', 0):.2f}~{bbox2.get('y', 0) + bbox2.get('h', 0):.2f}"
            )

        feedback = f"""[验证失败 - 检测到 nodes 重叠]

chunk_id: {chunk_id}

当前布局（共 {len(nodes)} 个 nodes）:
{chr(10).join(layout_lines)}

重叠问题详情（共 {len(overlap_info)} 对重叠）:
{chr(10).join(overlap_lines)}

请重新规划该 chunk 内所有 nodes 的 rel_bbox，确保：
1. 任意两个 node 的 bbox 不能有交集（即 node_A 的右边界 < node_B 的左边界，或 node_A 的下边界 < node_B 的上边界）
2. 相邻 nodes 间距 ≥ 0.03
3. 所有 bbox 必须在 [0.02, 0.98] 范围内"""

        return feedback

    def _build_utilization_feedback(
        self, chunk_res: Dict[str, Any], metrics: Dict[str, Any]
    ) -> str:
        """构建空间利用率的详细反馈信息。"""
        chunk_id = chunk_res.get("chunk_id", "unknown")
        nodes = chunk_res.get("nodes", [])
        utilization = metrics.get("utilization", 0)
        node_metrics = metrics.get("node_metrics", [])

        # 构建当前布局信息
        layout_lines = []
        for node in nodes:
            node_id = node.get("node_id", "?")
            bbox = node.get("rel_bbox", {})
            x, y, w, h = bbox.get("x", 0), bbox.get("y", 0), bbox.get("w", 0), bbox.get("h", 0)
            area = w * h
            layout_lines.append(
                f"  - {node_id}: x={x:.2f}, y={y:.2f}, w={w:.2f}, h={h:.2f}, 面积={area:.2%}"
            )

        # 找出面积较小的 nodes
        small_nodes = [nm for nm in node_metrics if nm.get("area", 0) < 0.05]
        small_node_ids = [nm.get("node_id", "?") for nm in small_nodes[:3]]

        feedback = f"""[验证失败 - 空间利用率过低]

chunk_id: {chunk_id}
当前利用率: {utilization:.0%}（目标: 65%~90%）

当前布局（共 {len(nodes)} 个 nodes）:
{chr(10).join(layout_lines)}

问题分析:
- 总面积覆盖不足，需要增加约 {(0.65 - utilization):.0%} 的面积
{f"- 以下 nodes 面积较小，可考虑适当扩大: {', '.join(small_node_ids)}" if small_nodes else ""}

请重新规划该 chunk 内所有 nodes 的 rel_bbox，确保：
1. 空间利用率达到 65%~90%
2. 根据 node 内容复杂度和功能合理分配尺寸
3. 避免极端宽高比（w/h 应在 0.5~3.0 之间）
4. 避免大面积空白区域"""

        return feedback

    def _extract_chunk_result(self, parsed_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """从解析结果中提取 chunk 布局数据。"""
        if not isinstance(parsed_result, dict):
            return None

        # 兼容多种包裹格式
        if "node_layout_plan_for_chunk" in parsed_result:
            return parsed_result["node_layout_plan_for_chunk"]
        elif "node_layout_plan" in parsed_result:
            return parsed_result["node_layout_plan"]
        elif "chunk_id" in parsed_result and "nodes" in parsed_result:
            return parsed_result

        return None

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
        state.agent_results.setdefault(self.role_name, {"chunks": [], "validation_results": []})

        chunk_res: Dict[str, Any] = {}
        react_failed = False
        if isinstance(result, dict):
            # 处理 ReAct 验证失败的情况：提取 last_result
            if "error" in result and "last_result" in result:
                react_failed = True
                last_result = result.get("last_result", {})
                if isinstance(last_result, dict):
                    chunk_res = last_result
                    log.warning(
                        "ReAct validation failed, using last_result for chunk: %s",
                        chunk_res.get("chunk_id", "unknown")
                    )
            # 兼容可能的包裹层: node_layout_plan_for_chunk / node_layout_plan
            elif "node_layout_plan_for_chunk" in result and isinstance(result["node_layout_plan_for_chunk"], dict):
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

            # ==================== 1. Nodes 重叠检测 ====================
            has_overlap, overlap_info, overlap_metrics = validate_nodes_overlap(chunk_res, threshold=0.1)

            # ==================== 2. 空间利用率验证 ====================
            is_valid, errors, metrics = validate_space_utilization(chunk_res, strict=False)

            # 如果有重叠，标记为无效
            if has_overlap:
                is_valid = False
                for info in overlap_info:
                    errors.append(
                        f"nodes {info['node1']} 和 {info['node2']} 重叠，重叠比例 {info['overlap_ratio']:.1%}"
                    )

            validation_result = {
                "chunk_id": chunk_id,
                "is_valid": is_valid,
                "errors": errors,
                "metrics": metrics,
                "has_overlap": has_overlap,
                "overlap_info": overlap_info,
            }

            if not is_valid:
                # 生成改进建议
                suggestions = generate_improvement_suggestions(metrics)
                if has_overlap:
                    suggestions.extend(generate_overlap_fix_suggestions(overlap_info, chunk_id))
                validation_result["suggestions"] = suggestions

                log.warning(
                    "chunk %s 验证未通过: 利用率=%.1f%%, 重叠=%d, 错误=%d",
                    chunk_id,
                    metrics.get("utilization", 0) * 100,
                    len(overlap_info),
                    len(errors),
                )
                for err in errors[:5]:  # 只显示前5个错误
                    log.warning("  - %s", err)
            else:
                log.info(
                    "chunk %s 验证通过: 利用率=%.1f%%, 无重叠",
                    chunk_id,
                    metrics.get("utilization", 0) * 100,
                )

            # 将验证结果附加到 chunk_res
            chunk_res["_validation"] = validation_result

            state.agent_results[self.role_name]["chunks"].append(chunk_res)
            state.agent_results[self.role_name]["validation_results"].append(validation_result)
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

    为避免并发状态冲突，每个任务使用独立的临时 state 来收集结果。

    Returns:
        包含 chunk_id 和 nodes 的布局结果字典
    """
    chunk_id = chunk_ctx.get("chunk_id", "unknown")

    try:
        # 创建一个新的 agent 实例以避免并发状态冲突
        single_agent = P2gNodeLayoutPlannerAgent.create(
            tool_manager=agent.tool_manager,
            model_name=agent.model_name,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
            parser_type=agent.parser_type,
            parser_config=agent.parser_config,
            use_vlm=agent.use_vlm,
            vlm_config=agent.vlm_config,
            react_mode=agent.react_mode,
            react_max_retries=agent.react_max_retries,
        )

        # 设置 chunk 上下文
        single_agent.set_chunk_ctx(chunk_ctx)

        # 创建一个临时的独立 state 用于收集结果，避免并发写入冲突
        # 复制必要的只读属性
        temp_state = Paper2GraphState()
        temp_state.semantic_json = state.semantic_json
        temp_state.enriched_description = getattr(state, "enriched_description", {})
        temp_state.layout_plan = getattr(state, "layout_plan", {})
        temp_state.agent_results = {}  # 独立的结果容器

        # 执行 agent（结果写入 temp_state）
        await single_agent.execute(
            temp_state,
            use_agent=False,
        )

        # 从临时 state 的 agent_results 中获取结果
        chunks_results = temp_state.agent_results.get(single_agent.role_name, {}).get("chunks", [])

        # 找到当前 chunk_id 对应的结果
        for res in reversed(chunks_results):
            if res.get("chunk_id") == chunk_id:
                return res

        log.warning("Could not find result for chunk %s in temp_state.agent_results", chunk_id)
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
    state.agent_results[agent.role_name] = {"chunks": [], "validation_results": []}

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
