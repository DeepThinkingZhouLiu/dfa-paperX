"""p2g_pptx_desc_parser_agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

将 node_render_design 中 pptx 类型节点的 pptx_desc 自然语言描述
解析为结构化的 PPTXRenderSpec JSON，供下游 pptx_composer_agent 使用。

输入: state.node_render_design (包含 pptx_desc)
输出: state.pptx_render_specs (node_id -> PPTXRenderSpec)
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from dataflow_agent.state import MainState, Paper2GraphState
from dataflow_agent.toolkits.tool_manager import ToolManager
from dataflow_agent.logger import get_logger
from dataflow_agent.agentroles.base_agent import BaseAgent
from dataflow_agent.agentroles.registry import register
from dataflow_agent.utils import robust_parse_json

log = get_logger(__name__)


# ----------------------------------------------------------------------
# Agent Definition
# ----------------------------------------------------------------------
@register("p2g_pptx_desc_parser_agent")
class P2gPptxDescParserAgent(BaseAgent):
    """批量解析 pptx_desc 为结构化 PPTXRenderSpec"""

    # ---------- 工厂 ----------
    @classmethod
    def create(cls, tool_manager: Optional[ToolManager] = None, **kwargs):
        return cls(tool_manager=tool_manager, **kwargs)

    # ---------- 基本配置 ----------
    @property
    def role_name(self) -> str:
        return "p2g_pptx_desc_parser_agent"

    @property
    def system_prompt_template_name(self) -> str:
        return "system_prompt_for_p2g_pptx_desc_parser_agent"

    @property
    def task_prompt_template_name(self) -> str:
        return "task_prompt_for_p2g_pptx_desc_parser_agent"

    # ---------- 构建消息：注入 state ----------
    def build_messages(self, state: MainState, pre_tool_results: Dict[str, Any]):
        """自定义消息构建，将 state 注入 pre_tool_results。"""
        pre_tool_results_with_state = {**pre_tool_results, "state": state}
        return super().build_messages(state, pre_tool_results_with_state)

    # ---------- Prompt 参数 ----------
    def get_task_prompt_params(self, pre_tool_results: Dict[str, Any]) -> Dict[str, Any]:
        """从 state.node_render_design 中提取所有 pptx 类型节点。"""
        state: Paper2GraphState = pre_tool_results.get("state")
        
        node_render_design = getattr(state, "node_render_design", None) or {}
        if not node_render_design:
            raise ValueError(
                "p2g_pptx_desc_parser_agent: node_render_design 为空，"
                "请确保已成功运行 p2g_node_render_design_agent。"
            )
        
        # 收集所有 pptx 类型节点
        pptx_nodes = []
        for chunk in node_render_design.get("chunks", []):
            for node in chunk.get("nodes", []):
                if node.get("render_method") == "pptx":
                    pptx_nodes.append({
                        "node_id": node.get("node_id", ""),
                        "pptx_desc": node.get("pptx_desc", "")
                    })
        
        if not pptx_nodes:
            log.warning("No pptx nodes found in node_render_design")
        
        log.info(
            "p2g_pptx_desc_parser_agent: Found %d pptx nodes to parse",
            len(pptx_nodes)
        )
        
        return {
            "pptx_nodes": json.dumps(pptx_nodes, ensure_ascii=False, indent=2),
            "node_count": len(pptx_nodes)
        }

    def get_default_pre_tool_results(self) -> Dict[str, Any]:
        return {}

    # ---------- 结果写回 ----------
    def update_state_result(
        self,
        state: MainState,
        result: Dict[str, Any],
        pre_tool_results: Dict[str, Any],
    ):
        """将解析结果写入 state.pptx_render_specs"""
        try:
            pstate: Paper2GraphState = state
            
            # 处理上游错误
            if isinstance(result, dict) and "error" in result:
                error_msg = str(result.get("error"))
                state.agent_results[self.role_name] = {"status": "failed", "error": error_msg}
                raise ValueError(error_msg)
            
            # 健壮解析 LLM 输出
            try:
                parsed = result if isinstance(result, dict) else robust_parse_json(str(result))
                if not isinstance(parsed, dict):
                    raise ValueError("LLM 输出无法解析为 JSON 对象")
            except Exception as parse_err:
                raw_preview = str(result)[:300] if result else "<empty>"
                error_msg = f"JSON 解析失败: {parse_err}. 原始输出: {raw_preview}"
                state.agent_results[self.role_name] = {"status": "failed", "error": error_msg}
                raise ValueError(error_msg) from parse_err
            
            # 提取 specs（兼容可能的嵌套结构）
            specs = parsed.get("specs", parsed)
            if not isinstance(specs, dict):
                error_msg = f"specs 不是 dict 类型: {type(specs)}"
                state.agent_results[self.role_name] = {"status": "failed", "error": error_msg}
                raise ValueError(error_msg)
            
            # 写入 state
            pstate.pptx_render_specs = specs
            
            # 统计信息
            stats = {
                "total_specs": len(specs),
                "node_ids": list(specs.keys())[:10],  # 只记录前10个
            }
            state.agent_results[self.role_name] = {"status": "ok", "stats": stats}
            log.info("p2g_pptx_desc_parser_agent: Parsed %d pptx specs", len(specs))
            
        except Exception as e:
            if self.role_name not in state.agent_results:
                state.agent_results[self.role_name] = {"status": "failed", "error": str(e)}
            raise


# ----------------------------------------------------------------------
# Helper APIs
# ----------------------------------------------------------------------
async def p2g_pptx_desc_parser_agent(
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
    """p2g_pptx_desc_parser_agent 的异步入口

    Args:
        state: 主状态对象，需包含 node_render_design
        model_name: 模型名称，如 "gpt-4" 或 "gemini-2.5-pro"
        tool_manager: 工具管理器实例
        temperature: 采样温度 (0.0-1.0)
        max_tokens: 最大生成 token 数
        tool_mode: 工具调用模式 ("auto", "none", "required")
        react_mode: 是否启用 ReAct 推理模式
        react_max_retries: ReAct 模式下最大重试次数
        parser_type: 解析器类型 ("json", "xml", "text")
        parser_config: 解析器配置字典
        use_vlm: 是否使用视觉语言模型
        vlm_config: VLM 配置字典
        use_agent: 是否使用 agent 模式
        **kwargs: 其他传递给 execute 的参数

    Returns:
        更新后的 MainState 对象，包含 pptx_render_specs
    """
    agent = P2gPptxDescParserAgent(
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
    pre_tool_results = {"state": state}
    return await agent.execute(state, use_agent=use_agent, pre_tool_results=pre_tool_results, **kwargs)


def create_p2g_pptx_desc_parser_agent(
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
) -> P2gPptxDescParserAgent:
    """创建 P2gPptxDescParserAgent 实例的工厂函数

    Args:
        tool_manager: 工具管理器实例
        model_name: 模型名称
        temperature: 采样温度
        max_tokens: 最大生成 token 数
        tool_mode: 工具调用模式
        react_mode: 是否启用 ReAct 推理模式
        react_max_retries: ReAct 模式下最大重试次数
        parser_type: 解析器类型
        parser_config: 解析器配置字典
        use_vlm: 是否使用视觉语言模型
        vlm_config: VLM 配置字典
        **kwargs: 其他参数

    Returns:
        P2gPptxDescParserAgent 实例
    """
    return P2gPptxDescParserAgent.create(
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

