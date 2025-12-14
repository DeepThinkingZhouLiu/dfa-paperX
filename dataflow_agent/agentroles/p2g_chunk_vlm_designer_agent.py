"""p2g_chunk_vlm_designer_agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Chunk-Based Pipeline 的 VLM Prompt 设计 Agent

为每个 chunk 生成 VLM 绘图 prompt 和宽高比。

输入：
- state.semantic_json: 语义结构 {chunks: [{chunk_id, chunk_content}]}
- state.chunk_layout_json: 布局信息 {canvas, chunks: [{chunk_id, bbox}]}

输出：
- state.chunk_vlm_designs: {chunk_id: {prompt, ratio}}
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

from dataflow_agent.state import MainState, ChunkP2GState
from dataflow_agent.toolkits.tool_manager import ToolManager
from dataflow_agent.logger import get_logger
from dataflow_agent.agentroles.base_agent import BaseAgent
from dataflow_agent.agentroles.registry import register

log = get_logger(__name__)


# ============================================================================
# VLM Prompt 模板
# ============================================================================

CHUNK_VLM_PROMPT_TEMPLATE = """Create a single cohesive scientific diagram illustration for a top-tier CS conference paper.

## Content to Draw
{chunk_content}

## Image Specifications
- Aspect Ratio: {ratio} (width:height) - MUST be preserved
- Style: Professional scientific illustration, flat 2D vector style
- Colors: Professional muted tones (Morandi palette)
  - Use blues (#4A90D9, #5B9BD5) for main modules
  - Use teals (#66c2a5, #7ECFC0) for data/datasets
  - Use coral (#fc8d62) for highlights/accents
  - Use dark gray (#333333) for text
- Background: Solid white
- Font: Clean sans-serif style

## Visual Style Guidelines
- Clean geometric shapes with rounded corners
- Minimalist design, no unnecessary decorations
- Clear visual hierarchy
- Professional arrows and connectors
- Readable text labels (not too small)

## IMPORTANT - DO NOT Include
- Photorealistic elements or textures
- Heavy 3D effects or shadows
- Gradients on shapes (flat colors only)
- Busy or cluttered backgrounds
- Watermarks or signatures

Generate a single, cohesive image with all elements described above."""


def _calculate_ratio_string(w: int, h: int) -> str:
    """根据宽高计算最接近的标准比例字符串

    Args:
        w: 宽度
        h: 高度

    Returns:
        比例字符串，如 "4:3", "16:9", "2:1", "1:1"
    """
    if h <= 0:
        return "4:3"

    ratio = w / h

    # 标准比例列表 (ratio_value, ratio_string)
    standard_ratios = [
        (1.0, "1:1"),
        (4/3, "4:3"),
        (3/2, "3:2"),
        (16/10, "16:10"),
        (16/9, "16:9"),
        (2/1, "2:1"),
        (21/9, "21:9"),
        (3/1, "3:1"),
        # 竖向比例
        (3/4, "3:4"),
        (2/3, "2:3"),
        (9/16, "9:16"),
        (1/2, "1:2"),
    ]

    # 找到最接近的标准比例
    closest_ratio = min(standard_ratios, key=lambda x: abs(x[0] - ratio))

    return closest_ratio[1]


def build_chunk_vlm_prompt(chunk_content: str, ratio: str) -> str:
    """为单个 chunk 构建 VLM prompt

    Args:
        chunk_content: chunk 的详细绘制描述
        ratio: 宽高比字符串，如 "4:3", "16:9"

    Returns:
        完整的 VLM prompt
    """
    return CHUNK_VLM_PROMPT_TEMPLATE.format(
        chunk_content=chunk_content,
        ratio=ratio,
    )


@register("p2g_chunk_vlm_designer_agent")
class P2gChunkVlmDesignerAgent(BaseAgent):
    """Chunk-Based Pipeline 的 VLM Prompt 设计 Agent

    这是一个纯计算 Agent，不调用 LLM，直接根据语义和布局信息生成 VLM prompt。
    """

    def __init__(self, tool_manager: Optional[ToolManager] = None, **kwargs):
        super().__init__(tool_manager=tool_manager, **kwargs)

    @classmethod
    def create(cls, tool_manager: Optional[ToolManager] = None, **kwargs):
        return cls(tool_manager=tool_manager, **kwargs)

    @property
    def role_name(self) -> str:
        return "p2g_chunk_vlm_designer_agent"

    @property
    def system_prompt_template_name(self) -> str:
        return ""

    @property
    def task_prompt_template_name(self) -> str:
        return ""

    def get_default_pre_tool_results(self) -> Dict[str, Any]:
        return {}

    def get_task_prompt_params(self, pre_tool_results: Dict[str, Any]) -> Dict[str, Any]:
        return {}

    def update_state_result(
        self,
        state: MainState,
        result: Dict[str, Any],
        pre_tool_results: Dict[str, Any],
    ):
        pass  # 由入口函数直接更新


async def p2g_chunk_vlm_designer_agent(
    state: ChunkP2GState,
    **kwargs,
) -> ChunkP2GState:
    """Chunk-Based VLM Prompt 设计 Agent 入口函数

    这是一个纯计算函数，不调用 LLM。

    Args:
        state: ChunkP2GState 状态对象

    Returns:
        更新后的 ChunkP2GState
    """
    semantic_json = getattr(state, "semantic_json", {})
    chunk_layout_json = getattr(state, "chunk_layout_json", {})

    if not semantic_json or not chunk_layout_json:
        log.warning("[ChunkVlmDesigner] semantic_json or chunk_layout_json is empty")
        setattr(state, "chunk_vlm_designs", {})
        return state

    # 构建索引
    chunks_semantic = {c["chunk_id"]: c for c in semantic_json.get("chunks", [])}
    chunks_layout = {c["chunk_id"]: c for c in chunk_layout_json.get("chunks", [])}

    # 为每个 chunk 生成 VLM prompt
    chunk_vlm_designs = {}

    for chunk_id, chunk_info in chunks_semantic.items():
        chunk_content = chunk_info.get("chunk_content", "")
        chunk_layout = chunks_layout.get(chunk_id, {})
        bbox = chunk_layout.get("bbox", {})

        if not chunk_content:
            log.warning("[ChunkVlmDesigner] No chunk_content for %s, skipping", chunk_id)
            continue

        if not bbox:
            log.warning("[ChunkVlmDesigner] No bbox for %s, using default ratio", chunk_id)
            ratio = "4:3"  # 默认宽高比
        else:
            w = bbox.get("w", 600)
            h = bbox.get("h", 400)
            ratio = _calculate_ratio_string(w, h)

        # 生成 prompt
        prompt = build_chunk_vlm_prompt(chunk_content, ratio)

        chunk_vlm_designs[chunk_id] = {
            "prompt": prompt,
            "ratio": ratio,
        }

        log.info(
            "[ChunkVlmDesigner] Generated prompt for %s: %d chars, ratio=%s",
            chunk_id, len(prompt), ratio,
        )

    setattr(state, "chunk_vlm_designs", chunk_vlm_designs)

    state.agent_results["p2g_chunk_vlm_designer_agent"] = {
        "status": "ok",
        "stats": {
            "chunks_designed": len(chunk_vlm_designs),
            "total_prompt_chars": sum(len(d["prompt"]) for d in chunk_vlm_designs.values()),
        }
    }

    log.info("[ChunkVlmDesigner] Completed: %d chunk prompts generated", len(chunk_vlm_designs))

    return state
