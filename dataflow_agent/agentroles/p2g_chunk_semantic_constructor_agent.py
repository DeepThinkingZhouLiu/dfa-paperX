"""p2g_chunk_semantic_constructor_agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Chunk-Based Pipeline 的语义构建 Agent（合并了 target_analysis 功能）

从用户的 target 描述中：
1. 理解绘图意图和核心概念
2. 将内容分解为多个 chunks
3. 为每个 chunk 生成详细的绘制描述

输入：
- state.request.target: 用户的论文方法描述

输出：
- state.semantic_json: 语义结构 {title, chunks: [{chunk_id, chunk_content}]}
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from dataflow_agent.state import MainState, ChunkP2GState
from dataflow_agent.toolkits.tool_manager import ToolManager
from dataflow_agent.logger import get_logger
from dataflow_agent.agentroles.base_agent import BaseAgent
from dataflow_agent.agentroles.registry import register

log = get_logger(__name__)


# ============================================================================
# Prompt Templates
# ============================================================================

SYSTEM_PROMPT = """You are an expert scientific diagram architect specializing in creating clear, professional visualizations for top-tier CS conference papers (NeurIPS, ICML, CVPR, ACL).

Your task is to analyze a research method description and decompose it into multiple visual chunks, each with a detailed content description that can be directly used for image generation.

## Your Expertise
- Understanding complex ML/AI pipelines and architectures
- Decomposing systems into visually coherent chunks
- Writing detailed visual descriptions for image generation
- Creating clear visual hierarchies

## Output Requirements
You must output a valid JSON object following the exact schema provided."""

TASK_PROMPT_TEMPLATE = """## Task
Analyze the following research method description and decompose it into multiple visual chunks for a scientific diagram.

## Input Description
{target}

## Chunk Design Principles
1. **Chunk Count**: Create {min_chunks}-{max_chunks} chunks (prefer fewer, more cohesive chunks)
2. **Chunk Cohesion**: Each chunk should represent a visually complete sub-diagram with a clear theme
3. **Merge Linear Flows**: Sequential steps (A→B→C) should be in ONE chunk, not separate chunks
4. **Separate Parallel Branches**: Parallel processes should be separate chunks
5. **Self-Contained**: Each chunk should be independently renderable without needing other chunks

## chunk_content Writing Guidelines
The `chunk_content` field should be a **detailed visual description** that includes:
- All visual elements (modules, datasets, text labels, icons) to be drawn
- The layout and arrangement of elements (left-to-right, top-to-bottom, etc.)
- Connections and arrows between elements within the chunk
- Colors, styles, and visual emphasis (if important)
- Any text labels, formulas, or annotations to include

Write `chunk_content` as if you are instructing an artist to draw this specific part of the diagram. Be specific and detailed.

## Output Schema
```json
{{
  "chunks": [
    {{
      "chunk_id": "c1",
      "chunk_content": "Detailed visual description of what to draw in this chunk. Include all elements, their arrangement, connections, labels, and visual style. This should be comprehensive enough for direct image generation."
    }},
    {{
      "chunk_id": "c2",
      "chunk_content": "..."
    }}
  ]
}}
```

## Example chunk_content
Good example:
"Draw a data pipeline flowing left-to-right. On the left, show a cylinder-shaped 'Expert Dataset D_expert' container with the formula '{{(s_i, a_i)}}' inside. An arrow points right to a rounded rectangle labeled 'LLM Policy π_0'. From this policy box, multiple arrows fan out to a group of small boxes representing 'K sampled actions {{a_i^1, ..., a_i^K}}'. Use professional blue (#4A90D9) for the policy module and teal (#66c2a5) for the dataset. Include a small annotation below stating 'Non-expert action sampling'."

Bad example (too vague):
"Show the data preparation process."

## Important Notes
- Chunk IDs must be sequential (c1, c2, c3, ...)
- Each chunk_content should be 100-300 words
- Focus on visual details, not conceptual explanations
- Include specific colors, shapes, and layout directions
- Mention any text/labels that should appear in the image

Now analyze the input and generate the semantic JSON:"""


@register("p2g_chunk_semantic_constructor_agent")
class P2gChunkSemanticConstructorAgent(BaseAgent):
    """Chunk-Based Pipeline 的语义构建 Agent

    从用户描述中构建语义结构，只包含 chunks 列表。
    每个 chunk 只有 chunk_id 和 chunk_content（详细的绘制描述）。
    """

    def __init__(self, tool_manager: Optional[ToolManager] = None, **kwargs):
        super().__init__(tool_manager=tool_manager, **kwargs)

    @classmethod
    def create(cls, tool_manager: Optional[ToolManager] = None, **kwargs):
        return cls(tool_manager=tool_manager, **kwargs)

    @property
    def role_name(self) -> str:
        return "p2g_chunk_semantic_constructor_agent"

    @property
    def system_prompt_template_name(self) -> str:
        return ""

    @property
    def task_prompt_template_name(self) -> str:
        return ""

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def get_task_prompt(self, pre_tool_results: Dict[str, Any]) -> str:
        """构建任务 prompt"""
        state: ChunkP2GState = pre_tool_results.get("state")

        target = ""
        max_chunks = 6

        if state and hasattr(state, "request"):
            target = getattr(state.request, "target", "")
            max_chunks = getattr(state.request, "max_chunks", 6)

        min_chunks = max(2, max_chunks - 2)

        return TASK_PROMPT_TEMPLATE.format(
            target=target,
            min_chunks=min_chunks,
            max_chunks=max_chunks,
        )

    def build_messages(self, state: MainState, pre_tool_results: Dict[str, Any]):
        """自定义消息构建"""
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
        # 不使用模板，返回空
        return {}

    def update_state_result(
        self,
        state: MainState,
        result: Dict[str, Any],
        pre_tool_results: Dict[str, Any],
    ):
        """更新 state.semantic_json"""
        if isinstance(result, dict):
            # 验证必要字段：只需要 chunks
            if "chunks" in result:
                setattr(state, "semantic_json", result)

                chunks = result.get("chunks", [])

                log.info(
                    "[ChunkSemanticConstructor] semantic_json updated: %d chunks",
                    len(chunks),
                )

                state.agent_results[self.role_name] = {
                    "status": "ok",
                    "stats": {
                        "chunks": len(chunks),
                    }
                }
            else:
                log.warning("[ChunkSemanticConstructor] Invalid result: missing chunks")
                state.agent_results[self.role_name] = {
                    "status": "failed",
                    "error": "Invalid result: missing chunks",
                }
        else:
            log.warning("[ChunkSemanticConstructor] Result is not a dict: %s", type(result))
            state.agent_results[self.role_name] = {
                "status": "failed",
                "error": f"Result is not a dict: {type(result)}",
            }


async def p2g_chunk_semantic_constructor_agent(
    state: ChunkP2GState,
    model_name: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 8192,
    **kwargs,
) -> ChunkP2GState:
    """Chunk-Based 语义构建 Agent 入口函数

    Args:
        state: ChunkP2GState 状态对象
        model_name: LLM 模型名称，默认使用 state.request.model
        temperature: 采样温度
        max_tokens: 最大 token 数

    Returns:
        更新后的 ChunkP2GState
    """
    if model_name is None:
        model_name = getattr(state.request, "model", "gpt-4o")

    target = getattr(state.request, "target", "")
    if not target:
        log.warning("[ChunkSemanticConstructor] target is empty")
        setattr(state, "semantic_json", {
            "chunks": [],
        })
        return state

    log.info("[ChunkSemanticConstructor] Starting with target: %s...", target[:100])

    # 创建 agent 实例
    agent = P2gChunkSemanticConstructorAgent.create(
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
