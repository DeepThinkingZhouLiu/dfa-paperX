"""测试 p2g_pptx_composer_agent

加载所有上游数据，组装生成最终的 PPTX 文件。
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

# 避免导入 agentroles 包时自动导入全部 agent 造成外部依赖错误
os.environ.setdefault("DF_SKIP_AGENTROLE_AUTOINIT", "1")

# 设置项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)

import sys
sys.path.insert(0, str(PROJECT_ROOT))

from dataflow_agent.state import Paper2GraphState, Paper2GraphRequest
from dataflow_agent.agentroles.p2g_pptx_composer_agent import p2g_pptx_composer_agent


# 数据目录
DATA_DIR = Path(__file__).parent / ".tmp"
OUTPUT_DIR = Path(__file__).parent / ".tmp" / "output"
# VLM 渲染结果目录（注意：目录名是 vlm_ndoes）
VLM_NODES_DIR = DATA_DIR / "vlm_ndoes"


def load_json(relative_path: str) -> dict:
    """加载 JSON 文件"""
    filepath = DATA_DIR / relative_path
    if not filepath.exists():
        print(f"Warning: {filepath} not found")
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def load_vlm_rendered_nodes() -> dict:
    """加载真实的 VLM 渲染结果

    从 vlm_ndoes/vlm_rendered_nodes.json 加载，
    并转换为 PPTXBuilder 期望的格式: {node_id: image_path}
    """
    vlm_nodes = {}

    # 尝试加载 vlm_rendered_nodes.json
    json_path = VLM_NODES_DIR / "vlm_rendered_nodes.json"
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        rendered_nodes = data.get("rendered_nodes", {})
        for node_id, node_info in rendered_nodes.items():
            # node_info 格式: {path, chunk_id, filename}
            image_path = node_info.get("path")
            if image_path and Path(image_path).exists():
                vlm_nodes[node_id] = image_path
            else:
                print(f"Warning: VLM image not found for {node_id}: {image_path}")

        print(f"Loaded {len(vlm_nodes)} VLM rendered nodes from {json_path}")
    else:
        print(f"Warning: {json_path} not found, will use placeholder images")

    return vlm_nodes


def create_placeholder_image(output_path: str, width: int = 200, height: int = 100):
    """创建占位图片（用于测试）"""
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (width, height), color=(240, 240, 240))
        draw = ImageDraw.Draw(img)

        # 画边框
        draw.rectangle([0, 0, width-1, height-1], outline=(200, 200, 200))

        # 添加文字
        text = Path(output_path).stem
        draw.text((10, height//2 - 10), text[:20], fill=(100, 100, 100))

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path)
        return True
    except ImportError:
        print("PIL not available, skipping placeholder image creation")
        return False


def fill_missing_vlm_nodes(vlm_nodes: dict, node_render_design: dict) -> dict:
    """为缺失的 VLM 节点创建占位图片

    Args:
        vlm_nodes: 已加载的 VLM 节点路径
        node_render_design: 渲染设计，用于获取所有 VLM 节点列表

    Returns:
        更新后的 vlm_nodes 字典
    """
    placeholder_dir = DATA_DIR / "vlm_placeholder"
    placeholder_dir.mkdir(parents=True, exist_ok=True)

    for chunk in node_render_design.get("chunks", []):
        for node in chunk.get("nodes", []):
            if node.get("render_method") == "vlm":
                node_id = node.get("node_id")
                if node_id not in vlm_nodes:
                    img_path = placeholder_dir / f"{node_id}.png"
                    if create_placeholder_image(str(img_path)):
                        vlm_nodes[node_id] = str(img_path)
                        print(f"Created placeholder for missing node: {node_id}")

    return vlm_nodes


async def test_pptx_composer():
    """测试 PPTX 组装

    - 从 vlm_ndoes/vlm_rendered_nodes.json 加载真实渲染的 VLM 节点图片
    - 暂时禁用 edges 绘制（edges 绘制逻辑需要优化）
    - 只绘制 chunks 和 nodes
    """

    print("=" * 60)
    print("Loading upstream data...")
    print("=" * 60)

    # 加载所有上游数据
    layout_json = load_json("layout_pipeline/layout_json.json")
    semantic_json = load_json("layout_pipeline/semantic_json.json")
    node_render_design = load_json("render_design/node_render_design.json")
    pptx_render_specs = load_json("pptx_specs/pptx_render_specs.json")

    # 检查数据
    if not layout_json:
        print("ERROR: layout_json.json not found!")
        return None
    if not node_render_design:
        print("ERROR: node_render_design.json not found!")
        return None

    print(f"\nLoaded data:")
    print(f"  - layout_json: {len(layout_json.get('positions', {}).get('nodes', []))} nodes")
    print(f"  - semantic_json: {len(semantic_json.get('edges', []))} edges")
    print(f"  - pptx_render_specs: {len(pptx_render_specs)} specs")

    # 加载真实的 VLM 渲染结果
    vlm_rendered_nodes = load_vlm_rendered_nodes()

    # 为缺失的 VLM 节点创建占位图片
    vlm_rendered_nodes = fill_missing_vlm_nodes(vlm_rendered_nodes, node_render_design)
    print(f"  - vlm_rendered_nodes: {len(vlm_rendered_nodes)} images (real + placeholder)")

    # 构建 state
    request = Paper2GraphRequest(
        target="Test PPTX composition",
        model="none",
    )

    state = Paper2GraphState(request=request)
    state.layout_json = layout_json
    state.semantic_json = semantic_json
    state.node_render_design = node_render_design
    state.pptx_render_specs = pptx_render_specs
    state.vlm_rendered_nodes = vlm_rendered_nodes

    # 输出路径
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = str(OUTPUT_DIR / "paper2graph_test.pptx")

    print("\n" + "=" * 60)
    print("Running p2g_pptx_composer_agent...")
    print("=" * 60)

    # 执行组装
    # 注意：暂时禁用 edges 绘制，因为 edges 绘制逻辑需要优化
    state = await p2g_pptx_composer_agent(
        state,
        output_path=output_path,
        render_edges=False,  # 暂时禁用 edges 绘制
        render_chunk_bg=True,  # 启用 chunk 背景绘制
    )

    # 验证结果
    print("\n" + "=" * 60)
    print("Results:")
    print("=" * 60)

    result = state.agent_results.get("p2g_pptx_composer_agent", {})
    print(f"\nStatus: {result.get('status', 'unknown')}")

    if result.get("status") == "ok":
        stats = result.get("stats", {})
        print(f"\nStats:")
        print(f"  - PPTX nodes rendered: {stats.get('pptx_nodes_rendered', 0)}")
        print(f"  - VLM nodes rendered: {stats.get('vlm_nodes_rendered', 0)}")
        print(f"  - Edges rendered: {stats.get('edges_rendered', 0)} (disabled)")

        if stats.get("errors"):
            print(f"\nErrors ({len(stats['errors'])}):")
            for err in stats["errors"][:10]:
                print(f"  - {err}")

        output_file = Path(state.pptx_output_path)
        if output_file.exists():
            print(f"\nPPTX generated: {output_file}")
            print(f"   File size: {output_file.stat().st_size / 1024:.1f} KB")
        else:
            print(f"\nOutput file not found: {state.pptx_output_path}")
    else:
        print(f"\nFailed: {result.get('error', 'Unknown error')}")

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)

    return state


if __name__ == "__main__":
    asyncio.run(test_pptx_composer())

