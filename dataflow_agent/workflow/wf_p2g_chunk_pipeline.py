"""wf_p2g_chunk_pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Chunk-Based Paper2Graph Pipeline Workflow

Pipeline 流程:
1. semantic_constructor -> semantic_json {title, chunks: [{chunk_id, chunk_content}]}
2. chunk_layout_planner -> chunk_layout_json {canvas, chunks: [{chunk_id, bbox}]}
3. chunk_vlm_designer -> chunk_vlm_designs {chunk_id: {prompt, ratio}}
4. chunk_renderer -> chunk_images {chunk_id: {path, render_status, render_time_ms}}
5. chunk_pptx_composer -> pptx_output_path
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from dataflow_agent.state import ChunkP2GState, ChunkP2GRequest
from dataflow_agent.logger import get_logger

log = get_logger(__name__)


async def run_chunk_p2g_pipeline(
    target: str,
    model_name: str = "gpt-4o",
    canvas_width: int = 1920,
    canvas_height: int = 1080,
    output_dir: str = ".tmp/chunk_pipeline_output",
    vlm_model: Optional[str] = None,
    vlm_concurrency: int = 4,
    vlm_timeout: int = 180,
    max_chunks: int = 6,
    skip_render: bool = False,
    skip_pptx: bool = False,
) -> ChunkP2GState:
    """运行 Chunk-Based Paper2Graph Pipeline

    Args:
        target: 用户的论文方法描述
        model_name: LLM 模型名称
        canvas_width: 画布宽度
        canvas_height: 画布高度
        output_dir: 输出目录
        vlm_model: VLM 模型名称
        vlm_concurrency: VLM 并发数
        vlm_timeout: VLM 超时时间
        max_chunks: 最大 chunk 数量
        skip_render: 是否跳过渲染步骤（用于调试）
        skip_pptx: 是否跳过 PPTX 生成步骤（用于调试）

    Returns:
        ChunkP2GState 状态对象
    """
    # 导入 agents
    from dataflow_agent.agentroles.p2g_chunk_semantic_constructor_agent import (
        p2g_chunk_semantic_constructor_agent,
    )
    from dataflow_agent.agentroles.p2g_chunk_layout_planner_agent import (
        p2g_chunk_layout_planner_agent,
    )
    from dataflow_agent.agentroles.p2g_chunk_vlm_designer_agent import (
        p2g_chunk_vlm_designer_agent,
    )
    from dataflow_agent.agentroles.p2g_chunk_renderer_agent import (
        p2g_chunk_renderer_agent,
    )
    from dataflow_agent.agentroles.p2g_chunk_pptx_composer_agent import (
        p2g_chunk_pptx_composer_for_chunk_pipeline,
    )

    # 创建 request 和 state
    request = ChunkP2GRequest(
        target=target,
        model=model_name,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        output_dir=output_dir,
        vlm_model=vlm_model or "gemini-3-pro-image-preview",
        vlm_concurrency=vlm_concurrency,
        vlm_timeout=vlm_timeout,
        max_chunks=max_chunks,
    )

    state = ChunkP2GState(request=request)

    log.info("=" * 60)
    log.info("Starting Chunk-Based P2G Pipeline")
    log.info("=" * 60)
    log.info(f"Target: {target[:100]}...")
    log.info(f"Model: {model_name}")
    log.info(f"Canvas: {canvas_width}x{canvas_height}")
    log.info(f"Output: {output_dir}")

    # Step 1: Semantic Constructor
    log.info("\n[Step 1/5] Running semantic_constructor...")
    state = await p2g_chunk_semantic_constructor_agent(
        state,
        model_name=model_name,
    )

    semantic_json = getattr(state, "semantic_json", {})
    chunks_count = len(semantic_json.get("chunks", []))
    log.info(f"  -> Generated: {chunks_count} chunks")

    if not chunks_count:
        log.error("  -> Failed: No chunks generated")
        return state

    # Step 2: Chunk Layout Planner
    log.info("\n[Step 2/5] Running chunk_layout_planner...")
    state = await p2g_chunk_layout_planner_agent(
        state,
        model_name=model_name,
    )

    chunk_layout_json = getattr(state, "chunk_layout_json", {})
    layout_chunks = len(chunk_layout_json.get("chunks", []))
    log.info(f"  -> Generated: {layout_chunks} chunk layouts")

    # Step 3: Chunk VLM Designer
    log.info("\n[Step 3/5] Running chunk_vlm_designer...")
    state = await p2g_chunk_vlm_designer_agent(state)

    chunk_vlm_designs = getattr(state, "chunk_vlm_designs", {})
    log.info(f"  -> Generated: {len(chunk_vlm_designs)} VLM prompts")

    if skip_render:
        log.info("\n[Step 4/5] Skipping chunk_renderer (skip_render=True)")
        log.info("[Step 5/5] Skipping pptx_composer (skip_render=True)")
        return state

    # Step 4: Chunk Renderer
    log.info("\n[Step 4/5] Running chunk_renderer...")
    state = await p2g_chunk_renderer_agent(
        state,
        output_dir=f"{output_dir}/chunks",
        concurrency=vlm_concurrency,
        vlm_model=vlm_model,
        timeout=vlm_timeout,
    )

    chunk_images = getattr(state, "chunk_images", {})
    chunk_errors = getattr(state, "chunk_render_errors", {})
    log.info(f"  -> Rendered: {len(chunk_images)} chunks, {len(chunk_errors)} errors")

    if skip_pptx:
        log.info("\n[Step 5/5] Skipping pptx_composer (skip_pptx=True)")
        return state

    # Step 5: PPTX Composer
    log.info("\n[Step 5/5] Running pptx_composer...")
    state = await p2g_chunk_pptx_composer_for_chunk_pipeline(
        state,
        output_path=f"{output_dir}/paper2graph_chunk.pptx",
    )

    pptx_path = getattr(state, "pptx_output_path", "")
    log.info(f"  -> Generated: {pptx_path}")

    log.info("\n" + "=" * 60)
    log.info("Pipeline Completed!")
    log.info("=" * 60)

    return state


# 便捷函数
async def quick_run(target: str, **kwargs) -> ChunkP2GState:
    """快速运行 pipeline 的便捷函数"""
    return await run_chunk_p2g_pipeline(target, **kwargs)
