"""p2g_chunk_vlm_renderer_agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Chunk 级别的 VLM 渲染器。

根据 chunk_prompts 调用 VLM 为每个 chunk 生成图片（不做抠图）。

输入：
- state.chunk_prompts: {chunk_id: {prompt, bbox, node_ids}} 字典

输出：
- state.chunk_images: {chunk_id: {path, bbox}} 字典
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dataflow_agent.state import MainState, Paper2GraphState
from dataflow_agent.toolkits.tool_manager import ToolManager
from dataflow_agent.logger import get_logger
from dataflow_agent.agentroles.base_agent import BaseAgent
from dataflow_agent.agentroles.registry import register

log = get_logger(__name__)

# 默认输出目录
DEFAULT_OUTPUT_DIR = ".tmp/chunk_images"

# 默认并发数
DEFAULT_CONCURRENCY = 3

# 默认 VLM 模型
DEFAULT_VLM_MODEL = "gemini-3-pro-image-preview"

# DEFAULT_VLM_MODEL = "dalle3"

async def _generate_chunk_image(
    prompt: str,
    save_path: str,
    api_url: str,
    api_key: str,
    model: str,
    timeout: int = 180,
) -> str:
    """调用 VLM 生成 chunk 图片

    Returns:
        保存的图片路径
    """
    from dataflow_agent.toolkits.imtool.req_img import generate_or_edit_and_save_image_async

    await generate_or_edit_and_save_image_async(
        prompt=prompt,
        save_path=save_path,
        api_url=api_url,
        api_key=api_key,
        model=model,
        use_edit=False,
        timeout=timeout,
    )

    return save_path


async def _render_single_chunk(
    chunk_id: str,
    prompt: str,
    bbox: Dict[str, int],
    output_dir: str,
    api_url: str,
    api_key: str,
    model: str,
    semaphore: asyncio.Semaphore,
    timeout: int = 180,
) -> Tuple[str, Dict[str, Any], Optional[str]]:
    """渲染单个 chunk

    Args:
        chunk_id: chunk ID
        prompt: VLM 生图提示词
        bbox: chunk 的 bbox {x, y, w, h}
        output_dir: 输出目录
        api_url: API URL
        api_key: API Key
        model: VLM 模型名称
        semaphore: 并发控制信号量
        timeout: 请求超时时间

    Returns:
        (chunk_id, {path, bbox}, error_message)
    """
    async with semaphore:
        try:
            log.info(f"[Chunk VLM Renderer] Starting render for chunk {chunk_id}")

            # 确保输出目录存在
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            # VLM 生图
            image_path = os.path.join(output_dir, f"{chunk_id}.png")
            await _generate_chunk_image(
                prompt=prompt,
                save_path=image_path,
                api_url=api_url,
                api_key=api_key,
                model=model,
                timeout=timeout,
            )

            log.info(f"[Chunk VLM Renderer] Generated image for {chunk_id}: {image_path}")

            return (chunk_id, {"path": image_path, "bbox": bbox}, None)

        except Exception as e:
            log.error(f"[Chunk VLM Renderer] Failed to render chunk {chunk_id}: {e}")
            return (chunk_id, {}, str(e))


@register("p2g_chunk_vlm_renderer_agent")
class P2gChunkVlmRendererAgent(BaseAgent):
    """Chunk 级别 VLM 渲染器 Agent

    根据 chunk_prompts 调用 VLM 为每个 chunk 生成图片。
    """

    def __init__(self, tool_manager: Optional[ToolManager] = None, **kwargs):
        super().__init__(tool_manager=tool_manager, **kwargs)
        self._output_dir = kwargs.get("output_dir", DEFAULT_OUTPUT_DIR)
        self._concurrency = kwargs.get("concurrency", DEFAULT_CONCURRENCY)
        self._vlm_model = kwargs.get("vlm_model", DEFAULT_VLM_MODEL)
        self._timeout = kwargs.get("timeout", 180)

    @classmethod
    def create(cls, tool_manager: Optional[ToolManager] = None, **kwargs):
        return cls(tool_manager=tool_manager, **kwargs)

    @property
    def role_name(self) -> str:
        return "p2g_chunk_vlm_renderer_agent"

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
        """更新 state.chunk_images"""
        if isinstance(result, dict):
            setattr(state, "chunk_images", result.get("chunk_images", {}))
        state.agent_results[self.role_name] = result


async def p2g_chunk_vlm_renderer_agent(
    state: Paper2GraphState,
    output_dir: Optional[str] = None,
    concurrency: int = DEFAULT_CONCURRENCY,
    vlm_model: Optional[str] = None,
    timeout: int = 180,
) -> Paper2GraphState:
    """Chunk VLM 渲染器入口函数

    从 state.chunk_prompts 中获取每个 chunk 的 prompt，
    并行调用 VLM 生成图片，结果保存到 state.chunk_images。

    Args:
        state: Paper2GraphState 状态对象
        output_dir: 输出目录，默认 .tmp/chunk_images
        concurrency: 并发数，默认 3
        vlm_model: VLM 模型名称
        timeout: 请求超时时间（秒），默认 180

    Returns:
        更新后的 Paper2GraphState
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
    log.info(f"[Chunk VLM Renderer] Using API config: url from {vlm_url_source}, key from {vlm_key_source}")

    # 设置输出目录
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR

    # 设置 VLM 模型
    if vlm_model is None:
        vlm_model = os.getenv("DF_VLM_MODEL", DEFAULT_VLM_MODEL)

    # 获取 chunk_prompts
    chunk_prompts = getattr(state, "chunk_prompts", {}) or {}

    if not chunk_prompts:
        log.warning("chunk_prompts is empty, skip VLM rendering")
        setattr(state, "chunk_images", {})
        return state

    log.info(f"[Chunk VLM Renderer] Found {len(chunk_prompts)} chunks to render")
    log.info(f"[Chunk VLM Renderer] Output directory: {output_dir}")
    log.info(f"[Chunk VLM Renderer] Concurrency: {concurrency}")
    log.info(f"[Chunk VLM Renderer] VLM model: {vlm_model}")

    # 创建并发控制信号量
    semaphore = asyncio.Semaphore(concurrency)

    # 并行渲染所有 chunk
    tasks = [
        _render_single_chunk(
            chunk_id=chunk_id,
            prompt=chunk_data["prompt"],
            bbox=chunk_data["bbox"],
            output_dir=output_dir,
            api_url=api_url,
            api_key=api_key,
            model=vlm_model,
            semaphore=semaphore,
            timeout=timeout,
        )
        for chunk_id, chunk_data in chunk_prompts.items()
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 汇总结果
    chunk_images: Dict[str, Dict[str, Any]] = {}
    errors: Dict[str, str] = {}

    for result in results:
        if isinstance(result, Exception):
            log.error(f"[Chunk VLM Renderer] Task exception: {result}")
            continue

        chunk_id, image_data, error = result
        if error:
            errors[chunk_id] = error
        elif image_data:
            chunk_images[chunk_id] = image_data

    # 统计结果
    success_count = len(chunk_images)
    error_count = len(errors)
    total_count = len(chunk_prompts)

    log.info(f"[Chunk VLM Renderer] Completed: {success_count}/{total_count} succeeded, {error_count} failed")

    if errors:
        log.warning(f"[Chunk VLM Renderer] Failed chunks: {list(errors.keys())}")

    # 更新 state
    setattr(state, "chunk_images", chunk_images)
    setattr(state, "chunk_render_errors", errors)

    # 记录到 agent_results
    state.agent_results["p2g_chunk_vlm_renderer_agent"] = {
        "chunk_images": chunk_images,
        "errors": errors,
        "stats": {
            "total": total_count,
            "success": success_count,
            "failed": error_count,
        }
    }

    return state
