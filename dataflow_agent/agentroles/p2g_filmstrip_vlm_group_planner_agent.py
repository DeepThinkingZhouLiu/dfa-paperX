"""p2g_filmstrip_vlm_group_planner_agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Film-Strip Pipeline Stage 3: VLM Group Planner Agent

对 VLM 节点进行分组，并为每组生成连环画 prompt。

输入：
- state.node_graph_json: 节点图结构
- state.render_plan_json: 渲染计划（包含 vlm_nodes 列表）

输出：
- state.vlm_group_plan_json: 分组计划 {groups: [{group_id, node_ids, subject, prompt}]}
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


@register("p2g_filmstrip_vlm_group_planner_agent")
class P2gFilmstripVLMGroupPlannerAgent(BaseAgent):
    """Film-Strip Pipeline Stage 3: VLM Group Planner Agent

    对 VLM 节点进行分组，并为每组生成连环画 prompt。
    """

    def __init__(self, tool_manager: Optional[ToolManager] = None, **kwargs):
        super().__init__(tool_manager=tool_manager, **kwargs)

    @classmethod
    def create(cls, tool_manager: Optional[ToolManager] = None, **kwargs):
        return cls(tool_manager=tool_manager, **kwargs)

    @property
    def role_name(self) -> str:
        return "p2g_filmstrip_vlm_group_planner_agent"

    @property
    def system_prompt_template_name(self) -> str:
        return "system_prompt_for_filmstrip_vlm_group_planner"

    @property
    def task_prompt_template_name(self) -> str:
        return "task_prompt_for_filmstrip_vlm_group_planner"

    def get_task_prompt_params(self, pre_tool_results: Dict[str, Any]) -> Dict[str, Any]:
        """构建任务 prompt 参数"""
        state: FilmStripP2GState = pre_tool_results.get("state")

        node_graph_json = {}
        render_plan_json = {}
        max_vlm_group_size = 4

        if state:
            node_graph_json = getattr(state, "node_graph_json", {})
            render_plan_json = getattr(state, "render_plan_json", {})
            if hasattr(state, "request"):
                max_vlm_group_size = getattr(state.request, "max_vlm_group_size", 4)

        return {
            "node_graph_json": json.dumps(node_graph_json, indent=2, ensure_ascii=False),
            "render_plan_json": json.dumps(render_plan_json, indent=2, ensure_ascii=False),
            "max_vlm_group_size": max_vlm_group_size,
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
        """更新 state.vlm_group_plan_json"""
        if isinstance(result, dict):
            # 验证必要字段
            if "groups" not in result:
                log.warning(
                    "[VLMGroupPlanner] Invalid result: missing 'groups' field"
                )
                state.agent_results[self.role_name] = {
                    "status": "failed",
                    "error": "Invalid result: missing 'groups' field",
                }
                return

            groups = result.get("groups", [])

            # 验证每个 group 的结构
            valid_groups = []
            for i, group in enumerate(groups):
                required_fields = ["group_id", "node_ids", "subject", "prompt"]
                missing_fields = [f for f in required_fields if f not in group]

                if missing_fields:
                    log.warning(
                        "[VLMGroupPlanner] Group %d missing fields: %s",
                        i,
                        missing_fields,
                    )
                    continue

                if not isinstance(group.get("node_ids"), list) or len(group["node_ids"]) == 0:
                    log.warning(
                        "[VLMGroupPlanner] Group %s has invalid node_ids",
                        group.get("group_id", i),
                    )
                    continue

                valid_groups.append(group)

            if valid_groups:
                setattr(state, "vlm_group_plan_json", {"groups": valid_groups})

                # 统计信息
                total_nodes = sum(len(g["node_ids"]) for g in valid_groups)
                group_sizes = [len(g["node_ids"]) for g in valid_groups]

                log.info(
                    "[VLMGroupPlanner] vlm_group_plan_json updated: %d groups, %d total nodes",
                    len(valid_groups),
                    total_nodes,
                )

                state.agent_results[self.role_name] = {
                    "status": "ok",
                    "stats": {
                        "group_count": len(valid_groups),
                        "total_vlm_nodes": total_nodes,
                        "group_sizes": group_sizes,
                        "group_ids": [g["group_id"] for g in valid_groups],
                    },
                }
            else:
                log.warning("[VLMGroupPlanner] No valid groups found in result")
                state.agent_results[self.role_name] = {
                    "status": "failed",
                    "error": "No valid groups found in result",
                }
        else:
            log.warning(
                "[VLMGroupPlanner] Result is not a dict: %s", type(result)
            )
            state.agent_results[self.role_name] = {
                "status": "failed",
                "error": f"Result is not a dict: {type(result)}",
            }


async def p2g_filmstrip_vlm_group_planner_agent(
    state: FilmStripP2GState,
    model_name: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 8192,
    **kwargs,
) -> FilmStripP2GState:
    """Film-Strip VLM Group Planner Agent 入口函数

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

    render_plan_json = getattr(state, "render_plan_json", {})
    vlm_nodes = render_plan_json.get("vlm_nodes", [])

    if not vlm_nodes:
        log.warning("[VLMGroupPlanner] No VLM nodes to group")
        setattr(
            state,
            "vlm_group_plan_json",
            {"groups": []},
        )
        return state

    log.info("[VLMGroupPlanner] Starting with %d VLM nodes", len(vlm_nodes))

    # 创建 agent 实例
    agent = P2gFilmstripVLMGroupPlannerAgent.create(
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
