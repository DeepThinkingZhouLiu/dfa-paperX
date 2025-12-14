# ================================================================
# 背景移除工具集
# - BriaRMBG2Remover: 使用 RMBG 2.0 模型（适合人物/产品照片）
# - EdgeFloodFillRemover: 基于边缘 flood fill（适合图表/图标）
# ================================================================

from __future__ import annotations
import os
import sys
import numpy as np
from pathlib import Path
from PIL import Image, ImageFilter
from scipy import ndimage

# 若依赖放在 ./deps 目录（推荐本地隔离）
DEPS_DIR = Path(__file__).resolve().parent / "deps"
if DEPS_DIR.exists():
    sys.path.append(str(DEPS_DIR))

import onnxruntime as ort

CURRENT_DIR = Path(__file__).resolve().parent
MODELS_DIR = CURRENT_DIR / "models" / "RMBG-2.0" / "onnx"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_OUTPUT_DIR = CURRENT_DIR
DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 使用 RMBG-2.0 的主模型
DEFAULT_MODEL_PATH = MODELS_DIR / "model.onnx"


class BriaRMBG2Remover:
    """使用 BRIA-RMBG 2.0 模型进行高质量抠图"""

    def __init__(self, model_path: str | None = None, output_dir: str | None = None):
        self.model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH

        if not self.model_path.exists():
            raise FileNotFoundError(f"模型文件不存在: {self.model_path}")

        # 初始化 ONNXRuntime 推理会话
        self.session = ort.InferenceSession(
            str(self.model_path),
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )

        self.output_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def remove_background(self, image_path: str) -> str:
        """输入图片路径，输出抠图后透明 PNG 文件路径"""
        img = Image.open(image_path).convert("RGB")
        orig_w, orig_h = img.size

        # 模型期望输入分辨率（1024x1024）
        side = 1024
        img_rs = img.resize((side, side), Image.BICUBIC)

        # 归一化 + 调整维度
        arr = np.asarray(img_rs).astype(np.float32) / 255.0
        arr = arr.transpose(2, 0, 1)[None, ...]  # (1,3,H,W)

        # 模型推理
        input_name = self.session.get_inputs()[0].name
        pred = self.session.run(None, {input_name: arr})[0]

        # RMBG 2.0 输出掩码（可能带边缘增强）
        mask = pred[0, 0]
        mask = np.clip(mask, 0, 1)
        mask = (mask * 255).astype(np.uint8)

        # 调整掩码尺寸回原图
        m = Image.fromarray(mask, "L").resize((orig_w, orig_h), Image.BICUBIC)

        # 合并 RGBA
        rgba = img.convert("RGBA")
        r, g, b, _ = rgba.split()
        out = Image.merge("RGBA", (r, g, b, m))

        # 轻微平滑边缘，增强自然感
        out = out.filter(ImageFilter.SMOOTH_MORE)

        name = Path(image_path).stem
        output_path = self.output_dir / f"{name}_bg_removed.png"
        out.save(output_path)
        print(f"抠图完成: {output_path}")
        return str(output_path)


class EdgeFloodFillRemover:
    """基于边缘 flood fill 的背景移除器

    适用于图表、图标等内容，特点：
    - 只移除与图片边缘连通的背景色区域
    - 保留内容区域内的白色/浅色元素
    - 不需要额外的深度学习模型
    - 多个元素作为整体保留（不会过度分割）
    """

    def __init__(
        self,
        output_dir: str | None = None,
        bg_threshold: int = 245,
        edge_smooth: bool = True,
        edge_smooth_radius: int = 2,
    ):
        """
        Args:
            output_dir: 输出目录
            bg_threshold: 背景色阈值，RGB 各通道都大于此值视为背景（默认 245）
            edge_smooth: 是否对边缘进行平滑处理
            edge_smooth_radius: 边缘平滑半径（像素）
        """
        self.output_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.bg_threshold = bg_threshold
        self.edge_smooth = edge_smooth
        self.edge_smooth_radius = edge_smooth_radius

    def remove_background(self, image_path: str) -> str:
        """移除背景，只保留内容区域

        Args:
            image_path: 输入图片路径

        Returns:
            输出图片路径（带透明通道的 PNG）
        """
        img = Image.open(image_path).convert("RGBA")
        data = np.array(img)
        h, w = data.shape[:2]

        # 1. 创建背景 mask：RGB 各通道都大于阈值的像素
        rgb = data[:, :, :3]
        bg_mask = np.all(rgb > self.bg_threshold, axis=2)

        # 2. 标记连通区域
        labeled, num_features = ndimage.label(bg_mask)

        # 3. 找到与边缘连通的区域标签
        edge_labels = set()
        edge_labels.update(labeled[0, :].tolist())       # 上边缘
        edge_labels.update(labeled[h - 1, :].tolist())   # 下边缘
        edge_labels.update(labeled[:, 0].tolist())       # 左边缘
        edge_labels.update(labeled[:, w - 1].tolist())   # 右边缘
        edge_labels.discard(0)  # 0 表示非背景区域

        # 4. 只移除与边缘连通的背景区域
        edge_bg_mask = np.isin(labeled, list(edge_labels))

        # 5. 创建 alpha 通道
        alpha = np.where(edge_bg_mask, 0, 255).astype(np.uint8)

        # 6. 边缘平滑处理（可选）
        if self.edge_smooth and self.edge_smooth_radius > 0:
            alpha = self._smooth_alpha_edge(alpha, edge_bg_mask)

        # 7. 合并 RGBA
        data[:, :, 3] = alpha
        out_img = Image.fromarray(data, "RGBA")

        # 8. 保存
        name = Path(image_path).stem
        output_path = self.output_dir / f"{name}_bg_removed.png"
        out_img.save(output_path)
        print(f"抠图完成（EdgeFloodFill）: {output_path}")
        return str(output_path)

    def _smooth_alpha_edge(self, alpha: np.ndarray, bg_mask: np.ndarray) -> np.ndarray:
        """对 alpha 通道边缘进行平滑处理，减少锯齿

        Args:
            alpha: 原始 alpha 通道
            bg_mask: 背景 mask

        Returns:
            平滑后的 alpha 通道
        """
        # 使用距离变换来创建渐变边缘
        # 计算前景区域到背景的距离
        foreground_mask = ~bg_mask
        dist_to_bg = ndimage.distance_transform_edt(foreground_mask)

        # 在边缘区域（距离小于 radius）创建渐变
        radius = self.edge_smooth_radius
        edge_zone = (dist_to_bg > 0) & (dist_to_bg <= radius)

        # 渐变 alpha：距离越近背景，alpha 越小
        smooth_alpha = alpha.copy().astype(np.float32)
        smooth_alpha[edge_zone] = (dist_to_bg[edge_zone] / radius) * 255

        return smooth_alpha.astype(np.uint8)


def local_tool_for_bg_remove(req: dict) -> str:
    """暴露统一接口（默认使用 RMBG 模型）"""
    remover = BriaRMBG2Remover(
        model_path=req.get("model_path"), output_dir=req.get("output_dir")
    )
    return remover.remove_background(req["image_path"])


def local_tool_for_edge_floodfill_bg_remove(req: dict) -> str:
    """暴露 EdgeFloodFill 接口（适合图表/图标）"""
    remover = EdgeFloodFillRemover(
        output_dir=req.get("output_dir"),
        bg_threshold=req.get("bg_threshold", 245),
        edge_smooth=req.get("edge_smooth", True),
        edge_smooth_radius=req.get("edge_smooth_radius", 2),
    )
    return remover.remove_background(req["image_path"])


def get_bg_remove_desc(lang: str = "zh") -> str:
    """中文说明"""
    return (
        "使用 BRIA-RMBG 2.0 模型执行高质量抠图，自动去除背景并输出带透明通道的 PNG 文件。"
        "支持多种输入格式（JPG/PNG/WebP），输出文件默认保存在同目录的 bg_removed/ 下。"
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="BRIA-RMBG 2.0 高质量抠图工具")
    parser.add_argument("image_path", help="输入图片路径")
    parser.add_argument("--model_path", default=None, help="模型路径（可选）")
    parser.add_argument("--output_dir", default=None, help="输出目录（可选）")
    args = parser.parse_args()

    out = local_tool_for_bg_remove(
        {
            "image_path": args.image_path,
            "model_path": args.model_path,
            "output_dir": args.output_dir,
        }
    )
    print(out)
