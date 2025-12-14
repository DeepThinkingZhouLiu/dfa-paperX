"""p2g_vlm_node_renderer_agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

为所有 render_method="vlm" 的节点生成图片，并进行抠图处理。

输入：
- state.node_render_design: 包含所有节点的渲染设计

输出：
- state.vlm_rendered_nodes: {node_id: image_path} 字典
- 图片文件保存在指定目录（默认 .tmp/vlm_nodes/）
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
DEFAULT_OUTPUT_DIR = ".tmp/vlm_nodes"

# 默认并发数
DEFAULT_CONCURRENCY = 5

# 默认 VLM 模型
DEFAULT_VLM_MODEL = "gemini-3-pro-image-preview"

# ============================================================================
# VLM Prompt 组装相关常量和函数
# ============================================================================

# 风格预设映射
STYLE_PRESETS = {
    "flat_2d_vector": "Flat 2D vector style, clean geometric shapes, minimalist design",
    "scientific_diagram": "Clean scientific diagram, minimalist design, publication-ready for top-tier CS conference",
    "icon": "Simple flat icon, single color, clear silhouette, centered composition",
    "module_box": "Rounded rectangle module box with clear label, professional look, suitable for flowchart"
}

# 颜色预设映射
COLOR_PRESETS = {
    "muted_teal": "muted teal color (#66c2a5)",
    "calm_blue": "calm professional blue color (#4A90D9)",
    "warm_accent": "soft warm coral color (#fc8d62)",
    "neutral_gray": "neutral gray color (#808080)",
    "muted_green": "muted green color (#6BAA9B)",
    "light_purple": "light purple color (#9B8EC2)",
    "soft_orange": "soft orange color (#E8A87C)"
}


def _assemble_vlm_prompt(
    vlm_spec: Dict[str, Any],
    vlm_prompt: str,
    aspect_ratio: float,
    bbox_w: int,
    bbox_h: int,
) -> str:
    """组装最终的 VLM prompt

    支持两种格式：
    1. 结构化 vlm_spec（新格式，推荐）
    2. 原始 vlm_prompt（旧格式，兼容）

    Args:
        vlm_spec: 结构化的 vlm 规格（新格式）
        vlm_prompt: 原始 vlm_prompt（旧格式，兼容）
        aspect_ratio: 目标宽高比
        bbox_w: 目标宽度（像素）
        bbox_h: 目标高度（像素）

    Returns:
        组装后的完整 prompt
    """
    # 如果有结构化 vlm_spec，使用新格式
    if vlm_spec and vlm_spec.get("content"):
        content = vlm_spec.get("content", "")
        style_key = vlm_spec.get("style", "flat_2d_vector")
        style = STYLE_PRESETS.get(style_key, STYLE_PRESETS["flat_2d_vector"])

        color_key = vlm_spec.get("color_scheme", "calm_blue")
        color = COLOR_PRESETS.get(color_key, COLOR_PRESETS["calm_blue"])

        background = vlm_spec.get("background", "white")
        label_text = vlm_spec.get("label_text", "")

        prompt_parts = [
            f"[CONTENT]",
            f"{content}",
            f"",
            f"[VISUAL STYLE]",
            f"{style}",
            f"Color: {color}",
        ]

        if label_text:
            prompt_parts.append(f'Text label to include: "{label_text}"')

        prompt_parts.extend([
            f"",
            f"[OUTPUT REQUIREMENTS]",
            f"- {background.capitalize()} background",
            f"- Aspect ratio: approximately {aspect_ratio:.2f}:1",
            f"- Target size: {bbox_w}x{bbox_h} pixels",
            f"- The image should fit naturally into this container without distortion",
            f"",
            f"[NEGATIVE - DO NOT INCLUDE]",
            f"Photorealistic elements, gradients, complex textures, 3D effects, shadows, busy backgrounds, watermarks"
        ])

        return "\n".join(prompt_parts)

    # 兼容旧格式：在原始 prompt 后追加比例约束
    elif vlm_prompt:
        ratio_hint = f"""

[OUTPUT SIZE REQUIREMENT]
- Aspect ratio: approximately {aspect_ratio:.2f}:1 (width:height = {bbox_w}:{bbox_h})
- The image should fit naturally into a {bbox_w}x{bbox_h} pixel container
- Avoid extreme aspect ratios that would cause distortion when scaled
"""
        return vlm_prompt.strip() + ratio_hint

    else:
        return ""


async def _generate_image(
    prompt: str,
    save_path: str,
    api_url: str,
    api_key: str,
    model: str,
    timeout: int = 120,
) -> str:
    """调用 VLM 生成图片
    
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


def _remove_background(
    image_path: str,
    output_dir: str,
    method: str = "edge_floodfill",
    bg_threshold: int = 245,
) -> str:
    """对图片进行抠图处理

    Args:
        image_path: 输入图片路径
        output_dir: 输出目录
        method: 抠图方法，"edge_floodfill"（适合图表/图标）或 "rmbg"（适合人物/产品）
        bg_threshold: 背景色阈值（仅 edge_floodfill 方法使用）

    Returns:
        抠图后的图片路径
    """
    if method == "edge_floodfill":
        from dataflow_agent.toolkits.imtool.bg_tool import EdgeFloodFillRemover
        remover = EdgeFloodFillRemover(
            output_dir=output_dir,
            bg_threshold=bg_threshold,
            edge_smooth=True,
            edge_smooth_radius=2,
        )
    else:
        from dataflow_agent.toolkits.imtool.bg_tool import BriaRMBG2Remover
        remover = BriaRMBG2Remover(output_dir=output_dir)

    return remover.remove_background(image_path)


async def _render_single_node(
    node_id: str,
    vlm_spec: Dict[str, Any],
    vlm_prompt: str,
    aspect_ratio: float,
    bbox_w: int,
    bbox_h: int,
    output_dir: str,
    api_url: str,
    api_key: str,
    model: str,
    semaphore: asyncio.Semaphore,
    timeout: int = 120,
    skip_bg_remove: bool = False,
    bg_remove_method: str = "edge_floodfill",
    bg_threshold: int = 245,
) -> Tuple[str, str, Optional[str]]:
    """渲染单个 VLM 节点

    Args:
        node_id: 节点 ID
        vlm_spec: 结构化的 vlm 规格（新格式）
        vlm_prompt: VLM 生图提示词（旧格式，兼容）
        aspect_ratio: 目标宽高比
        bbox_w: 目标宽度（像素）
        bbox_h: 目标高度（像素）
        output_dir: 输出目录
        api_url: API URL
        api_key: API Key
        model: VLM 模型名称
        semaphore: 并发控制信号量
        timeout: 请求超时时间
        skip_bg_remove: 是否跳过抠图步骤
        bg_remove_method: 抠图方法，"edge_floodfill"（适合图表/图标）或 "rmbg"（适合人物/产品）
        bg_threshold: 背景色阈值（仅 edge_floodfill 方法使用，默认 245）

    Returns:
        (node_id, final_image_path, error_message)
    """
    async with semaphore:
        try:
            log.info(f"[VLM Renderer] Starting render for node {node_id}, aspect_ratio={aspect_ratio:.2f}")

            # 确保输出目录存在
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            # 组装最终 prompt
            final_prompt = _assemble_vlm_prompt(
                vlm_spec=vlm_spec,
                vlm_prompt=vlm_prompt,
                aspect_ratio=aspect_ratio,
                bbox_w=bbox_w,
                bbox_h=bbox_h,
            )

            if not final_prompt:
                return (node_id, "", "Empty prompt after assembly")

            log.debug(f"[VLM Renderer] Final prompt for {node_id}:\n{final_prompt[:300]}...")

            # 1. VLM 生图
            raw_path = os.path.join(output_dir, f"{node_id}_raw.png")
            await _generate_image(
                prompt=final_prompt,
                save_path=raw_path,
                api_url=api_url,
                api_key=api_key,
                model=model,
                timeout=timeout,
            )
            log.info(f"[VLM Renderer] Generated raw image for {node_id}: {raw_path}")

            # 2. 抠图（可选）
            if skip_bg_remove:
                final_path = raw_path
                log.info(f"[VLM Renderer] Skipped background removal for {node_id}")
            else:
                try:
                    final_path = _remove_background(
                        raw_path,
                        output_dir,
                        method=bg_remove_method,
                        bg_threshold=bg_threshold,
                    )
                    log.info(f"[VLM Renderer] Background removed for {node_id} (method={bg_remove_method}): {final_path}")
                except Exception as bg_err:
                    log.warning(f"[VLM Renderer] Background removal failed for {node_id}: {bg_err}, using raw image")
                    final_path = raw_path

            return (node_id, final_path, None)

        except Exception as e:
            log.error(f"[VLM Renderer] Failed to render node {node_id}: {e}")
            return (node_id, "", str(e))


def _extract_vlm_nodes(
    node_render_design: Dict[str, Any],
    layout_json: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """从 node_render_design 中提取所有 vlm 类型的节点

    Args:
        node_render_design: 渲染设计
        layout_json: 布局信息（可选，用于获取 bbox 比例）

    Returns:
        vlm 节点列表，每个元素包含 node_id、vlm_prompt/vlm_spec、aspect_ratio 等
    """
    # 构建 node_id -> bbox 映射
    bbox_map = {}
    if layout_json:
        for node_pos in layout_json.get("positions", {}).get("nodes", []):
            node_id = node_pos.get("node_id")
            bbox = node_pos.get("bbox", {})
            if node_id and bbox:
                w = bbox.get("w", 200)
                h = bbox.get("h", 200)
                aspect_ratio = w / h if h > 0 else 1.0
                bbox_map[node_id] = {
                    "w": int(w),
                    "h": int(h),
                    "aspect_ratio": round(aspect_ratio, 2)
                }

    vlm_nodes = []

    chunks = node_render_design.get("chunks", [])
    for chunk in chunks:
        nodes = chunk.get("nodes", [])
        for node in nodes:
            if node.get("render_method") == "vlm":
                node_id = node.get("node_id", "")

                # 获取 vlm_spec（新格式）或 vlm_prompt（旧格式）
                vlm_spec = node.get("vlm_spec", {})
                vlm_prompt = node.get("vlm_prompt", "")

                if not vlm_prompt and not vlm_spec:
                    log.warning(f"VLM node {node_id} has no vlm_prompt or vlm_spec, skipping")
                    continue

                # 获取 bbox 信息
                bbox_info = bbox_map.get(node_id, {
                    "w": 200,
                    "h": 200,
                    "aspect_ratio": 1.0
                })

                vlm_nodes.append({
                    "node_id": node_id,
                    "vlm_spec": vlm_spec,
                    "vlm_prompt": vlm_prompt,
                    "chunk_id": chunk.get("chunk_id", ""),
                    "aspect_ratio": bbox_info["aspect_ratio"],
                    "bbox_w": bbox_info["w"],
                    "bbox_h": bbox_info["h"],
                })

    return vlm_nodes


@register("p2g_vlm_node_renderer_agent")
class P2gVlmNodeRendererAgent(BaseAgent):
    """VLM 节点渲染器 Agent
    
    为所有 render_method="vlm" 的节点生成图片并抠图。
    """

    def __init__(self, tool_manager: Optional[ToolManager] = None, **kwargs):
        super().__init__(tool_manager=tool_manager, **kwargs)
        self._output_dir = kwargs.get("output_dir", DEFAULT_OUTPUT_DIR)
        self._concurrency = kwargs.get("concurrency", DEFAULT_CONCURRENCY)
        self._vlm_model = kwargs.get("vlm_model", DEFAULT_VLM_MODEL)
        self._skip_bg_remove = kwargs.get("skip_bg_remove", False)
        self._timeout = kwargs.get("timeout", 120)

    @classmethod
    def create(cls, tool_manager: Optional[ToolManager] = None, **kwargs):
        return cls(tool_manager=tool_manager, **kwargs)

    @property
    def role_name(self) -> str:
        return "p2g_vlm_node_renderer_agent"

    @property
    def system_prompt_template_name(self) -> str:
        # 这个 agent 不需要 LLM 调用，直接执行工具
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
        """更新 state.vlm_rendered_nodes"""
        if isinstance(result, dict):
            setattr(state, "vlm_rendered_nodes", result)
        state.agent_results[self.role_name] = result


async def p2g_vlm_node_renderer_agent(
    state: Paper2GraphState,
    output_dir: Optional[str] = None,
    concurrency: int = DEFAULT_CONCURRENCY,
    vlm_model: Optional[str] = None,
    skip_bg_remove: bool = False,
    bg_remove_method: str = "edge_floodfill",
    bg_threshold: int = 245,
    timeout: int = 120,
) -> Paper2GraphState:
    """VLM 节点渲染器入口函数

    从 state.node_render_design 中提取所有 vlm 类型节点，
    并行调用 VLM 生图 + 抠图，结果保存到 state.vlm_rendered_nodes。

    Args:
        state: Paper2GraphState 状态对象
        output_dir: 输出目录，默认 .tmp/vlm_nodes
        concurrency: 并发数，默认 5
        vlm_model: VLM 模型名称，默认 gemini-3-pro-image-preview
        skip_bg_remove: 是否跳过抠图步骤，默认 False
        bg_remove_method: 抠图方法，"edge_floodfill"（适合图表/图标）或 "rmbg"（适合人物/产品）
        bg_threshold: 背景色阈值（仅 edge_floodfill 方法使用，默认 245）
        timeout: 请求超时时间（秒），默认 120

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
    log.info(f"[VLM Renderer] Using API config: url from {vlm_url_source}, key from {vlm_key_source}")

    # 设置输出目录
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR
    
    # 设置 VLM 模型
    if vlm_model is None:
        vlm_model = os.getenv("DF_VLM_MODEL", DEFAULT_VLM_MODEL)
    
    # 获取 node_render_design 和 layout_json
    node_render_design = getattr(state, "node_render_design", {}) or {}
    layout_json = getattr(state, "layout_json", {}) or {}

    if not node_render_design:
        log.warning("node_render_design is empty, skip VLM rendering")
        setattr(state, "vlm_rendered_nodes", {})
        return state

    # 提取 vlm 节点（传入 layout_json 以获取 bbox 比例）
    vlm_nodes = _extract_vlm_nodes(node_render_design, layout_json)

    if not vlm_nodes:
        log.info("No VLM nodes found, skip rendering")
        setattr(state, "vlm_rendered_nodes", {})
        return state

    log.info(f"[VLM Renderer] Found {len(vlm_nodes)} VLM nodes to render")
    log.info(f"[VLM Renderer] Output directory: {output_dir}")
    log.info(f"[VLM Renderer] Concurrency: {concurrency}")
    log.info(f"[VLM Renderer] VLM model: {vlm_model}")
    log.info(f"[VLM Renderer] Skip background removal: {skip_bg_remove}")
    log.info(f"[VLM Renderer] Background removal method: {bg_remove_method}")
    log.info(f"[VLM Renderer] Background threshold: {bg_threshold}")

    # 创建并发控制信号量
    semaphore = asyncio.Semaphore(concurrency)

    # 并行渲染所有节点
    tasks = [
        _render_single_node(
            node_id=node["node_id"],
            vlm_spec=node["vlm_spec"],
            vlm_prompt=node["vlm_prompt"],
            aspect_ratio=node["aspect_ratio"],
            bbox_w=node["bbox_w"],
            bbox_h=node["bbox_h"],
            output_dir=output_dir,
            api_url=api_url,
            api_key=api_key,
            model=vlm_model,
            semaphore=semaphore,
            timeout=timeout,
            skip_bg_remove=skip_bg_remove,
            bg_remove_method=bg_remove_method,
            bg_threshold=bg_threshold,
        )
        for node in vlm_nodes
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 汇总结果
    vlm_rendered_nodes: Dict[str, str] = {}
    errors: Dict[str, str] = {}
    
    for result in results:
        if isinstance(result, Exception):
            log.error(f"[VLM Renderer] Task exception: {result}")
            continue
        
        node_id, image_path, error = result
        if error:
            errors[node_id] = error
        elif image_path:
            vlm_rendered_nodes[node_id] = image_path
    
    # 统计结果
    success_count = len(vlm_rendered_nodes)
    error_count = len(errors)
    total_count = len(vlm_nodes)
    
    log.info(f"[VLM Renderer] Completed: {success_count}/{total_count} succeeded, {error_count} failed")
    
    if errors:
        log.warning(f"[VLM Renderer] Failed nodes: {list(errors.keys())}")
    
    # 更新 state
    setattr(state, "vlm_rendered_nodes", vlm_rendered_nodes)
    setattr(state, "vlm_render_errors", errors)
    
    # 记录到 agent_results
    state.agent_results["p2g_vlm_node_renderer_agent"] = {
        "vlm_rendered_nodes": vlm_rendered_nodes,
        "errors": errors,
        "stats": {
            "total": total_count,
            "success": success_count,
            "failed": error_count,
        }
    }
    
    return state


# CLI 入口
if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="VLM Node Renderer Agent")
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="node_render_design.json 文件路径"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=DEFAULT_OUTPUT_DIR,
        help=f"输出目录，默认 {DEFAULT_OUTPUT_DIR}"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"并发数，默认 {DEFAULT_CONCURRENCY}"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_VLM_MODEL,
        help=f"VLM 模型，默认 {DEFAULT_VLM_MODEL}"
    )
    parser.add_argument(
        "--skip-bg-remove",
        action="store_true",
        help="跳过抠图步骤"
    )
    parser.add_argument(
        "--bg-remove-method",
        type=str,
        default="edge_floodfill",
        choices=["edge_floodfill", "rmbg"],
        help="抠图方法：edge_floodfill（适合图表/图标，默认）或 rmbg（适合人物/产品）"
    )
    parser.add_argument(
        "--bg-threshold",
        type=int,
        default=245,
        help="背景色阈值（仅 edge_floodfill 方法使用，默认 245）"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="请求超时时间（秒），默认 120"
    )

    args = parser.parse_args()
    
    # 读取输入文件
    with open(args.input, "r", encoding="utf-8") as f:
        node_render_design = json.load(f)
    
    # 构建 state
    from dataflow_agent.state import Paper2GraphState, Paper2GraphRequest
    
    state = Paper2GraphState()
    state.request = Paper2GraphRequest()
    state.node_render_design = node_render_design
    
    # 执行
    async def main():
        result_state = await p2g_vlm_node_renderer_agent(
            state,
            output_dir=args.output_dir,
            concurrency=args.concurrency,
            vlm_model=args.model,
            skip_bg_remove=args.skip_bg_remove,
            bg_remove_method=args.bg_remove_method,
            bg_threshold=args.bg_threshold,
            timeout=args.timeout,
        )
        
        # 输出结果
        vlm_rendered_nodes = getattr(result_state, "vlm_rendered_nodes", {})
        errors = getattr(result_state, "vlm_render_errors", {})
        
        print("\n" + "=" * 60)
        print("VLM Node Renderer Results")
        print("=" * 60)
        print(f"Total VLM nodes: {len(vlm_rendered_nodes) + len(errors)}")
        print(f"Successfully rendered: {len(vlm_rendered_nodes)}")
        print(f"Failed: {len(errors)}")
        
        if vlm_rendered_nodes:
            print("\nRendered nodes:")
            for node_id, path in vlm_rendered_nodes.items():
                print(f"  {node_id}: {path}")
        
        if errors:
            print("\nFailed nodes:")
            for node_id, error in errors.items():
                print(f"  {node_id}: {error}")
        
        # 保存结果
        result_path = os.path.join(args.output_dir, "vlm_rendered_nodes.json")
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump({
                "vlm_rendered_nodes": vlm_rendered_nodes,
                "errors": errors,
            }, f, ensure_ascii=False, indent=2)
        print(f"\nResults saved to: {result_path}")
    
    asyncio.run(main())
