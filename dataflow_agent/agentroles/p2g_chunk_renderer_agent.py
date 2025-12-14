"""p2g_chunk_renderer_agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Chunk-Based Pipeline 的渲染 Agent

并行调用 VLM 渲染各 chunk 图片。

输入：
- state.chunk_vlm_designs: VLM prompt 设计

输出：
- state.chunk_images: 渲染结果
- state.chunk_render_errors: 渲染错误
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dataflow_agent.state import MainState, ChunkP2GState
from dataflow_agent.toolkits.tool_manager import ToolManager
from dataflow_agent.logger import get_logger
from dataflow_agent.agentroles.base_agent import BaseAgent
from dataflow_agent.agentroles.registry import register

log = get_logger(__name__)

# 默认 VLM 模型
DEFAULT_VLM_MODEL = "gemini-2.0-flash-preview-image-generation"


async def _generate_chunk_image(
    chunk_id: str,
    prompt: str,
    output_path: str,
    api_url: str,
    api_key: str,
    model: str,
    timeout: int = 1800,
) -> Tuple[str, str, Optional[str], int]:
    """生成单个 chunk 的图片

    Args:
        chunk_id: chunk ID
        prompt: VLM prompt
        output_path: 输出路径
        api_url: API URL
        api_key: API Key
        model: VLM 模型名称
        timeout: 超时时间（秒）

    Returns:
        (chunk_id, image_path, error_message, render_time_ms)
    """
    start_time = time.time()

    try:
        from dataflow_agent.toolkits.imtool.req_img import generate_or_edit_and_save_image_async

        # 确保输出目录存在
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        await generate_or_edit_and_save_image_async(
            prompt=prompt,
            save_path=output_path,
            api_url=api_url,
            api_key=api_key,
            model=model,
            use_edit=False,
            timeout=timeout,
        )

        render_time_ms = int((time.time() - start_time) * 1000)
        log.info("[ChunkRenderer] Generated %s: %s (%d ms)", chunk_id, output_path, render_time_ms)

        return (chunk_id, output_path, None, render_time_ms)

    except Exception as e:
        render_time_ms = int((time.time() - start_time) * 1000)
        # 确保超时异常有清晰的错误信息
        error_msg = str(e) if str(e) else f"{type(e).__name__}: {repr(e)}"
        if "timeout" in type(e).__name__.lower() or "Timeout" in repr(e):
            error_msg = f"请求超时 (>{timeout}s): {type(e).__name__}"
        log.error("[ChunkRenderer] Failed to generate %s: %s", chunk_id, error_msg)
        return (chunk_id, "", error_msg, render_time_ms)


async def _render_chunks_parallel(
    chunk_vlm_designs: Dict[str, Any],
    output_dir: str,
    api_url: str,
    api_key: str,
    model: str,
    concurrency: int = 3,
    timeout: int = 600,  # 默认 10 分钟，图像生成需要较长时间
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """并行渲染所有 chunks

    Args:
        chunk_vlm_designs: chunk VLM 设计
        output_dir: 输出目录
        api_url: API URL
        api_key: API Key
        model: VLM 模型名称
        concurrency: 并发数
        timeout: 超时时间（秒）

    Returns:
        (chunk_images, chunk_render_errors)
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def render_with_semaphore(chunk_id: str, design: Dict[str, Any]):
        async with semaphore:
            prompt = design.get("prompt", "")
            output_path = os.path.join(output_dir, f"{chunk_id}.png")

            return await _generate_chunk_image(
                chunk_id=chunk_id,
                prompt=prompt,
                output_path=output_path,
                api_url=api_url,
                api_key=api_key,
                model=model,
                timeout=timeout,
            )

    # 创建所有任务
    tasks = [
        render_with_semaphore(chunk_id, design)
        for chunk_id, design in chunk_vlm_designs.items()
    ]

    # 并行执行
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 汇总结果
    chunk_images = {}
    chunk_render_errors = {}

    for i, result in enumerate(results):
        chunk_id = list(chunk_vlm_designs.keys())[i]

        if isinstance(result, Exception):
            chunk_render_errors[chunk_id] = str(result)
            log.error("[ChunkRenderer] Task exception for %s: %s", chunk_id, result)
        else:
            cid, image_path, error, render_time_ms = result
            if error:
                chunk_render_errors[cid] = error
            elif image_path:
                chunk_images[cid] = {
                    "path": image_path,
                    "render_status": "success",
                    "render_time_ms": render_time_ms,
                }

    return chunk_images, chunk_render_errors


@register("p2g_chunk_renderer_agent")
class P2gChunkRendererAgent(BaseAgent):
    """Chunk-Based Pipeline 的渲染 Agent

    并行调用 VLM 渲染各 chunk 图片。
    """

    def __init__(self, tool_manager: Optional[ToolManager] = None, **kwargs):
        super().__init__(tool_manager=tool_manager, **kwargs)

    @classmethod
    def create(cls, tool_manager: Optional[ToolManager] = None, **kwargs):
        return cls(tool_manager=tool_manager, **kwargs)

    @property
    def role_name(self) -> str:
        return "p2g_chunk_renderer_agent"

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


async def p2g_chunk_renderer_agent(
    state: ChunkP2GState,
    output_dir: Optional[str] = None,
    concurrency: Optional[int] = None,
    vlm_model: Optional[str] = None,
    timeout: Optional[int] = None,
    **kwargs,
) -> ChunkP2GState:
    """Chunk-Based 渲染 Agent 入口函数

    Args:
        state: ChunkP2GState 状态对象
        output_dir: 输出目录，默认使用 state.request.output_dir
        concurrency: 并发数，默认使用 state.request.vlm_concurrency
        vlm_model: VLM 模型名称，默认使用 state.request.vlm_model
        timeout: 超时时间（秒），默认使用 state.request.vlm_timeout

    Returns:
        更新后的 ChunkP2GState
    """
    # 从环境变量读取 API 配置
    # VLM 生图优先使用 VLM_API_URL 和 VLM_API_KEY，如果没有设置则回退到 DF_API_URL 和 DF_API_KEY
    api_url = os.getenv("VLM_API_URL") or os.getenv("DF_API_URL")
    api_key = os.getenv("VLM_API_KEY") or os.getenv("DF_API_KEY")

    if not api_url or not api_key:
        raise ValueError("请先设置环境变量 VLM_API_URL/VLM_API_KEY 或 DF_API_URL/DF_API_KEY")

    # 打印使用的 API 配置来源
    vlm_url_source = "VLM_API_URL" if os.getenv("VLM_API_URL") else "DF_API_URL"
    vlm_key_source = "VLM_API_KEY" if os.getenv("VLM_API_KEY") else "DF_API_KEY"
    log.info("[ChunkRenderer] Using API config: url from %s, key from %s", vlm_url_source, vlm_key_source)

    # 获取配置
    request = state.request
    if output_dir is None:
        output_dir = os.path.join(getattr(request, "output_dir", ".tmp/chunk_pipeline_output"), "chunks")
    if concurrency is None:
        concurrency = getattr(request, "vlm_concurrency", 3)
    if vlm_model is None:
        vlm_model = os.getenv("DF_VLM_MODEL", getattr(request, "vlm_model", DEFAULT_VLM_MODEL))
    if timeout is None:
        timeout = getattr(request, "vlm_timeout", 1800)

    # 获取 chunk VLM 设计
    chunk_vlm_designs = getattr(state, "chunk_vlm_designs", {})

    if not chunk_vlm_designs:
        log.warning("[ChunkRenderer] chunk_vlm_designs is empty")
        setattr(state, "chunk_images", {})
        setattr(state, "chunk_render_errors", {})
        return state

    log.info(
        "[ChunkRenderer] Starting render: %d chunks, concurrency=%d, model=%s",
        len(chunk_vlm_designs), concurrency, vlm_model,
    )

    # 确保输出目录存在
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # 并行渲染
    start_time = time.time()
    chunk_images, chunk_render_errors = await _render_chunks_parallel(
        chunk_vlm_designs=chunk_vlm_designs,
        output_dir=output_dir,
        api_url=api_url,
        api_key=api_key,
        model=vlm_model,
        concurrency=concurrency,
        timeout=timeout,
    )
    total_time_ms = int((time.time() - start_time) * 1000)

    # 更新 state
    setattr(state, "chunk_images", chunk_images)
    setattr(state, "chunk_render_errors", chunk_render_errors)

    # 统计
    success_count = len(chunk_images)
    error_count = len(chunk_render_errors)
    total_count = len(chunk_vlm_designs)

    state.agent_results["p2g_chunk_renderer_agent"] = {
        "status": "ok" if error_count == 0 else "partial",
        "stats": {
            "total": total_count,
            "success": success_count,
            "failed": error_count,
            "total_time_ms": total_time_ms,
        },
        "errors": chunk_render_errors if chunk_render_errors else None,
    }

    log.info(
        "[ChunkRenderer] Completed: %d/%d succeeded, %d failed, total time: %d ms",
        success_count, total_count, error_count, total_time_ms,
    )

    return state
