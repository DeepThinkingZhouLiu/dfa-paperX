"""p2g_filmstrip_pptx_spec_generator_agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Film-Strip Pipeline Stage 4: PPTX Spec Generator Agent

为 PPTX 节点生成结构化渲染规格（PPTXRenderSpec）。

输入：
- state.node_graph_json: 节点图结构
- state.render_plan_json: 渲染计划（包含 pptx_nodes 列表）

输出：
- state.pptx_render_specs: {node_id: PPTXRenderSpec}
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


@register("p2g_filmstrip_pptx_spec_generator_agent")
class P2gFilmstripPPTXSpecGeneratorAgent(BaseAgent):
    """Film-Strip Pipeline Stage 4: PPTX Spec Generator Agent

    为 PPTX 节点生成结构化渲染规格。
    """

    def __init__(self, tool_manager: Optional[ToolManager] = None, **kwargs):
        super().__init__(tool_manager=tool_manager, **kwargs)

    @classmethod
    def create(cls, tool_manager: Optional[ToolManager] = None, **kwargs):
        return cls(tool_manager=tool_manager, **kwargs)

    @property
    def role_name(self) -> str:
        return "p2g_filmstrip_pptx_spec_generator_agent"

    @property
    def system_prompt_template_name(self) -> str:
        return "system_prompt_for_filmstrip_pptx_spec_generator"

    @property
    def task_prompt_template_name(self) -> str:
        return "task_prompt_for_filmstrip_pptx_spec_generator"

    def get_task_prompt_params(self, pre_tool_results: Dict[str, Any]) -> Dict[str, Any]:
        """构建任务 prompt 参数"""
        state: FilmStripP2GState = pre_tool_results.get("state")

        node_graph_json = {}
        render_plan_json = {}

        if state:
            node_graph_json = getattr(state, "node_graph_json", {})
            render_plan_json = getattr(state, "render_plan_json", {})

        return {
            "node_graph_json": json.dumps(node_graph_json, indent=2, ensure_ascii=False),
            "render_plan_json": json.dumps(render_plan_json, indent=2, ensure_ascii=False),
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
        """更新 state.pptx_render_specs"""
        if isinstance(result, dict):
            # 验证每个 spec 的结构
            valid_specs = {}
            required_fields = ["element_type", "text", "text_style", "shape_style"]

            for node_id, spec in result.items():
                if not isinstance(spec, dict):
                    log.warning(
                        "[PPTXSpecGenerator] Invalid spec for %s: not a dict",
                        node_id,
                    )
                    continue

                missing_fields = [f for f in required_fields if f not in spec]
                if missing_fields:
                    log.warning(
                        "[PPTXSpecGenerator] Spec for %s missing fields: %s",
                        node_id,
                        missing_fields,
                    )
                    # 仍然保留，因为可能有默认值

                valid_specs[node_id] = spec

            if valid_specs:
                setattr(state, "pptx_render_specs", valid_specs)

                log.info(
                    "[PPTXSpecGenerator] pptx_render_specs updated: %d specs",
                    len(valid_specs),
                )

                # 统计 element_type 分布
                element_types = {}
                for spec in valid_specs.values():
                    et = spec.get("element_type", "unknown")
                    element_types[et] = element_types.get(et, 0) + 1

                state.agent_results[self.role_name] = {
                    "status": "ok",
                    "stats": {
                        "spec_count": len(valid_specs),
                        "node_ids": list(valid_specs.keys()),
                        "element_types": element_types,
                    },
                }
            else:
                log.warning("[PPTXSpecGenerator] No valid specs found in result")
                state.agent_results[self.role_name] = {
                    "status": "failed",
                    "error": "No valid specs found in result",
                }
        else:
            log.warning(
                "[PPTXSpecGenerator] Result is not a dict: %s", type(result)
            )
            state.agent_results[self.role_name] = {
                "status": "failed",
                "error": f"Result is not a dict: {type(result)}",
            }


async def p2g_filmstrip_pptx_spec_generator_agent(
    state: FilmStripP2GState,
    model_name: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 8192,
    **kwargs,
) -> FilmStripP2GState:
    """Film-Strip PPTX Spec Generator Agent 入口函数

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
    pptx_nodes = render_plan_json.get("pptx_nodes", [])

    if not pptx_nodes:
        log.warning("[PPTXSpecGenerator] No PPTX nodes to process")
        setattr(state, "pptx_render_specs", {})
        return state

    log.info("[PPTXSpecGenerator] Starting with %d PPTX nodes", len(pptx_nodes))

    # 创建 agent 实例
    agent = P2gFilmstripPPTXSpecGeneratorAgent.create(
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
