"""坐标转换工具

将像素坐标转换为 PowerPoint 的 EMU (English Metric Units)。
"""

from __future__ import annotations

from typing import Dict, Tuple


class CoordinateConverter:
    """像素到 EMU 坐标转换器
    
    PowerPoint 使用 EMU 作为内部坐标单位:
    - 1 inch = 914400 EMU
    - 假设屏幕 DPI = 96，则 1 px = 914400 / 96 = 9525 EMU
    """
    
    # 1 inch = 914400 EMU, 假设 96 DPI
    EMU_PER_INCH = 914400
    DEFAULT_DPI = 96
    PX_TO_EMU = EMU_PER_INCH / DEFAULT_DPI  # 9525
    
    def __init__(self, dpi: int = 96):
        """
        Args:
            dpi: 屏幕 DPI，默认 96
        """
        self.dpi = dpi
        self.px_to_emu_ratio = self.EMU_PER_INCH / dpi
    
    def px_to_emu(self, px: float) -> int:
        """将像素值转换为 EMU
        
        Args:
            px: 像素值
            
        Returns:
            EMU 值（整数）
        """
        return int(px * self.px_to_emu_ratio)
    
    def emu_to_px(self, emu: int) -> float:
        """将 EMU 转换为像素值
        
        Args:
            emu: EMU 值
            
        Returns:
            像素值
        """
        return emu / self.px_to_emu_ratio
    
    def bbox_to_emu(self, bbox: Dict[str, float]) -> Tuple[int, int, int, int]:
        """将 bbox 字典转换为 EMU 元组
        
        Args:
            bbox: {"x": px, "y": px, "w": px, "h": px}
            
        Returns:
            (left, top, width, height) 的 EMU 元组
        """
        return (
            self.px_to_emu(bbox.get("x", 0)),
            self.px_to_emu(bbox.get("y", 0)),
            self.px_to_emu(bbox.get("w", 0)),
            self.px_to_emu(bbox.get("h", 0)),
        )
    
    def point_to_emu(self, x: float, y: float) -> Tuple[int, int]:
        """将点坐标转换为 EMU
        
        Args:
            x: X 坐标（像素）
            y: Y 坐标（像素）
            
        Returns:
            (x_emu, y_emu) 元组
        """
        return (self.px_to_emu(x), self.px_to_emu(y))
    
    @classmethod
    def get_slide_size_emu(cls, width_px: int = 1920, height_px: int = 1080) -> Tuple[int, int]:
        """获取幻灯片尺寸（EMU）
        
        Args:
            width_px: 宽度（像素），默认 1920
            height_px: 高度（像素），默认 1080
            
        Returns:
            (width_emu, height_emu) 元组
        """
        converter = cls()
        return (converter.px_to_emu(width_px), converter.px_to_emu(height_px))


# 全局默认转换器实例
default_converter = CoordinateConverter()

