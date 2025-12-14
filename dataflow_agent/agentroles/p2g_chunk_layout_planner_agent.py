"""p2g_chunk_layout_planner_agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Chunk-Based Pipeline 的布局规划 Agent

根据语义结构规划各 chunk 的位置和大小。

输入：
- state.semantic_json: 语义结构 {title, chunks: [{chunk_id, chunk_content}]}
- state.request.canvas_width/height: 画布尺寸

输出：
- state.chunk_layout_json: 布局信息 {canvas, chunks: [{chunk_id, bbox}]}
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from dataflow_agent.state import MainState, ChunkP2GState
from dataflow_agent.toolkits.tool_manager import ToolManager
from dataflow_agent.logger import get_logger
from dataflow_agent.agentroles.base_agent import BaseAgent
from dataflow_agent.agentroles.registry import register

log = get_logger(__name__)


# ============================================================================
# Prompt Templates
# ============================================================================

SYSTEM_PROMPT = """You are an expert layout designer for scientific diagrams. Your task is to create precise, professional layouts for publication-ready figures.

## Your Expertise
- Creating balanced, visually appealing layouts
- Optimizing space utilization (target: 50-75%)
- Ensuring clear visual hierarchy and flow
- Preventing overlaps and maintaining proper spacing

## Layout Principles
1. **Flow Direction**: Main flow should be left-to-right or top-to-bottom
2. **Hierarchy**: Important chunks should be larger and more central
3. **Grouping**: Related chunks should be visually close
4. **Balance**: Distribute visual weight evenly across the canvas
5. **Spacing**: Maintain consistent gaps between chunks (min 30px)

## Output Requirements
You must output a valid JSON object with precise pixel coordinates."""

TASK_PROMPT_TEMPLATE = """## Task
Create a layout plan for the following chunks.

## Canvas Size
- Width: {canvas_width}px
- Height: {canvas_height}px
- Margins: 50px on all sides (usable area: {usable_width}x{usable_height}px)

## Chunks to Layout
```json
{semantic_json}
```

## Layout Requirements
1. Position each chunk within the usable canvas area (50px margins)
2. Chunks must NOT overlap
3. Minimum gap between chunks: 30px
4. Allocate space based on chunk_content complexity (longer content = larger area)
5. Ensure total chunk area is 50-75% of usable canvas area
6. Consider logical flow when positioning (e.g., data flow left-to-right)

## Output Schema
```json
{{
  "canvas": {{
    "width": {canvas_width},
    "height": {canvas_height}
  }},
  "chunks": [
    {{
      "chunk_id": "c1",
      "bbox": {{
        "x": 50,
        "y": 50,
        "w": 500,
        "h": 400
      }}
    }},
    {{
      "chunk_id": "c2",
      "bbox": {{
        "x": 580,
        "y": 50,
        "w": 400,
        "h": 300
      }}
    }}
  ]
}}
```

## Important Notes
- All coordinates are in pixels
- bbox.x and bbox.y are the top-left corner position
- bbox.w and bbox.h are width and height
- Ensure all chunks fit within the canvas (considering margins)
- The aspect ratio (w/h) of each chunk will be used for VLM rendering

Now create the layout JSON:"""


@register("p2g_chunk_layout_planner_agent")
class P2gChunkLayoutPlannerAgent(BaseAgent):
    """Chunk-Based Pipeline 的布局规划 Agent

    只规划 chunk 的位置和大小，不涉及内部布局。
    """

    def __init__(self, tool_manager: Optional[ToolManager] = None, **kwargs):
        super().__init__(tool_manager=tool_manager, **kwargs)

    @classmethod
    def create(cls, tool_manager: Optional[ToolManager] = None, **kwargs):
        return cls(tool_manager=tool_manager, **kwargs)

    @property
    def role_name(self) -> str:
        return "p2g_chunk_layout_planner_agent"

    @property
    def system_prompt_template_name(self) -> str:
        return ""

    @property
    def task_prompt_template_name(self) -> str:
        return ""

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def get_task_prompt(self, pre_tool_results: Dict[str, Any]) -> str:
        state: ChunkP2GState = pre_tool_results.get("state")

        canvas_width = 1920
        canvas_height = 1080
        semantic_json = {}

        if state:
            if hasattr(state, "request"):
                canvas_width = getattr(state.request, "canvas_width", 1920)
                canvas_height = getattr(state.request, "canvas_height", 1080)
            semantic_json = getattr(state, "semantic_json", {})

        usable_width = canvas_width - 100
        usable_height = canvas_height - 100

        return TASK_PROMPT_TEMPLATE.format(
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            usable_width=usable_width,
            usable_height=usable_height,
            semantic_json=json.dumps(semantic_json, indent=2, ensure_ascii=False),
        )

    def build_messages(self, state: MainState, pre_tool_results: Dict[str, Any]):
        pre_tool_results_with_state = {**pre_tool_results, "state": state}

        system_prompt = self.get_system_prompt()
        task_prompt = self.get_task_prompt(pre_tool_results_with_state)

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task_prompt},
        ]

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
        """更新 state.chunk_layout_json"""
        if isinstance(result, dict):
            if "chunks" in result:
                setattr(state, "chunk_layout_json", result)

                chunks = result.get("chunks", [])

                log.info(
                    "[ChunkLayoutPlanner] chunk_layout_json updated: %d chunks",
                    len(chunks),
                )

                state.agent_results[self.role_name] = {
                    "status": "ok",
                    "stats": {
                        "chunks": len(chunks),
                    }
                }
            else:
                log.warning("[ChunkLayoutPlanner] Invalid result: missing chunks")
                state.agent_results[self.role_name] = {
                    "status": "failed",
                    "error": "Invalid result: missing chunks",
                }
        else:
            log.warning("[ChunkLayoutPlanner] Result is not a dict")
            state.agent_results[self.role_name] = {
                "status": "failed",
                "error": f"Result is not a dict: {type(result)}",
            }


async def p2g_chunk_layout_planner_agent(
    state: ChunkP2GState,
    model_name: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    **kwargs,
) -> ChunkP2GState:
    """Chunk-Based 布局规划 Agent 入口函数

    Args:
        state: ChunkP2GState 状态对象
        model_name: LLM 模型名称
        temperature: 采样温度
        max_tokens: 最大 token 数

    Returns:
        更新后的 ChunkP2GState
    """
    if model_name is None:
        model_name = getattr(state.request, "model", "gpt-4o")

    semantic_json = getattr(state, "semantic_json", {})
    if not semantic_json or not semantic_json.get("chunks"):
        log.warning("[ChunkLayoutPlanner] semantic_json is empty or has no chunks")
        canvas_width = getattr(state.request, "canvas_width", 1920)
        canvas_height = getattr(state.request, "canvas_height", 1080)
        setattr(state, "chunk_layout_json", {
            "canvas": {"width": canvas_width, "height": canvas_height},
            "chunks": [],
        })
        return state

    log.info(
        "[ChunkLayoutPlanner] Starting with %d chunks",
        len(semantic_json.get("chunks", [])),
    )

    agent = P2gChunkLayoutPlannerAgent.create(
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        parser_type="json",
    )

    await agent.execute(
        state,
        use_agent=False,
        pre_tool_results={"state": state},
    )

    return state
