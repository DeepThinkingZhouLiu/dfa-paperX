"""p2g_filmstrip_renderer_agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Film-Strip Pipeline Stage 5: Filmstrip Renderer Agent

对每个 VLM group 执行：
1. 调用 VLM 生成连环画图像
2. 切图（检测白色分隔带或等分回退）
3. 去背景（EdgeFloodFill）
4. 裁剪透明边缘获取真实尺寸

输入：
- state.vlm_group_plan_json: 分组计划

输出：
- state.filmstrip_images: {group_id: {path, status, ...}}
- state.vlm_rendered_nodes: {node_id: image_path}
- state.vlm_node_assets: {node_id: {width_px, height_px, source_group_id, panel_index, path}}
- state.filmstrip_render_errors: {group_id: error_message}
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from dataflow_agent.state import FilmStripP2GState
from dataflow_agent.logger import get_logger

log = get_logger(__name__)


class FilmstripSlicer:
    """连环画切图器

    支持两种切图策略：
    1. 白色分隔带检测（优先）
    2. 等分切割（回退）
    """

    def __init__(
        self,
        white_threshold: int = 245,
        min_gap_width: int = 10,
        white_ratio_threshold: float = 0.95,
    ):
        """
        Args:
            white_threshold: 白色像素阈值（RGB 各通道都大于此值视为白色）
                            默认 245，适应 VLM 生成图像中略带灰度的"白色"背景
            min_gap_width: 最小分隔带宽度（像素）
            white_ratio_threshold: 列被视为"白色列"的白色像素比例阈值
        """
        self.white_threshold = white_threshold
        self.min_gap_width = min_gap_width
        self.white_ratio_threshold = white_ratio_threshold

    def slice_filmstrip(
        self,
        image_path: str,
        expected_count: int,
        output_dir: str,
        prefix: str = "panel",
        trim_whitespace: bool = True,
    ) -> List[str]:
        """切分连环画图像

        Args:
            image_path: 连环画图像路径
            expected_count: 期望的 panel 数量
            output_dir: 输出目录
            prefix: 输出文件名前缀
            trim_whitespace: 是否裁剪每个 panel 周围的白色空白

        Returns:
            切分后的 panel 图像路径列表（按顺序）
        """
        img = Image.open(image_path).convert("RGB")
        img_array = np.array(img)
        h, w = img_array.shape[:2]

        # 尝试检测白色分隔带
        boundaries = self._detect_white_gaps(img_array, expected_count)

        if boundaries is None or len(boundaries) != expected_count + 1:
            log.warning(
                f"White gap detection failed (got {len(boundaries) if boundaries else 0} boundaries, "
                f"expected {expected_count + 1}), falling back to equal split"
            )
            boundaries = self._equal_split(w, expected_count)

        # 切分并保存
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        panel_paths = []

        for i in range(expected_count):
            left = boundaries[i]
            right = boundaries[i + 1]

            # 切分
            panel = img.crop((left, 0, right, h))

            # 裁剪白色空白边缘
            if trim_whitespace:
                panel = self._trim_whitespace(panel)

            # 保存
            panel_path = os.path.join(output_dir, f"{prefix}_{i}.png")
            panel.save(panel_path)
            panel_paths.append(panel_path)

            log.debug(f"Saved panel {i}: {panel_path} (size: {panel.width}x{panel.height})")

        return panel_paths

    def _trim_whitespace(self, img: Image.Image, padding: int = 2) -> Image.Image:
        """使用 flood fill 从边缘淹没白色像素，然后裁剪

        从图像四周开始，淹没所有与边缘连通的白色像素区域，
        然后根据剩余内容的边界进行裁剪。

        Args:
            img: PIL Image 对象
            padding: 保留的边缘像素数（避免裁剪过紧）

        Returns:
            裁剪后的图像
        """
        from scipy import ndimage

        img_array = np.array(img)
        h, w = img_array.shape[:2]

        # 1. 创建白色像素 mask
        white_mask = np.all(img_array > self.white_threshold, axis=2)

        # 2. 使用连通区域标记
        labeled, num_features = ndimage.label(white_mask)

        # 3. 找到与边缘连通的白色区域标签
        edge_labels = set()
        edge_labels.update(labeled[0, :].tolist())       # 上边缘
        edge_labels.update(labeled[h - 1, :].tolist())   # 下边缘
        edge_labels.update(labeled[:, 0].tolist())       # 左边缘
        edge_labels.update(labeled[:, w - 1].tolist())   # 右边缘
        edge_labels.discard(0)  # 0 表示非白色区域

        # 4. 创建边缘连通白色区域的 mask
        edge_white_mask = np.isin(labeled, list(edge_labels))

        # 5. 内容区域 = 非边缘连通白色的区域
        content_mask = ~edge_white_mask

        # 6. 找到内容区域的边界
        rows = np.any(content_mask, axis=1)
        cols = np.any(content_mask, axis=0)

        if not np.any(rows) or not np.any(cols):
            # 全是边缘连通的白色，返回原图
            log.warning("Panel content is entirely edge-connected white, returning original")
            return img

        # 获取边界索引
        row_indices = np.where(rows)[0]
        col_indices = np.where(cols)[0]

        top = max(0, row_indices[0] - padding)
        bottom = min(h, row_indices[-1] + 1 + padding)
        left = max(0, col_indices[0] - padding)
        right = min(w, col_indices[-1] + 1 + padding)

        # 裁剪
        cropped = img.crop((left, top, right, bottom))

        log.debug(
            f"Trimmed whitespace (flood fill): {img.width}x{img.height} -> {cropped.width}x{cropped.height} "
            f"(removed: top={top}, bottom={h - bottom}, left={left}, right={w - right})"
        )

        return cropped

    def _detect_white_gaps(
        self,
        img_array: np.ndarray,
        expected_count: int,
    ) -> Optional[List[int]]:
        """检测白色分隔带

        Returns:
            边界列表 [0, gap1_center, gap2_center, ..., width]，或 None 如果检测失败
        """
        h, w = img_array.shape[:2]

        # 计算每列的白色像素比例
        white_mask = np.all(img_array > self.white_threshold, axis=2)
        white_ratio_per_col = white_mask.sum(axis=0) / h

        # 找到"白色列"
        is_white_col = white_ratio_per_col > self.white_ratio_threshold

        # 找到连续的白色区域（分隔带）
        gaps = []
        in_gap = False
        gap_start = 0

        for x in range(w):
            if is_white_col[x] and not in_gap:
                in_gap = True
                gap_start = x
            elif not is_white_col[x] and in_gap:
                in_gap = False
                gap_width = x - gap_start
                if gap_width >= self.min_gap_width:
                    gap_center = gap_start + gap_width // 2
                    gaps.append(gap_center)

        # 处理末尾的 gap
        if in_gap:
            gap_width = w - gap_start
            if gap_width >= self.min_gap_width:
                gap_center = gap_start + gap_width // 2
                gaps.append(gap_center)

        # 检查是否找到了正确数量的分隔带
        expected_gaps = expected_count - 1
        if len(gaps) != expected_gaps:
            log.debug(f"Found {len(gaps)} gaps, expected {expected_gaps}")
            return None

        # 构建边界列表
        boundaries = [0] + gaps + [w]
        return boundaries

    def _equal_split(self, width: int, count: int) -> List[int]:
        """等分切割"""
        panel_width = width // count
        boundaries = [i * panel_width for i in range(count)]
        boundaries.append(width)
        return boundaries


class PanelProcessor:
    """Panel 后处理器

    负责去背景和裁剪透明边缘
    """

    def __init__(
        self,
        bg_threshold: int = 245,
        edge_smooth: bool = True,
        edge_smooth_radius: int = 2,
    ):
        self.bg_threshold = bg_threshold
        self.edge_smooth = edge_smooth
        self.edge_smooth_radius = edge_smooth_radius

    def process_panel(
        self,
        panel_path: str,
        output_path: str,
    ) -> Dict[str, Any]:
        """处理单个 panel：去背景 + 裁剪透明边缘

        Args:
            panel_path: 输入 panel 路径
            output_path: 输出路径

        Returns:
            {path, width_px, height_px, original_width, original_height}
        """
        from dataflow_agent.toolkits.imtool.bg_tool import EdgeFloodFillRemover

        # 去背景
        remover = EdgeFloodFillRemover(
            output_dir=os.path.dirname(output_path),
            bg_threshold=self.bg_threshold,
            edge_smooth=self.edge_smooth,
            edge_smooth_radius=self.edge_smooth_radius,
        )

        bg_removed_path = remover.remove_background(panel_path)

        # 裁剪透明边缘
        img = Image.open(bg_removed_path).convert("RGBA")
        original_w, original_h = img.size

        # 获取 alpha 通道的 bounding box
        alpha = img.split()[3]
        bbox = alpha.getbbox()

        if bbox:
            # 裁剪
            cropped = img.crop(bbox)
            cropped.save(output_path)
            final_w, final_h = cropped.size
        else:
            # 没有内容，保存原图
            img.save(output_path)
            final_w, final_h = original_w, original_h

        # 清理中间文件
        if bg_removed_path != output_path and os.path.exists(bg_removed_path):
            os.remove(bg_removed_path)

        return {
            "path": output_path,
            "width_px": final_w,
            "height_px": final_h,
            "original_width": original_w,
            "original_height": original_h,
        }


async def render_single_group(
    group: Dict[str, Any],
    output_dir: str,
    vlm_model: str,
    vlm_timeout: int,
    api_url: str,
    api_key: str,
) -> Dict[str, Any]:
    """渲染单个 group

    Args:
        group: group 配置 {group_id, node_ids, subject, prompt}
        output_dir: 输出目录
        vlm_model: VLM 模型名称
        vlm_timeout: VLM 超时时间
        api_url: API URL
        api_key: API Key

    Returns:
        {
            group_id: str,
            status: "ok" | "error",
            filmstrip_path: str,
            panels: [{node_id, path, width_px, height_px, panel_index}],
            error: str (if error),
            render_time_ms: int,
        }
    """
    from dataflow_agent.toolkits.imtool.req_img import generate_or_edit_and_save_image_async

    group_id = group["group_id"]
    node_ids = group["node_ids"]
    prompt = group["prompt"]

    start_time = time.time()

    # 创建输出目录
    filmstrips_dir = os.path.join(output_dir, "filmstrips")
    vlm_nodes_dir = os.path.join(output_dir, "vlm_nodes")
    Path(filmstrips_dir).mkdir(parents=True, exist_ok=True)
    Path(vlm_nodes_dir).mkdir(parents=True, exist_ok=True)

    filmstrip_path = os.path.join(filmstrips_dir, f"{group_id}.png")

    try:
        # 1. 调用 VLM 生成连环画
        log.info(f"[{group_id}] Generating filmstrip with {len(node_ids)} panels...")

        await generate_or_edit_and_save_image_async(
            prompt=prompt,
            save_path=filmstrip_path,
            api_url=api_url,
            api_key=api_key,
            model=vlm_model,
            use_edit=False,
            timeout=vlm_timeout,
        )

        log.info(f"[{group_id}] Filmstrip saved to {filmstrip_path}")

        # 2. 切图
        slicer = FilmstripSlicer()
        panels_dir = os.path.join(output_dir, "panels", group_id)
        panel_paths = slicer.slice_filmstrip(
            image_path=filmstrip_path,
            expected_count=len(node_ids),
            output_dir=panels_dir,
            prefix="panel",
        )

        log.info(f"[{group_id}] Sliced into {len(panel_paths)} panels")

        # 3. 处理每个 panel（去背景 + 裁剪）
        processor = PanelProcessor()
        panels_result = []

        for i, (node_id, panel_path) in enumerate(zip(node_ids, panel_paths)):
            output_path = os.path.join(vlm_nodes_dir, f"{node_id}.png")

            panel_info = processor.process_panel(
                panel_path=panel_path,
                output_path=output_path,
            )

            panels_result.append({
                "node_id": node_id,
                "path": panel_info["path"],
                "width_px": panel_info["width_px"],
                "height_px": panel_info["height_px"],
                "panel_index": i,
                "source_group_id": group_id,
            })

            log.info(
                f"[{group_id}] Panel {i} ({node_id}): "
                f"{panel_info['width_px']}x{panel_info['height_px']}px"
            )

        render_time_ms = int((time.time() - start_time) * 1000)

        return {
            "group_id": group_id,
            "status": "ok",
            "filmstrip_path": filmstrip_path,
            "panels": panels_result,
            "render_time_ms": render_time_ms,
        }

    except Exception as e:
        render_time_ms = int((time.time() - start_time) * 1000)
        log.error(f"[{group_id}] Render failed: {e}")

        return {
            "group_id": group_id,
            "status": "error",
            "error": str(e),
            "render_time_ms": render_time_ms,
        }


async def p2g_filmstrip_renderer_agent(
    state: FilmStripP2GState,
    vlm_model: Optional[str] = None,
    vlm_timeout: int = 600,
    concurrency: int = 2,
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs,
) -> FilmStripP2GState:
    """Film-Strip Renderer Agent 入口函数

    Args:
        state: FilmStripP2GState 状态对象
        vlm_model: VLM 模型名称
        vlm_timeout: VLM 超时时间（秒）
        concurrency: 并发数
        api_url: API URL（默认从环境变量读取，优先使用 VLM_API_URL）
        api_key: API Key（默认从环境变量读取，优先使用 VLM_API_KEY）

    Returns:
        更新后的 FilmStripP2GState
    """
    # 获取配置
    if vlm_model is None:
        vlm_model = getattr(state.request, "vlm_model", "gemini-2.0-flash-exp-image-generation")

    # VLM 生图优先使用 VLM_API_URL 和 VLM_API_KEY，如果没有设置则回退到 DF_API_URL 和 DF_API_KEY
    if api_url is None:
        api_url = os.getenv("VLM_API_URL") or os.getenv("DF_API_URL", "http://123.129.219.111:3000/v1")

    if api_key is None:
        api_key = os.getenv("VLM_API_KEY") or os.getenv("DF_API_KEY", "")

    # 打印使用的 API 配置来源
    vlm_url_source = "VLM_API_URL" if os.getenv("VLM_API_URL") else "DF_API_URL"
    vlm_key_source = "VLM_API_KEY" if os.getenv("VLM_API_KEY") else "DF_API_KEY"
    log.info(f"[FilmstripRenderer] Using API config: url from {vlm_url_source}, key from {vlm_key_source}")

    output_dir = getattr(state.request, "output_dir", ".tmp/filmstrip_p2g")

    vlm_group_plan_json = getattr(state, "vlm_group_plan_json", {})
    groups = vlm_group_plan_json.get("groups", [])

    if not groups:
        log.warning("[FilmstripRenderer] No groups to render")
        setattr(state, "filmstrip_images", {})
        setattr(state, "vlm_rendered_nodes", {})
        setattr(state, "vlm_node_assets", {})
        setattr(state, "filmstrip_render_errors", {})
        return state

    log.info(f"[FilmstripRenderer] Starting with {len(groups)} groups, concurrency={concurrency}")

    # 并发渲染
    semaphore = asyncio.Semaphore(concurrency)

    async def render_with_semaphore(group):
        async with semaphore:
            return await render_single_group(
                group=group,
                output_dir=output_dir,
                vlm_model=vlm_model,
                vlm_timeout=vlm_timeout,
                api_url=api_url,
                api_key=api_key,
            )

    results = await asyncio.gather(
        *[render_with_semaphore(g) for g in groups],
        return_exceptions=True,
    )

    # 整理结果
    filmstrip_images = {}
    vlm_rendered_nodes = {}
    vlm_node_assets = {}
    filmstrip_render_errors = {}

    for result in results:
        if isinstance(result, Exception):
            log.error(f"[FilmstripRenderer] Unexpected error: {result}")
            continue

        group_id = result["group_id"]

        if result["status"] == "ok":
            filmstrip_images[group_id] = {
                "path": result["filmstrip_path"],
                "render_time_ms": result["render_time_ms"],
                "status": "ok",
            }

            for panel in result["panels"]:
                node_id = panel["node_id"]
                vlm_rendered_nodes[node_id] = panel["path"]
                vlm_node_assets[node_id] = {
                    "path": panel["path"],
                    "width_px": panel["width_px"],
                    "height_px": panel["height_px"],
                    "source_group_id": panel["source_group_id"],
                    "panel_index": panel["panel_index"],
                }
        else:
            filmstrip_render_errors[group_id] = result.get("error", "Unknown error")
            filmstrip_images[group_id] = {
                "status": "error",
                "error": result.get("error", "Unknown error"),
                "render_time_ms": result.get("render_time_ms", 0),
            }

    # 更新 state
    setattr(state, "filmstrip_images", filmstrip_images)
    setattr(state, "vlm_rendered_nodes", vlm_rendered_nodes)
    setattr(state, "vlm_node_assets", vlm_node_assets)
    setattr(state, "filmstrip_render_errors", filmstrip_render_errors)

    # 统计
    success_count = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "ok")
    error_count = len(groups) - success_count
    total_nodes = len(vlm_rendered_nodes)

    log.info(
        f"[FilmstripRenderer] Completed: {success_count}/{len(groups)} groups, "
        f"{total_nodes} nodes rendered, {error_count} errors"
    )

    return state
