"""p2g_pptx_composer_agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Paper2Graph Pipeline 最终阶段：
将布局信息、PPTX 渲染规格、VLM 图片组装成最终的 PowerPoint 文件。

输入:
    - state.layout_json: 布局信息
    - state.pptx_render_specs: PPTX 节点结构化规格
    - state.vlm_rendered_nodes: VLM 图片路径
    - state.semantic_json: 语义信息（包含 edges）
    - state.node_render_design: 渲染设计

输出:
    - state.pptx_output_path: 生成的 PPTX 文件路径
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from dataflow_agent.state import MainState, Paper2GraphState
from dataflow_agent.toolkits.tool_manager import ToolManager
from dataflow_agent.logger import get_logger
from dataflow_agent.agentroles.base_agent import BaseAgent
from dataflow_agent.agentroles.registry import register

log = get_logger(__name__)


# ----------------------------------------------------------------------
# Agent Definition
# ----------------------------------------------------------------------
@register("p2g_pptx_composer_agent")
class P2gPptxComposerAgent(BaseAgent):
    """PPTX 组装 Agent
    
    特殊的 Agent：不调用 LLM，直接执行渲染逻辑。
    """

    # ---------- 工厂 ----------
    @classmethod
    def create(cls, tool_manager: Optional[ToolManager] = None, **kwargs):
        return cls(tool_manager=tool_manager, **kwargs)

    # ---------- 基本配置 ----------
    @property
    def role_name(self) -> str:
        return "p2g_pptx_composer_agent"

    @property
    def system_prompt_template_name(self) -> str:
        return ""  # 不使用 LLM

    @property
    def task_prompt_template_name(self) -> str:
        return ""  # 不使用 LLM

    def get_task_prompt_params(self, pre_tool_results: Dict[str, Any]) -> Dict[str, Any]:
        return {}

    def get_default_pre_tool_results(self) -> Dict[str, Any]:
        return {}

    def update_state_result(
        self,
        state: MainState,
        result: Dict[str, Any],
        pre_tool_results: Dict[str, Any],
    ):
        """更新 state"""
        pstate: Paper2GraphState = state
        
        if isinstance(result, dict):
            if "output_path" in result:
                pstate.pptx_output_path = result["output_path"]
            
            state.agent_results[self.role_name] = {
                "status": result.get("status", "ok"),
                "stats": result.get("stats", {}),
            }


# ----------------------------------------------------------------------
# Helper API
# ----------------------------------------------------------------------
async def p2g_pptx_composer_agent(
    state: MainState,
    output_path: Optional[str] = None,
    render_edges: bool = True,
    render_chunk_bg: bool = False,
    slide_width: int = 1920,
    slide_height: int = 1080,
    **kwargs,
) -> MainState:
    """PPTX 组装入口
    
    Args:
        state: Paper2GraphState，需包含:
            - layout_json
            - pptx_render_specs
            - vlm_rendered_nodes
            - semantic_json
            - node_render_design
        output_path: 输出路径，默认自动生成
        render_edges: 是否渲染连接线
        render_chunk_bg: 是否渲染 chunk 背景
        slide_width: 幻灯片宽度（像素）
        slide_height: 幻灯片高度（像素）
        
    Returns:
        更新后的 MainState，包含 pptx_output_path
    """
    from dataflow_agent.toolkits.pptx_composer import PPTXBuilder
    
    pstate: Paper2GraphState = state
    
    # 验证输入
    if not pstate.layout_json:
        raise ValueError("layout_json is required")
    if not pstate.node_render_design:
        raise ValueError("node_render_design is required")
    
    # 默认输出路径
    if not output_path:
        output_dir = Path("output")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / "paper2graph_output.pptx")
    
    log.info("Starting PPTX composition...")
    log.info(f"  - Output path: {output_path}")
    log.info(f"  - Slide size: {slide_width}x{slide_height}")
    log.info(f"  - Render edges: {render_edges}")
    log.info(f"  - Render chunk bg: {render_chunk_bg}")
    
    try:
        # 构建 PPTX
        builder = PPTXBuilder(
            width_px=slide_width,
            height_px=slide_height,
        )
        
        builder.build(
            layout_json=pstate.layout_json,
            node_render_design=pstate.node_render_design,
            pptx_render_specs=pstate.pptx_render_specs or {},
            vlm_rendered_nodes=pstate.vlm_rendered_nodes or {},
            semantic_json=pstate.semantic_json or {},
            render_edges=render_edges,
            render_chunk_bg=render_chunk_bg,
        )
        
        # 保存
        saved_path = builder.save(output_path)
        
        # 更新 state
        pstate.pptx_output_path = saved_path
        pstate.agent_results["p2g_pptx_composer_agent"] = {
            "status": "ok",
            "stats": builder.stats,
            "output_path": saved_path,
        }

        log.info(f"PPTX composition complete: {saved_path}")

    except Exception as e:
        log.error(f"PPTX composition failed: {e}")
        pstate.agent_results["p2g_pptx_composer_agent"] = {
            "status": "failed",
            "error": str(e),
        }
        raise

    return pstate


def create_p2g_pptx_composer_agent(
    tool_manager: Optional[ToolManager] = None,
    **kwargs,
) -> P2gPptxComposerAgent:
    """创建 P2gPptxComposerAgent 实例"""
    return P2gPptxComposerAgent.create(tool_manager=tool_manager, **kwargs)

