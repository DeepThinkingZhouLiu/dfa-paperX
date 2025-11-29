"""
P2gChunkLayoutPlannerAgent agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
生成时间: 2025-11-23

本 agent 负责根据 semantic_json + layout_desc 生成中间层的布局计划（layout_plan）。
layout_plan 包含 grid 级别的规划信息：
- global: grid_rows, grid_cols, flow_direction, notes
- chunks: 每个 chunk 的 row, col, span_row, span_col, size_hint, relation_note
"""

from __future__ import annotations

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
@register("p2g_chunk_layout_planner_agent")
class P2gChunkLayoutPlannerAgent(BaseAgent):
    """根据 semantic_json + layout_desc 生成 layout_plan（grid 级别布局规划）"""

    # ---------- 工厂 ----------
    @classmethod
    def create(cls, tool_manager: Optional[ToolManager] = None, **kwargs):
        return cls(tool_manager=tool_manager, **kwargs)

    # ---------- 基本配置 ----------
    @property
    def role_name(self) -> str:  # noqa: D401
        return "p2g_chunk_layout_planner_agent"

    @property
    def system_prompt_template_name(self) -> str:
        # 返回模板名称字符串，供 PromptsTemplateGenerator 渲染
        return "system_prompt_for_p2g_chunk_layout_planner_agent"

    @property
    def task_prompt_template_name(self) -> str:
        # 返回模板名称字符串，供 PromptsTemplateGenerator 渲染
        return "task_prompt_for_p2g_chunk_layout_planner_agent"

    # ---------- 构建消息：注入 state ----------
    def build_messages(self, state: MainState, pre_tool_results: Dict[str, Any]):
        """自定义消息构建，将 state 注入 pre_tool_results 以便 get_task_prompt_params 使用。"""
        # 将 state 添加到 pre_tool_results 中
        pre_tool_results_with_state = {**pre_tool_results, "state": state}
        # 调用父类的 build_messages 方法
        return super().build_messages(state, pre_tool_results_with_state)

    # ---------- Prompt 参数 ----------
    def get_task_prompt_params(self, pre_tool_results: Dict[str, Any]) -> Dict[str, Any]:
        """构造传入 LLM 的任务级 Prompt 参数.

        布局规划阶段依赖两类输入:
        1. semantic_json: 来自上游 semantic_constructor 的语义结构（chunks/nodes/edges）;
        2. layout_desc: 来自 enriched_description.layout_desc, 为自然语言形式的布局建议。
        3. semantic_desc: 来自 enriched_description.semantic_desc, 为自然语言形式的语义描述。
        """
        state: Paper2GraphState = pre_tool_results.get("state")  # 约定由 execute 传入
        
        # 获取 semantic_json
        semantic_json = getattr(state, "semantic_json", None) or {}
        if not semantic_json:
            raise ValueError(
                "p2g_chunk_layout_planner_agent: semantic_json 为空，请确保已成功运行 p2g_semantic_constructor_agent。"
            )
        
        # 从 enriched_description 中提取 layout_desc
        enriched = getattr(state, "enriched_description", {}) or {}
        layout_desc = ""
        
        if isinstance(enriched, dict):
            ld, sd = enriched.get("layout_desc"), enriched.get("semantic_desc")
            if isinstance(ld, str) and ld.strip() and isinstance(sd, str) and sd.strip():
                layout_desc = ld
                semantic_desc = sd

        
        if not layout_desc:
            raise ValueError(
                "p2g_chunk_layout_planner_agent: layout_desc 为空，请确保已成功运行 p2g_target_analyst 并写入 "
                "enriched_description.layout_desc."
            )
        
        if not semantic_desc:
            raise ValueError(
                "p2g_chunk_layout_planner_agent: semantic_desc 为空，请确保已成功运行 p2g_target_analyst 并写入 "
                "enriched_description.semantic_desc."
            )
        
        return {
            "semantic_json": semantic_json,
            "layout_desc": layout_desc,
            "semantic_desc": semantic_desc,
        }

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
        """将推理结果写回 Paper2GraphState.layout_plan，失败则报错返回，不做重试"""
        try:
            pstate: Paper2GraphState = state  # 类型别名
            # 若为上游错误，直接写入失败并返回
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
                # 附带原始输出前缀便于调试
                raw_output_preview = str(result)[:200] if result else "<empty>"
                error_msg = f"JSON 解析失败: {str(parse_err)}. 原始输出前缀: {raw_output_preview}"
                state.agent_results[self.role_name] = {"status": "failed", "error": error_msg}
                raise ValueError(error_msg) from parse_err

            # 处理 LLM 可能返回的嵌套结构：{"layout_plan": {"global": ..., "chunks": ...}}
            # 如果存在 layout_plan 键，则提取其内容
            if "layout_plan" in parsed:
                parsed = parsed["layout_plan"]

            # 基本结构校验
            if "global" not in parsed or "chunks" not in parsed:
                error_msg = "layout_plan 缺少必要字段 'global' 或 'chunks'"
                state.agent_results[self.role_name] = {"status": "failed", "error": error_msg}
                raise ValueError(error_msg)

            # 写入 state: 直接将实例化后的 layout_plan 写入, 供下游布局构建使用
            pstate.layout_plan = parsed

            # 简要统计信息
            stats = {
                "grid_rows": parsed.get("global", {}).get("grid_rows", 0),
                "grid_cols": parsed.get("global", {}).get("grid_cols", 0),
                "chunks_count": len(parsed.get("chunks", []) or []),
            }
            # 记录到 agent_results
            state.agent_results[self.role_name] = {"status": "ok", "stats": stats}
        except Exception as e:
            # 保持与"报错返回，不重试"的约定
            # 若未被之前的块处理，则这里捕获所有其他异常
            if self.role_name not in state.agent_results or "error" not in state.agent_results[self.role_name]:
                state.agent_results[self.role_name] = {"status": "failed", "error": str(e)}
            raise


# ----------------------------------------------------------------------
# Helper APIs
# ----------------------------------------------------------------------
async def p2g_layout_chunk_planner_agent(
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
    """p2g_chunk_layout_planner_agent 的异步入口
    
    Args:
        state: 主状态对象
        model_name: 模型名称，如 "gpt-4"
        tool_manager: 工具管理器实例
        temperature: 采样温度，控制随机性 (0.0-1.0)
        max_tokens: 最大生成token数
        tool_mode: 工具调用模式 ("auto", "none", "required")
        react_mode: 是否启用ReAct推理模式
        react_max_retries: ReAct模式下最大重试次数
        parser_type: 解析器类型 ("json", "xml", "text")
        parser_config: 解析器配置字典（如XML的root_tag）
        use_vlm: 是否使用视觉语言模型
        vlm_config: VLM配置字典
        use_agent: 是否使用agent模式
        **kwargs: 其他传递给execute的参数
        
    Returns:
        更新后的MainState对象
    """
    agent = P2gChunkLayoutPlannerAgent(
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
    # 将 state 作为 pre_tool_results 传入，以便构造 prompt 参数
    pre_tool_results = {"state": state}
    return await agent.execute(state, use_agent=use_agent, pre_tool_results=pre_tool_results, **kwargs)


def create_p2g_chunk_layout_planner_agent(
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
) -> P2gChunkLayoutPlannerAgent:
    """创建 P2gChunkLayoutPlannerAgent 实例的工厂函数
    
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
        P2gChunkLayoutPlannerAgent实例
    """
    return P2gChunkLayoutPlannerAgent.create(
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
