"""边渲染器

渲染节点之间的连接线/箭头。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from pptx.util import Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR_TYPE

from dataflow_agent.logger import get_logger

log = get_logger(__name__)


def hex_to_rgb(hex_color: str) -> Optional[RGBColor]:
    """将 hex 颜色转换为 RGBColor"""
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


class EdgeRenderer:
    """边/连接线渲染器"""

    # 默认边样式
    DEFAULT_EDGE_COLOR = "#808080"  # 灰色
    DEFAULT_EDGE_WIDTH = 1.5  # pt

    def __init__(self, slide):
        """
        Args:
            slide: python-pptx Slide 对象
        """
        self.slide = slide

    def render_edges(
        self,
        edges: List[Dict[str, Any]],
        node_bboxes: Dict[str, Dict[str, float]],
        edge_styles: Optional[Dict[str, Dict]] = None,
    ) -> int:
        """渲染所有边

        Args:
            edges: 边列表 [{"edge_id": "e1", "from": "n1", "to": "n2"}, ...]
            node_bboxes: 节点 bbox 字典 {node_id: {"x", "y", "w", "h"}}
            edge_styles: 可选的边样式 {edge_id: {"color": "#xxx", "width": 1.5}}

        Returns:
            成功渲染的边数量
        """
        edge_styles = edge_styles or {}
        success_count = 0

        for edge in edges:
            edge_id = edge.get("edge_id", "")
            from_node = edge.get("from", "")
            to_node = edge.get("to", "")

            if not from_node or not to_node:
                log.warning(f"Edge {edge_id} missing from/to node")
                continue

            from_bbox = node_bboxes.get(from_node)
            to_bbox = node_bboxes.get(to_node)

            if not from_bbox or not to_bbox:
                log.warning(f"Edge {edge_id}: bbox not found for {from_node} or {to_node}")
                continue

            style = edge_styles.get(edge_id, {})
            if self._render_edge(edge_id, from_bbox, to_bbox, style):
                success_count += 1

        log.info(f"Rendered {success_count}/{len(edges)} edges")
        return success_count

    def _render_edge(
        self,
        edge_id: str,
        from_bbox: Dict[str, float],
        to_bbox: Dict[str, float],
        style: Dict[str, Any],
    ) -> bool:
        """渲染单条边

        Args:
            edge_id: 边 ID
            from_bbox: 起始节点 bbox
            to_bbox: 目标节点 bbox
            style: 边样式

        Returns:
            是否渲染成功
        """
        try:
            # 计算连接点
            start_x, start_y = self._get_connection_point(from_bbox, to_bbox, is_start=True)
            end_x, end_y = self._get_connection_point(to_bbox, from_bbox, is_start=False)

            # 转换为 EMU
            from .coordinate_utils import default_converter as conv
            start_x_emu = conv.px_to_emu(start_x)
            start_y_emu = conv.px_to_emu(start_y)
            end_x_emu = conv.px_to_emu(end_x)
            end_y_emu = conv.px_to_emu(end_y)

            # 添加连接线
            connector = self.slide.shapes.add_connector(
                MSO_CONNECTOR_TYPE.STRAIGHT,
                Emu(start_x_emu), Emu(start_y_emu),
                Emu(end_x_emu), Emu(end_y_emu)
            )

            # 应用样式
            self._apply_edge_style(connector, style)

            log.debug(f"Rendered edge {edge_id}: ({start_x:.0f},{start_y:.0f}) -> ({end_x:.0f},{end_y:.0f})")
            return True

        except Exception as e:
            log.error(f"Failed to render edge {edge_id}: {e}")
            return False

    def _get_connection_point(
        self,
        bbox: Dict[str, float],
        other_bbox: Dict[str, float],
        is_start: bool,
    ) -> Tuple[float, float]:
        """计算连接点位置

        根据两个节点的相对位置，选择合适的边缘点作为连接点。
        """
        # bbox 中心点
        cx = bbox["x"] + bbox["w"] / 2
        cy = bbox["y"] + bbox["h"] / 2

        # 另一个 bbox 的中心点
        other_cx = other_bbox["x"] + other_bbox["w"] / 2
        other_cy = other_bbox["y"] + other_bbox["h"] / 2

        # 计算相对方向
        dx = other_cx - cx
        dy = other_cy - cy

        # 根据主要方向选择连接边
        if abs(dx) > abs(dy):
            # 水平方向为主
            if dx > 0:
                # 另一个在右边，从右边缘连接
                return (bbox["x"] + bbox["w"], cy)
            else:
                # 另一个在左边，从左边缘连接
                return (bbox["x"], cy)
        else:
            # 垂直方向为主
            if dy > 0:
                # 另一个在下方，从下边缘连接
                return (cx, bbox["y"] + bbox["h"])
            else:
                # 另一个在上方，从上边缘连接
                return (cx, bbox["y"])

    def _apply_edge_style(self, connector, style: Dict[str, Any]):
        """应用边样式"""
        line = connector.line

        # 颜色
        color = style.get("color", self.DEFAULT_EDGE_COLOR)
        rgb = hex_to_rgb(color)
        if rgb:
            line.color.rgb = rgb

        # 线宽
        width = style.get("width", self.DEFAULT_EDGE_WIDTH)
        line.width = Pt(width)

        # 箭头
        from pptx.enum.dml import MSO_LINE_DASH_STYLE

        # 设置终点箭头
        try:
            from pptx.enum.shapes import MSO_ARROW_TYPE
            connector.line.end_marker_style = MSO_ARROW_TYPE.STEALTH
        except Exception:
            # 某些版本可能不支持
            pass

        # 虚线样式
        dash_style = style.get("dash_style", "solid")
        if dash_style == "dashed":
            line.dash_style = MSO_LINE_DASH_STYLE.DASH
