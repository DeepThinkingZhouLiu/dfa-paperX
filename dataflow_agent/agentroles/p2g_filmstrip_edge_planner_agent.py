"""p2g_filmstrip_edge_planner_agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Film-Strip Pipeline Stage 1B: Edge Planner Agent

根据 Stage 1A 的 nodes 规划 edges，包含连接锚点信息（from_anchor/to_anchor）。

输入：
- state.request.target: 用户的论文方法描述
- state.node_graph_json: 只包含 nodes 的节点图（来自 Stage 1A）

输出：
- state.node_graph_json["edges"]: 填充 edges 数组
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from dataflow_agent.state import MainState, FilmStripP2GState
from dataflow_agent.toolkits.tool_manager import ToolManager
from dataflow_agent.logger import get_logger
from dataflow_agent.agentroles.base_agent import BaseAgent
from dataflow_agent.agentroles.registry import register

log = get_logger(__name__)

# 有效的 anchor 值
VALID_ANCHORS = {"left", "right", "top", "bottom", ""}


@register("p2g_filmstrip_edge_planner_agent")
class P2gFilmstripEdgePlannerAgent(BaseAgent):
    """Film-Strip Pipeline Stage 1B: Edge Planner Agent

    根据 Stage 1A 的 nodes 规划 edges，包含连接锚点信息。
    """

    def __init__(self, tool_manager: Optional[ToolManager] = None, **kwargs):
        super().__init__(tool_manager=tool_manager, **kwargs)

    @classmethod
    def create(cls, tool_manager: Optional[ToolManager] = None, **kwargs):
        return cls(tool_manager=tool_manager, **kwargs)

    @property
    def role_name(self) -> str:
        return "p2g_filmstrip_edge_planner_agent"

    @property
    def system_prompt_template_name(self) -> str:
        return "system_prompt_for_filmstrip_edge_planner"

    @property
    def task_prompt_template_name(self) -> str:
        return "task_prompt_for_filmstrip_edge_planner"

    def get_task_prompt_params(self, pre_tool_results: Dict[str, Any]) -> Dict[str, Any]:
        """构建任务 prompt 参数"""
        state: FilmStripP2GState = pre_tool_results.get("state")

        target = ""
        node_graph_json = {}

        if state and hasattr(state, "request"):
            target = getattr(state.request, "target", "")

        if state and hasattr(state, "node_graph_json"):
            node_graph_json = getattr(state, "node_graph_json", {})

        # 只传递 title, global_style, nodes 给 edge planner
        # 避免传递无关字段干扰
        filtered_node_graph = {
            "title": node_graph_json.get("title", ""),
            "global_style": node_graph_json.get("global_style", {}),
            "nodes": node_graph_json.get("nodes", []),
        }

        return {
            "target": target,
            "node_graph_json": json.dumps(filtered_node_graph, ensure_ascii=False, indent=2),
        }

    def build_messages(self, state: MainState, pre_tool_results: Dict[str, Any]):
        """自定义消息构建 - 将 state 注入到 pre_tool_results 中"""
        from dataflow_agent.promptstemplates.prompt_template import PromptsTemplateGenerator

        # 将 state 注入到 pre_tool_results 中
        pre_tool_results_with_state = {**pre_tool_results, "state": state}

        ptg = PromptsTemplateGenerator(state.request.language)
        sys_prompt = ptg.render(self.system_prompt_template_name)

        # 添加解析器格式说明
        format_instruction = self.parser.get_format_instruction()
        if format_instruction:
            sys_prompt += f"\n\n{format_instruction}"

        task_params = self.get_task_prompt_params(pre_tool_results_with_state)
        task_prompt = ptg.render(self.task_prompt_template_name, **task_params)

        return [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": task_prompt},
        ]

    def get_default_pre_tool_results(self) -> Dict[str, Any]:
        return {}

    def update_state_result(
        self,
        state: MainState,
        result: Dict[str, Any],
        pre_tool_results: Dict[str, Any],
    ):
        """更新 state.node_graph_json["edges"]"""
        if isinstance(result, dict) and "edges" in result:
            edges = result.get("edges", [])

            # 获取现有的 node_graph_json
            node_graph_json = getattr(state, "node_graph_json", {})
            if not node_graph_json:
                log.warning("[EdgePlanner] node_graph_json is empty, cannot add edges")
                state.agent_results[self.role_name] = {
                    "status": "failed",
                    "error": "node_graph_json is empty",
                }
                return

            # 获取有效的 node_ids
            nodes = node_graph_json.get("nodes", [])
            valid_node_ids = {n.get("node_id", "") for n in nodes}

            # 验证和清理 edges
            validated_edges = []
            warnings = []

            for edge in edges:
                edge_id = edge.get("edge_id", "")
                from_node = edge.get("from", "")
                to_node = edge.get("to", "")
                from_anchor = edge.get("from_anchor", "")
                to_anchor = edge.get("to_anchor", "")

                # 验证 node_id 存在
                if from_node not in valid_node_ids:
                    warnings.append(f"Edge {edge_id}: from node '{from_node}' not found")
                    continue
                if to_node not in valid_node_ids:
                    warnings.append(f"Edge {edge_id}: to node '{to_node}' not found")
                    continue

                # 验证 anchor 值（轻校验，只记录 warning）
                if from_anchor and from_anchor not in VALID_ANCHORS:
                    warnings.append(
                        f"Edge {edge_id}: invalid from_anchor '{from_anchor}', "
                        f"expected one of {VALID_ANCHORS}"
                    )
                if to_anchor and to_anchor not in VALID_ANCHORS:
                    warnings.append(
                        f"Edge {edge_id}: invalid to_anchor '{to_anchor}', "
                        f"expected one of {VALID_ANCHORS}"
                    )

                validated_edges.append(edge)

            # 更新 node_graph_json 的 edges
            node_graph_json["edges"] = validated_edges
            setattr(state, "node_graph_json", node_graph_json)

            # 记录 warnings
            if warnings:
                for w in warnings:
                    log.warning("[EdgePlanner] %s", w)

            log.info(
                "[EdgePlanner] Stage 1B: edges updated: %d edges added",
                len(validated_edges),
            )

            # 验证 edge_id 格式
            edge_ids = [e.get("edge_id", "") for e in validated_edges]
            invalid_edge_ids = [eid for eid in edge_ids if not eid.startswith("e")]

            if invalid_edge_ids:
                log.warning(
                    "[EdgePlanner] Invalid edge_ids found: %s",
                    invalid_edge_ids,
                )

            state.agent_results[self.role_name] = {
                "status": "ok",
                "stats": {
                    "edges": len(validated_edges),
                    "edge_ids": edge_ids,
                    "warnings": warnings,
                },
            }
        else:
            log.warning(
                "[EdgePlanner] Invalid result: expected dict with 'edges' key, got %s",
                type(result),
            )
            state.agent_results[self.role_name] = {
                "status": "failed",
                "error": f"Invalid result: expected dict with 'edges' key",
            }


async def p2g_filmstrip_edge_planner_agent(
    state: FilmStripP2GState,
    model_name: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 8192,
    **kwargs,
) -> FilmStripP2GState:
    """Film-Strip Edge Planner Agent 入口函数

    Args:
        state: FilmStripP2GState 状态对象（需要已有 node_graph_json.nodes）
        model_name: LLM 模型名称，默认使用 state.request.model
        temperature: 采样温度
        max_tokens: 最大 token 数

    Returns:
        更新后的 FilmStripP2GState（node_graph_json.edges 已填充）
    """
    if model_name is None:
        model_name = getattr(state.request, "model", "gpt-4o")

    # 检查 node_graph_json 是否存在且有 nodes
    node_graph_json = getattr(state, "node_graph_json", {})
    nodes = node_graph_json.get("nodes", [])

    if not nodes:
        log.warning("[EdgePlanner] No nodes found in node_graph_json, skipping edge planning")
        return state

    target = getattr(state.request, "target", "")
    if not target:
        log.warning("[EdgePlanner] target is empty")
        return state

    log.info(
        "[EdgePlanner] Starting Stage 1B with %d nodes, target: %s...",
        len(nodes),
        target[:100],
    )

    # 创建 agent 实例
    agent = P2gFilmstripEdgePlannerAgent.create(
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        parser_type="json",
    )

    # 执行 agent
    await agent.execute(
        state,
        use_agent=False,
        pre_tool_results={"state": state},
    )

    return state
