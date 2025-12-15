"""p2g_filmstrip_node_graph_constructor_agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Film-Strip Pipeline Stage 1A: Node Graph Constructor Agent (Nodes Only)

从用户的 target 描述中构建节点图（只有 nodes，edges 置空），不做布局、不做渲染方式决策。

输入：
- state.request.target: 用户的论文方法描述

输出：
- state.node_graph_json: 节点图结构 {title, global_style, nodes, edges=[]}

注意：edges 由 Stage1B (p2g_filmstrip_edge_planner_agent) 单独生成。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from dataflow_agent.state import MainState, FilmStripP2GState
from dataflow_agent.toolkits.tool_manager import ToolManager
from dataflow_agent.logger import get_logger
from dataflow_agent.agentroles.base_agent import BaseAgent
from dataflow_agent.agentroles.registry import register

log = get_logger(__name__)


@register("p2g_filmstrip_node_graph_constructor_agent")
class P2gFilmstripNodeGraphConstructorAgent(BaseAgent):
    """Film-Strip Pipeline Stage 1: Node Graph Constructor Agent

    从用户描述中构建节点图（nodes + edges），不做布局和渲染决策。
    """

    def __init__(self, tool_manager: Optional[ToolManager] = None, **kwargs):
        super().__init__(tool_manager=tool_manager, **kwargs)

    @classmethod
    def create(cls, tool_manager: Optional[ToolManager] = None, **kwargs):
        return cls(tool_manager=tool_manager, **kwargs)

    @property
    def role_name(self) -> str:
        return "p2g_filmstrip_node_graph_constructor_agent"

    @property
    def system_prompt_template_name(self) -> str:
        return "system_prompt_for_filmstrip_node_graph_constructor"

    @property
    def task_prompt_template_name(self) -> str:
        return "task_prompt_for_filmstrip_node_graph_constructor"

    def get_task_prompt_params(self, pre_tool_results: Dict[str, Any]) -> Dict[str, Any]:
        """构建任务 prompt 参数"""
        state: FilmStripP2GState = pre_tool_results.get("state")

        target = ""
        if state and hasattr(state, "request"):
            target = getattr(state.request, "target", "")

        return {"target": target}

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
        """更新 state.node_graph_json (Stage 1A: nodes only, edges forced to [])"""
        if isinstance(result, dict):
            # 验证必要字段 (edges 不再是必须的，会被强制置空)
            required_fields = ["title", "nodes"]
            missing_fields = [f for f in required_fields if f not in result]

            if not missing_fields:
                # Stage 1A: 强制将 edges 置为空数组
                result["edges"] = []

                setattr(state, "node_graph_json", result)

                nodes = result.get("nodes", [])

                log.info(
                    "[NodeGraphConstructor] Stage 1A: node_graph_json updated: %d nodes (edges forced to [])",
                    len(nodes),
                )

                # 验证 node_id 格式
                node_ids = [n.get("node_id", "") for n in nodes]

                invalid_node_ids = [nid for nid in node_ids if not nid.startswith("n")]

                if invalid_node_ids:
                    log.warning(
                        "[NodeGraphConstructor] Invalid node_ids found: %s",
                        invalid_node_ids,
                    )

                state.agent_results[self.role_name] = {
                    "status": "ok",
                    "stats": {
                        "nodes": len(nodes),
                        "edges": 0,  # Stage 1A always outputs 0 edges
                        "node_ids": node_ids,
                    },
                }
            else:
                log.warning(
                    "[NodeGraphConstructor] Invalid result: missing fields %s",
                    missing_fields,
                )
                state.agent_results[self.role_name] = {
                    "status": "failed",
                    "error": f"Invalid result: missing fields {missing_fields}",
                }
        else:
            log.warning(
                "[NodeGraphConstructor] Result is not a dict: %s", type(result)
            )
            state.agent_results[self.role_name] = {
                "status": "failed",
                "error": f"Result is not a dict: {type(result)}",
            }


async def p2g_filmstrip_node_graph_constructor_agent(
    state: FilmStripP2GState,
    model_name: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 8192,
    **kwargs,
) -> FilmStripP2GState:
    """Film-Strip Node Graph Constructor Agent 入口函数

    Args:
        state: FilmStripP2GState 状态对象
        model_name: LLM 模型名称，默认使用 state.request.model
        temperature: 采样温度
        max_tokens: 最大 token 数

    Returns:
        更新后的 FilmStripP2GState
    """
    if model_name is None:
        model_name = getattr(state.request, "model", "gpt-4o")

    target = getattr(state.request, "target", "")
    if not target:
        log.warning("[NodeGraphConstructor] target is empty")
        setattr(
            state,
            "node_graph_json",
            {
                "title": "",
                "global_style": {},
                "nodes": [],
                "edges": [],
            },
        )
        return state

    log.info("[NodeGraphConstructor] Starting with target: %s...", target[:100])

    # 创建 agent 实例
    agent = P2gFilmstripNodeGraphConstructorAgent.create(
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
