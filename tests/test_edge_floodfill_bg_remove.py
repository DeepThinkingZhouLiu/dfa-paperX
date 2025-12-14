"""测试 EdgeFloodFillRemover 抠图效果

用法：
    python tests/test_edge_floodfill_bg_remove.py --image <图片路径>
    python tests/test_edge_floodfill_bg_remove.py --image tests/.tmp/vlm_nodes/n3_raw.png
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# 设置项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from dataflow_agent.toolkits.imtool.bg_tool import EdgeFloodFillRemover


def test_edge_floodfill(image_path: str, output_dir: str, bg_threshold: int = 245):
    """测试 EdgeFloodFillRemover"""
    print(f"\n{'=' * 60}")
    print("EdgeFloodFillRemover 测试")
    print(f"{'=' * 60}")
    print(f"输入图片: {image_path}")
    print(f"输出目录: {output_dir}")
    print(f"背景阈值: {bg_threshold}")

    # 检查输入文件
    if not Path(image_path).exists():
        print(f"错误: 图片文件不存在: {image_path}")
        return

    # 创建 remover
    remover = EdgeFloodFillRemover(
        output_dir=output_dir,
        bg_threshold=bg_threshold,
        edge_smooth=True,
        edge_smooth_radius=2,
    )

    # 执行抠图
    try:
        output_path = remover.remove_background(image_path)
        print(f"\n✓ 抠图成功!")
        print(f"  输出文件: {output_path}")

        # 检查输出文件
        if Path(output_path).exists():
            from PIL import Image
            img = Image.open(output_path)
            print(f"  图片尺寸: {img.size}")
            print(f"  图片模式: {img.mode}")

            # 统计透明像素
            if img.mode == "RGBA":
                import numpy as np
                data = np.array(img)
                total_pixels = data.shape[0] * data.shape[1]
                transparent_pixels = np.sum(data[:, :, 3] == 0)
                semi_transparent = np.sum((data[:, :, 3] > 0) & (data[:, :, 3] < 255))
                opaque_pixels = np.sum(data[:, :, 3] == 255)

                print(f"  总像素数: {total_pixels}")
                print(f"  完全透明: {transparent_pixels} ({100*transparent_pixels/total_pixels:.1f}%)")
                print(f"  半透明: {semi_transparent} ({100*semi_transparent/total_pixels:.1f}%)")
                print(f"  完全不透明: {opaque_pixels} ({100*opaque_pixels/total_pixels:.1f}%)")

    except Exception as e:
        print(f"\n✗ 抠图失败: {e}")
        import traceback
        traceback.print_exc()


def compare_methods(image_path: str, output_dir: str):
    """对比两种抠图方法"""
    print(f"\n{'=' * 60}")
    print("对比两种抠图方法")
    print(f"{'=' * 60}")

    if not Path(image_path).exists():
        print(f"错误: 图片文件不存在: {image_path}")
        return

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # 1. EdgeFloodFill 方法
    print("\n[1] EdgeFloodFillRemover:")
    try:
        from dataflow_agent.toolkits.imtool.bg_tool import EdgeFloodFillRemover
        remover1 = EdgeFloodFillRemover(output_dir=output_dir, bg_threshold=245)
        out1 = remover1.remove_background(image_path)
        print(f"    输出: {out1}")
    except Exception as e:
        print(f"    失败: {e}")

    # 2. RMBG 方法（如果模型存在）
    print("\n[2] BriaRMBG2Remover:")
    try:
        from dataflow_agent.toolkits.imtool.bg_tool import BriaRMBG2Remover
        remover2 = BriaRMBG2Remover(output_dir=output_dir)
        out2 = remover2.remove_background(image_path)
        print(f"    输出: {out2}")
    except FileNotFoundError as e:
        print(f"    跳过（模型文件不存在）: {e}")
    except Exception as e:
        print(f"    失败: {e}")

    print(f"\n请查看 {output_dir} 目录对比结果")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="测试 EdgeFloodFillRemover")
    parser.add_argument(
        "--image",
        type=str,
        required=True,
        help="输入图片路径"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="tests/.tmp/bg_remove_test",
        help="输出目录"
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=245,
        help="背景色阈值（默认 245）"
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="对比两种抠图方法"
    )

    args = parser.parse_args()

    if args.compare:
        compare_methods(args.image, args.output_dir)
    else:
        test_edge_floodfill(args.image, args.output_dir, args.threshold)
