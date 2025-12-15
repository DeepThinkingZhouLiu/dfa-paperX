"""边渲染器

渲染节点之间的连接线/箭头。

优化特性：
1. 使用正确的箭头 API (MSO_ARROWHEAD_STYLE) 确保箭头清晰可见
2. 支持 from_anchor/to_anchor 锚点，决定从哪条边连接
3. 支持正交折线 (ELBOW) 连接器，让边更规整
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from pptx.util import Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR_TYPE

from dataflow_agent.logger import get_logger

log = get_logger(__name__)

# 有效的锚点值
VALID_ANCHORS = {"left", "right", "top", "bottom"}


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
    """边/连接线渲染器

    支持：
    - 正交折线 (ELBOW) 和直线 (STRAIGHT) 连接器
    - 锚点 (from_anchor/to_anchor) 指定连接位置
    - 清晰的箭头样式
    """

    # 默认边样式
    DEFAULT_EDGE_COLOR = "#555555"  # 深灰色，更明显
    DEFAULT_EDGE_WIDTH = 2.0  # pt，加粗

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
        use_elbow: bool = True,
    ) -> int:
        """渲染所有边

        Args:
            edges: 边列表，支持以下字段:
                - edge_id: 边 ID
                - from: 起始节点 ID
                - to: 目标节点 ID
                - from_anchor: 起始锚点 (left/right/top/bottom)
                - to_anchor: 目标锚点 (left/right/top/bottom)
                - edge_type: 边类型 (data_flow/control_flow/annotation)
                - route: 路由方式 (orthogonal/straight)
            node_bboxes: 节点 bbox 字典 {node_id: {"x", "y", "w", "h"}}
            edge_styles: 可选的边样式 {edge_id: {"color": "#xxx", "width": 1.5}}
            use_elbow: 是否默认使用正交折线

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

            # 合并 edge 自带的样式和外部样式
            style = {**edge, **edge_styles.get(edge_id, {})}

            if self._render_edge(edge_id, from_bbox, to_bbox, style, use_elbow):
                success_count += 1

        log.info(f"Rendered {success_count}/{len(edges)} edges")
        return success_count

    def _render_edge(
        self,
        edge_id: str,
        from_bbox: Dict[str, float],
        to_bbox: Dict[str, float],
        style: Dict[str, Any],
        use_elbow: bool = True,
    ) -> bool:
        """渲染单条边

        Args:
            edge_id: 边 ID
            from_bbox: 起始节点 bbox
            to_bbox: 目标节点 bbox
            style: 边样式（包含 from_anchor, to_anchor, route 等）
            use_elbow: 是否使用正交折线

        Returns:
            是否渲染成功
        """
        try:
            # 提取锚点信息
            from_anchor = style.get("from_anchor", "")
            to_anchor = style.get("to_anchor", "")
            route = style.get("route", "")

            # 计算连接点（利用锚点信息）
            start_x, start_y, auto_from_anchor = self._get_connection_point_with_anchor(
                from_bbox, to_bbox, from_anchor, is_start=True
            )
            end_x, end_y, auto_to_anchor = self._get_connection_point_with_anchor(
                to_bbox, from_bbox, to_anchor, is_start=False
            )

            # 转换为 EMU
            from .coordinate_utils import default_converter as conv
            start_x_emu = conv.px_to_emu(start_x)
            start_y_emu = conv.px_to_emu(start_y)
            end_x_emu = conv.px_to_emu(end_x)
            end_y_emu = conv.px_to_emu(end_y)

            # 决定连接器类型
            # 如果明确指定 route="straight"，则用直线；否则默认用正交折线
            if route == "straight" or not use_elbow:
                connector_type = MSO_CONNECTOR_TYPE.STRAIGHT
            else:
                # 使用正交折线 (ELBOW)
                connector_type = MSO_CONNECTOR_TYPE.ELBOW

            # 添加连接线
            connector = self.slide.shapes.add_connector(
                connector_type,
                Emu(start_x_emu), Emu(start_y_emu),
                Emu(end_x_emu), Emu(end_y_emu)
            )

            # 应用样式
            self._apply_edge_style(connector, style)

            connector_name = "ELBOW" if connector_type == MSO_CONNECTOR_TYPE.ELBOW else "STRAIGHT"
            log.debug(
                f"Rendered edge {edge_id}: ({start_x:.0f},{start_y:.0f}) -> ({end_x:.0f},{end_y:.0f}) "
                f"[{connector_name}, from={auto_from_anchor}, to={auto_to_anchor}]"
            )
            return True

        except Exception as e:
            log.error(f"Failed to render edge {edge_id}: {e}")
            return False

    def _get_connection_point_with_anchor(
        self,
        bbox: Dict[str, float],
        other_bbox: Dict[str, float],
        anchor: str,
        is_start: bool,
    ) -> Tuple[float, float, str]:
        """计算连接点位置（支持锚点）

        Args:
            bbox: 当前节点的 bbox
            other_bbox: 另一个节点的 bbox
            anchor: 指定的锚点 (left/right/top/bottom)，为空则自动计算
            is_start: 是否是起始点

        Returns:
            (x, y, actual_anchor): 连接点坐标和实际使用的锚点
        """
        # bbox 中心点
        cx = bbox["x"] + bbox["w"] / 2
        cy = bbox["y"] + bbox["h"] / 2

        # 如果指定了有效锚点，直接使用
        if anchor in VALID_ANCHORS:
            x, y = self._anchor_to_point(bbox, anchor)
            return (x, y, anchor)

        # 否则根据相对位置自动选择锚点
        other_cx = other_bbox["x"] + other_bbox["w"] / 2
        other_cy = other_bbox["y"] + other_bbox["h"] / 2

        dx = other_cx - cx
        dy = other_cy - cy

        # 根据主要方向选择连接边
        if abs(dx) > abs(dy):
            # 水平方向为主
            if dx > 0:
                # 另一个在右边，从右边缘连接
                auto_anchor = "right"
            else:
                # 另一个在左边，从左边缘连接
                auto_anchor = "left"
        else:
            # 垂直方向为主
            if dy > 0:
                # 另一个在下方，从下边缘连接
                auto_anchor = "bottom"
            else:
                # 另一个在上方，从上边缘连接
                auto_anchor = "top"

        x, y = self._anchor_to_point(bbox, auto_anchor)
        return (x, y, auto_anchor)

    def _anchor_to_point(
        self,
        bbox: Dict[str, float],
        anchor: str,
    ) -> Tuple[float, float]:
        """将锚点转换为具体坐标

        Args:
            bbox: 节点 bbox
            anchor: 锚点名称 (left/right/top/bottom)

        Returns:
            (x, y) 坐标
        """
        cx = bbox["x"] + bbox["w"] / 2
        cy = bbox["y"] + bbox["h"] / 2

        if anchor == "left":
            return (bbox["x"], cy)
        elif anchor == "right":
            return (bbox["x"] + bbox["w"], cy)
        elif anchor == "top":
            return (cx, bbox["y"])
        elif anchor == "bottom":
            return (cx, bbox["y"] + bbox["h"])
        else:
            # 默认返回中心点
            return (cx, cy)

    def _apply_edge_style(self, connector, style: Dict[str, Any]):
        """应用边样式

        使用正确的 python-pptx 箭头 API 确保箭头清晰可见
        """
        line = connector.line

        # 颜色
        color = style.get("color", self.DEFAULT_EDGE_COLOR)
        rgb = hex_to_rgb(color)
        if rgb:
            line.color.rgb = rgb

        # 线宽
        width = style.get("width", self.DEFAULT_EDGE_WIDTH)
        line.width = Pt(width)

        # 设置终点箭头 - 使用正确的 API
        try:
            from pptx.enum.dml import MSO_LINE_DASH_STYLE

            # 使用 line 的箭头属性（这是 python-pptx 的正确方式）
            # line.end_arrowhead 可能不存在于所有版本，尝试多种方式
            try:
                # 方法1: 直接设置 XML 属性（最可靠）
                from pptx.oxml.ns import qn
                from lxml import etree

                # 获取 line 的 XML 元素
                ln_elem = line._ln

                # 添加或更新 tailEnd 元素
                tail_end = ln_elem.find(qn("a:tailEnd"))
                if tail_end is None:
                    tail_end = etree.SubElement(ln_elem, qn("a:tailEnd"))

                # 设置箭头类型为 triangle（三角形，最清晰）
                tail_end.set("type", "triangle")
                # 设置箭头宽度和长度为 medium
                tail_end.set("w", "med")
                tail_end.set("len", "med")

                log.debug("Applied arrow style via XML")

            except Exception as xml_err:
                log.debug(f"XML arrow method failed: {xml_err}, trying fallback")
                # 方法2: 尝试旧版 API
                try:
                    from pptx.enum.shapes import MSO_ARROW_TYPE
                    connector.line.end_marker_style = MSO_ARROW_TYPE.STEALTH
                except Exception:
                    pass

        except Exception as e:
            log.warning(f"Failed to set arrow style: {e}")

        # 虚线样式
        try:
            from pptx.enum.dml import MSO_LINE_DASH_STYLE
            dash_style = style.get("dash_style", "solid")
            if dash_style == "dashed":
                line.dash_style = MSO_LINE_DASH_STYLE.DASH
        except Exception:
            pass
