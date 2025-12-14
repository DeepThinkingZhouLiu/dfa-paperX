"""p2g_chunk_prompt_agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Chunk 级别的 VLM Prompt 生成器。

将每个 chunk 内的所有 node 描述合并，生成一个完整的 chunk 级别绘图 prompt，
让 VLM 一次性绘制整个 chunk 区域。

输入：
- state.semantic_json: 包含 chunks 和 nodes 的语义信息
- state.node_render_design: 包含每个 node 的渲染设计（vlm_prompt/pptx_desc）
- state.layout_json: 包含 chunk 的 bbox 信息

输出：
- state.chunk_prompts: {chunk_id: {prompt, bbox, nodes}} 字典
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from dataflow_agent.state import MainState, Paper2GraphState
from dataflow_agent.toolkits.tool_manager import ToolManager
from dataflow_agent.logger import get_logger
from dataflow_agent.agentroles.base_agent import BaseAgent
from dataflow_agent.agentroles.registry import register

log = get_logger(__name__)


# Chunk prompt 模板
CHUNK_PROMPT_TEMPLATE = """Create a single cohesive scientific diagram illustration for a chunk of a paper figure.

## Chunk Information
- Title: {title}
- Summary: {summary}
- Canvas Size: {width}px × {height}px (aspect ratio must be preserved)

## Style Guidelines
{style_hints}

## Global Style
{global_style}

## Elements to Include
This chunk contains the following elements that should be arranged naturally within the canvas:

{elements_description}

## Important Instructions
1. Create a SINGLE cohesive image containing ALL the elements described above
2. Arrange elements logically based on their relationships and the chunk's purpose
3. Use consistent visual style throughout (colors, fonts, shapes)
4. Maintain the specified aspect ratio ({width}:{height})
5. Use flat 2D vector style, clean lines, no photorealism
6. Background should be white or very light gray
7. Text should be dark gray for readability
8. This is for a top-tier CS conference paper - keep it professional and clean
"""

ELEMENT_TEMPLATE = """
### Element: {node_id} ({node_type})
Description: {description}
"""


def _build_chunk_prompt(
    chunk_info: Dict[str, Any],
    nodes_info: List[Dict[str, Any]],
    chunk_bbox: Dict[str, int],
    global_style: Dict[str, Any],
) -> str:
    """构建单个 chunk 的 VLM prompt

    Args:
        chunk_info: chunk 的语义信息（title, summary 等）
        nodes_info: chunk 内所有 node 的渲染信息
        chunk_bbox: chunk 的 bbox {x, y, w, h}
        global_style: 全局样式指南

    Returns:
        完整的 VLM prompt
    """
    # 构建元素描述
    elements_parts = []
    for node in nodes_info:
        node_id = node.get("node_id", "unknown")
        node_type = node.get("node_type", "shape")

        # 优先使用 vlm_prompt，其次使用 pptx_desc，最后使用 desc
        description = (
            node.get("vlm_prompt") or
            node.get("pptx_desc") or
            node.get("desc", "No description")
        )

        elements_parts.append(ELEMENT_TEMPLATE.format(
            node_id=node_id,
            node_type=node_type,
            description=description,
        ))

    elements_description = "\n".join(elements_parts)

    # 构建样式提示
    style_hints = chunk_info.get("chunk_style_hints", {})
    if isinstance(style_hints, dict):
        style_hints_str = "\n".join([
            f"- {k}: {v}" for k, v in style_hints.items()
        ])
    else:
        style_hints_str = str(style_hints)

    # 构建全局样式
    if isinstance(global_style, dict):
        global_style_str = json.dumps(global_style, indent=2, ensure_ascii=False)
    else:
        global_style_str = str(global_style)

    # 填充模板
    prompt = CHUNK_PROMPT_TEMPLATE.format(
        title=chunk_info.get("title", "Untitled Chunk"),
        summary=chunk_info.get("summary", ""),
        width=chunk_bbox.get("w", 400),
        height=chunk_bbox.get("h", 300),
        style_hints=style_hints_str or "Use professional scientific illustration style",
        global_style=global_style_str,
        elements_description=elements_description,
    )

    return prompt


def _extract_chunk_data(
    semantic_json: Dict[str, Any],
    node_render_design: Dict[str, Any],
    layout_json: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """提取所有 chunk 的数据

    Returns:
        chunk 数据列表，每个元素包含:
        - chunk_id
        - chunk_info: 语义信息
        - nodes_info: 节点渲染信息列表
        - bbox: chunk 的 bbox
    """
    chunks_data = []

    # 从 semantic_json 获取 chunk 语义信息
    semantic_chunks = {
        c["chunk_id"]: c
        for c in semantic_json.get("chunks", [])
    }

    # 从 node_render_design 获取节点渲染信息
    render_nodes = {}
    render_chunks_style = {}
    for chunk in node_render_design.get("chunks", []):
        chunk_id = chunk.get("chunk_id")
        render_chunks_style[chunk_id] = chunk.get("chunk_style_hints", {})
        for node in chunk.get("nodes", []):
            render_nodes[node.get("node_id")] = node

    # 从 semantic_json 获取节点基本信息
    semantic_nodes = {
        n["node_id"]: n
        for n in semantic_json.get("nodes", [])
    }

    # 从 layout_json 获取 chunk bbox
    chunk_bboxes = {
        c["chunk_id"]: c["bbox"]
        for c in layout_json.get("positions", {}).get("chunks", [])
    }

    # 全局样式
    global_style = node_render_design.get("global_style", {})

    # 组装每个 chunk 的数据
    for chunk_id, chunk_info in semantic_chunks.items():
        bbox = chunk_bboxes.get(chunk_id, {"x": 0, "y": 0, "w": 400, "h": 300})

        # 合并 chunk 样式信息
        chunk_info_merged = dict(chunk_info)
        chunk_info_merged["chunk_style_hints"] = render_chunks_style.get(chunk_id, {})

        # 获取 chunk 内的所有节点信息
        node_ids = chunk_info.get("node_ids", [])
        nodes_info = []

        for node_id in node_ids:
            # 合并语义信息和渲染信息
            node_data = {}

            # 基本语义信息
            if node_id in semantic_nodes:
                node_data.update(semantic_nodes[node_id])

            # 渲染信息（覆盖）
            if node_id in render_nodes:
                node_data.update(render_nodes[node_id])

            if node_data:
                nodes_info.append(node_data)

        chunks_data.append({
            "chunk_id": chunk_id,
            "chunk_info": chunk_info_merged,
            "nodes_info": nodes_info,
            "bbox": bbox,
            "global_style": global_style,
        })

    return chunks_data


@register("p2g_chunk_prompt_agent")
class P2gChunkPromptAgent(BaseAgent):
    """Chunk 级别 Prompt 生成器 Agent

    将每个 chunk 内的所有 node 描述合并，生成完整的 chunk 级别绘图 prompt。
    """

    def __init__(self, tool_manager: Optional[ToolManager] = None, **kwargs):
        super().__init__(tool_manager=tool_manager, **kwargs)

    @classmethod
    def create(cls, tool_manager: Optional[ToolManager] = None, **kwargs):
        return cls(tool_manager=tool_manager, **kwargs)

    @property
    def role_name(self) -> str:
        return "p2g_chunk_prompt_agent"

    @property
    def system_prompt_template_name(self) -> str:
        return ""  # 不使用 LLM

    @property
    def task_prompt_template_name(self) -> str:
        return ""  # 不使用 LLM

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
        """更新 state.chunk_prompts"""
        if isinstance(result, dict):
            setattr(state, "chunk_prompts", result.get("chunk_prompts", {}))
        state.agent_results[self.role_name] = result


async def p2g_chunk_prompt_agent(
    state: Paper2GraphState,
) -> Paper2GraphState:
    """Chunk Prompt 生成器入口函数

    从 state 中提取语义信息、渲染设计和布局信息，
    为每个 chunk 生成完整的 VLM 绘图 prompt。

    Args:
        state: Paper2GraphState 状态对象

    Returns:
        更新后的 Paper2GraphState，包含 chunk_prompts
    """
    # 获取输入数据
    semantic_json = getattr(state, "semantic_json", {}) or {}
    node_render_design = getattr(state, "node_render_design", {}) or {}
    layout_json = getattr(state, "layout_json", {}) or {}

    if not semantic_json:
        log.warning("semantic_json is empty, cannot generate chunk prompts")
        setattr(state, "chunk_prompts", {})
        return state

    if not node_render_design:
        log.warning("node_render_design is empty, using semantic_json only")

    if not layout_json:
        log.warning("layout_json is empty, using default bbox")

    # 提取 chunk 数据
    chunks_data = _extract_chunk_data(semantic_json, node_render_design, layout_json)

    log.info(f"[Chunk Prompt] Found {len(chunks_data)} chunks to process")

    # 为每个 chunk 生成 prompt
    chunk_prompts = {}

    for chunk_data in chunks_data:
        chunk_id = chunk_data["chunk_id"]

        prompt = _build_chunk_prompt(
            chunk_info=chunk_data["chunk_info"],
            nodes_info=chunk_data["nodes_info"],
            chunk_bbox=chunk_data["bbox"],
            global_style=chunk_data["global_style"],
        )

        chunk_prompts[chunk_id] = {
            "prompt": prompt,
            "bbox": chunk_data["bbox"],
            "node_ids": [n.get("node_id") for n in chunk_data["nodes_info"]],
            "title": chunk_data["chunk_info"].get("title", ""),
        }

        log.info(f"[Chunk Prompt] Generated prompt for {chunk_id}: {len(prompt)} chars, {len(chunk_data['nodes_info'])} nodes")

    # 更新 state
    setattr(state, "chunk_prompts", chunk_prompts)

    # 记录到 agent_results
    state.agent_results["p2g_chunk_prompt_agent"] = {
        "chunk_prompts": chunk_prompts,
        "stats": {
            "total_chunks": len(chunk_prompts),
            "total_nodes": sum(len(cp["node_ids"]) for cp in chunk_prompts.values()),
        }
    }

    log.info(f"[Chunk Prompt] Completed: {len(chunk_prompts)} chunk prompts generated")

    return state
