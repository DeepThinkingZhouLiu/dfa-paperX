"""p2g_filmstrip_render_method_classifier_agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Film-Strip Pipeline Stage 2: Render Method Classifier Agent

对 Stage 1 的 nodes 做渲染策略分类：
- VLM：具象视觉内容（输入图/分割图/热力图/示例图/小插画/图标等）
- PPTX：文本框、基础形状、流程模块框、纯几何容器、简单箭头说明等（强调可编辑）

输入：
- state.node_graph_json: 节点图结构

输出：
- state.render_plan_json: 渲染计划 {vlm_nodes, pptx_nodes, by_node}
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


@register("p2g_filmstrip_render_method_classifier_agent")
class P2gFilmstripRenderMethodClassifierAgent(BaseAgent):
    """Film-Strip Pipeline Stage 2: Render Method Classifier Agent

    对 nodes 做渲染策略分类：VLM vs PPTX。
    """

    def __init__(self, tool_manager: Optional[ToolManager] = None, **kwargs):
        super().__init__(tool_manager=tool_manager, **kwargs)

    @classmethod
    def create(cls, tool_manager: Optional[ToolManager] = None, **kwargs):
        return cls(tool_manager=tool_manager, **kwargs)

    @property
    def role_name(self) -> str:
        return "p2g_filmstrip_render_method_classifier_agent"

    @property
    def system_prompt_template_name(self) -> str:
        return "system_prompt_for_filmstrip_render_method_classifier"

    @property
    def task_prompt_template_name(self) -> str:
        return "task_prompt_for_filmstrip_render_method_classifier"

    def get_task_prompt_params(self, pre_tool_results: Dict[str, Any]) -> Dict[str, Any]:
        """构建任务 prompt 参数"""
        state: FilmStripP2GState = pre_tool_results.get("state")

        node_graph_json = {}
        if state:
            node_graph_json = getattr(state, "node_graph_json", {})

        return {
            "node_graph_json": json.dumps(node_graph_json, indent=2, ensure_ascii=False)
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
        """更新 state.render_plan_json"""
        if isinstance(result, dict):
            # 验证必要字段
            required_fields = ["vlm_nodes", "pptx_nodes", "by_node"]
            missing_fields = [f for f in required_fields if f not in result]

            if not missing_fields:
                setattr(state, "render_plan_json", result)

                vlm_nodes = result.get("vlm_nodes", [])
                pptx_nodes = result.get("pptx_nodes", [])
                by_node = result.get("by_node", {})

                log.info(
                    "[RenderMethodClassifier] render_plan_json updated: %d VLM nodes, %d PPTX nodes",
                    len(vlm_nodes),
                    len(pptx_nodes),
                )

                # 验证 by_node 中的节点数量是否匹配
                total_classified = len(vlm_nodes) + len(pptx_nodes)
                if len(by_node) != total_classified:
                    log.warning(
                        "[RenderMethodClassifier] by_node count (%d) != vlm_nodes + pptx_nodes (%d)",
                        len(by_node),
                        total_classified,
                    )

                state.agent_results[self.role_name] = {
                    "status": "ok",
                    "stats": {
                        "vlm_nodes": len(vlm_nodes),
                        "pptx_nodes": len(pptx_nodes),
                        "vlm_node_ids": vlm_nodes,
                        "pptx_node_ids": pptx_nodes,
                    },
                }
            else:
                log.warning(
                    "[RenderMethodClassifier] Invalid result: missing fields %s",
                    missing_fields,
                )
                state.agent_results[self.role_name] = {
                    "status": "failed",
                    "error": f"Invalid result: missing fields {missing_fields}",
                }
        else:
            log.warning(
                "[RenderMethodClassifier] Result is not a dict: %s", type(result)
            )
            state.agent_results[self.role_name] = {
                "status": "failed",
                "error": f"Result is not a dict: {type(result)}",
            }


async def p2g_filmstrip_render_method_classifier_agent(
    state: FilmStripP2GState,
    model_name: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 8192,
    **kwargs,
) -> FilmStripP2GState:
    """Film-Strip Render Method Classifier Agent 入口函数

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

    node_graph_json = getattr(state, "node_graph_json", {})
    nodes = node_graph_json.get("nodes", [])

    if not nodes:
        log.warning("[RenderMethodClassifier] node_graph_json has no nodes")
        setattr(
            state,
            "render_plan_json",
            {
                "vlm_nodes": [],
                "pptx_nodes": [],
                "by_node": {},
            },
        )
        return state

    log.info("[RenderMethodClassifier] Starting with %d nodes", len(nodes))

    # 创建 agent 实例
    agent = P2gFilmstripRenderMethodClassifierAgent.create(
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
