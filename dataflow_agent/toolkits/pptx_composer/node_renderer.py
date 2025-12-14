"""节点渲染器

根据 PPTXRenderSpec 渲染 PPTX 原生节点，或插入 VLM 生成的图片。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from pptx.util import Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.enum.shapes import MSO_SHAPE

from dataflow_agent.logger import get_logger

log = get_logger(__name__)


# 对齐方式映射
ALIGNMENT_MAP = {
    "left": PP_ALIGN.LEFT,
    "center": PP_ALIGN.CENTER,
    "right": PP_ALIGN.RIGHT,
}


def hex_to_rgb(hex_color: str) -> Optional[RGBColor]:
    """将 hex 颜色转换为 RGBColor
    
    Args:
        hex_color: "#RRGGBB" 格式的颜色字符串
        
    Returns:
        RGBColor 对象，如果颜色无效则返回 None
    """
    if not hex_color:
        return None
    try:
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return RGBColor(r, g, b)
    except (ValueError, TypeError):
        pass
    return None


class PPTXNodeRenderer:
    """PPTX 节点渲染器"""
    
    def __init__(self, slide):
        """
        Args:
            slide: python-pptx Slide 对象
        """
        self.slide = slide
    
    def render_node(
        self,
        node_id: str,
        bbox_emu: Tuple[int, int, int, int],
        spec: Dict[str, Any],
    ) -> bool:
        """根据 spec 渲染节点
        
        Args:
            node_id: 节点 ID
            bbox_emu: (left, top, width, height) EMU 坐标
            spec: PPTXRenderSpec 字典
            
        Returns:
            是否渲染成功
        """
        element_type = spec.get("element_type", "text_box")
        
        try:
            if element_type == "text_box":
                self._render_text_box(bbox_emu, spec)
            elif element_type == "rectangle":
                self._render_rectangle(bbox_emu, spec, rounded=False)
            elif element_type == "rounded_rectangle":
                self._render_rectangle(bbox_emu, spec, rounded=True)
            elif element_type == "arrow":
                self._render_arrow_annotation(bbox_emu, spec)
            elif element_type == "line":
                self._render_line(bbox_emu, spec)
            else:
                # 默认作为文本框处理
                log.warning(f"Unknown element_type '{element_type}' for {node_id}, using text_box")
                self._render_text_box(bbox_emu, spec)
            
            log.debug(f"Rendered node {node_id} as {element_type}")
            return True
            
        except Exception as e:
            log.error(f"Failed to render node {node_id}: {e}")
            return False
    
    def render_vlm_image(
        self,
        node_id: str,
        bbox_emu: Tuple[int, int, int, int],
        image_path: str,
        fit_mode: str = "contain",
    ) -> bool:
        """插入 VLM 生成的图片，支持等比缩放

        Args:
            node_id: 节点 ID
            bbox_emu: (left, top, width, height) EMU 坐标
            image_path: 图片文件路径
            fit_mode: 适应模式
                - "contain": 等比缩放，完整显示，居中放置（推荐）
                - "cover": 等比缩放，填满区域，可能裁剪
                - "stretch": 强制拉伸（不推荐，会扭曲）

        Returns:
            是否插入成功
        """
        if not image_path or not Path(image_path).exists():
            log.error(f"Image not found for node {node_id}: {image_path}")
            return False

        try:
            from PIL import Image

            # 获取原始图片尺寸
            with Image.open(image_path) as img:
                img_w, img_h = img.size

            left, top, width, height = bbox_emu

            if fit_mode == "stretch":
                # 强制拉伸（不推荐）
                new_left, new_top = left, top
                new_width, new_height = width, height
            elif fit_mode == "contain":
                # 等比缩放，完整显示，居中放置
                bbox_ratio = width / height if height > 0 else 1
                img_ratio = img_w / img_h if img_h > 0 else 1

                if img_ratio > bbox_ratio:
                    # 图片更宽，以宽度为准
                    new_width = width
                    new_height = int(width / img_ratio)
                    new_left = left
                    new_top = top + (height - new_height) // 2
                else:
                    # 图片更高，以高度为准
                    new_height = height
                    new_width = int(height * img_ratio)
                    new_left = left + (width - new_width) // 2
                    new_top = top
            elif fit_mode == "cover":
                # 等比缩放，填满区域
                bbox_ratio = width / height if height > 0 else 1
                img_ratio = img_w / img_h if img_h > 0 else 1

                if img_ratio > bbox_ratio:
                    # 图片更宽，以高度为准
                    new_height = height
                    new_width = int(height * img_ratio)
                    new_left = left + (width - new_width) // 2
                    new_top = top
                else:
                    # 图片更高，以宽度为准
                    new_width = width
                    new_height = int(width / img_ratio)
                    new_left = left
                    new_top = top + (height - new_height) // 2
            else:
                # 默认 contain
                new_left, new_top = left, top
                new_width, new_height = width, height

            self.slide.shapes.add_picture(
                image_path,
                Emu(new_left), Emu(new_top),
                Emu(new_width), Emu(new_height)
            )

            log.debug(f"Inserted VLM image for {node_id}: fit_mode={fit_mode}, "
                      f"original={img_w}x{img_h}, bbox={width}x{height}, "
                      f"final={new_width}x{new_height}")
            return True

        except ImportError:
            # PIL 不可用时，回退到强制拉伸
            log.warning(f"PIL not available, using stretch mode for {node_id}")
            left, top, width, height = bbox_emu
            self.slide.shapes.add_picture(
                image_path,
                Emu(left), Emu(top),
                Emu(width), Emu(height)
            )
            return True

        except Exception as e:
            log.error(f"Failed to insert image for node {node_id}: {e}")
            return False
    
    def _render_text_box(self, bbox_emu: Tuple[int, int, int, int], spec: Dict):
        """渲染文本框，支持自适应"""
        left, top, width, height = bbox_emu

        txBox = self.slide.shapes.add_textbox(
            Emu(left), Emu(top), Emu(width), Emu(height)
        )
        tf = txBox.text_frame
        tf.word_wrap = True

        # 自适应模式
        auto_fit = spec.get("auto_fit", "shrink")  # "shrink" | "expand" | "none"

        if auto_fit == "shrink":
            # 自动缩小字体以适应框
            tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
        elif auto_fit == "expand":
            # 自动扩展框以适应文本
            tf.auto_size = MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT
        else:
            tf.auto_size = None

        # 垂直居中
        tf.anchor = MSO_ANCHOR.MIDDLE

        # 设置文本
        text = spec.get("text", "")
        text_lines = spec.get("text_lines")
        text_style = spec.get("text_style", {})

        p = tf.paragraphs[0]
        p.text = text if not text_lines else "\n".join(text_lines)

        # 应用文本样式
        self._apply_text_style(p, text_style)

        # 设置形状样式（通常文本框无填充无边框）
        shape_style = spec.get("shape_style", {})
        self._apply_shape_style(txBox, shape_style)

    def _render_rectangle(self, bbox_emu: Tuple[int, int, int, int], spec: Dict, rounded: bool = False):
        """渲染矩形"""
        left, top, width, height = bbox_emu

        shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
        shape = self.slide.shapes.add_shape(
            shape_type,
            Emu(left), Emu(top), Emu(width), Emu(height)
        )

        # 应用形状样式
        shape_style = spec.get("shape_style", {})
        self._apply_shape_style(shape, shape_style)

        # 如果有文本，添加到形状中
        text = spec.get("text", "")
        text_lines = spec.get("text_lines")
        if text or text_lines:
            tf = shape.text_frame
            tf.word_wrap = True
            tf.anchor = MSO_ANCHOR.MIDDLE

            p = tf.paragraphs[0]
            p.text = text if not text_lines else "\n".join(text_lines)

            text_style = spec.get("text_style", {})
            self._apply_text_style(p, text_style)

    def _render_arrow_annotation(self, bbox_emu: Tuple[int, int, int, int], spec: Dict):
        """渲染箭头注释（文本框 + 可选的箭头指示）"""
        # 简化处理：作为带样式的文本框
        self._render_text_box(bbox_emu, spec)

    def _render_line(self, bbox_emu: Tuple[int, int, int, int], spec: Dict):
        """渲染线条"""
        left, top, width, height = bbox_emu

        # 从 bbox 推断线条方向
        end_x = left + width
        end_y = top + height

        connector = self.slide.shapes.add_connector(
            1,  # MSO_CONNECTOR.STRAIGHT
            Emu(left), Emu(top),
            Emu(end_x), Emu(end_y)
        )

        shape_style = spec.get("shape_style", {})
        border_color = hex_to_rgb(shape_style.get("border_color"))
        if border_color:
            connector.line.color.rgb = border_color

    def _apply_text_style(self, paragraph, text_style: Dict):
        """应用文本样式到段落"""
        font = paragraph.font

        # 字体
        font_family = text_style.get("font_family", "Arial")
        font.name = font_family

        # 字号
        font_size = text_style.get("font_size", 12)
        font.size = Pt(font_size)

        # 粗体/斜体
        font.bold = text_style.get("bold", False)
        font.italic = text_style.get("italic", False)

        # 颜色
        color = hex_to_rgb(text_style.get("color", "#333333"))
        if color:
            font.color.rgb = color

        # 对齐
        alignment = text_style.get("alignment", "left")
        paragraph.alignment = ALIGNMENT_MAP.get(alignment, PP_ALIGN.LEFT)

    def _apply_shape_style(self, shape, shape_style: Dict):
        """应用形状样式"""
        fill = shape.fill
        line = shape.line

        # 填充
        fill_color = shape_style.get("fill_color")
        if fill_color:
            rgb = hex_to_rgb(fill_color)
            if rgb:
                fill.solid()
                fill.fore_color.rgb = rgb
        else:
            fill.background()  # 无填充

        # 边框
        border_style = shape_style.get("border_style", "none")
        border_color = shape_style.get("border_color")
        border_width = shape_style.get("border_width", 1.0)

        if border_style == "none" or not border_color:
            line.fill.background()  # 无边框
        else:
            rgb = hex_to_rgb(border_color)
            if rgb:
                line.color.rgb = rgb
                line.width = Pt(border_width)

                if border_style == "dashed":
                    from pptx.enum.dml import MSO_LINE_DASH_STYLE
                    line.dash_style = MSO_LINE_DASH_STYLE.DASH

