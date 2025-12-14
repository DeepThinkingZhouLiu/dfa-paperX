"""测试 p2g_pptx_desc_parser_agent

读取 tests/.tmp/render_design 中已有的 node_render_design.json，
调用 p2g_pptx_desc_parser_agent 生成结构化的 pptx_render_specs。
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
from dataflow_agent.agentroles.p2g_pptx_desc_parser_agent import (
    p2g_pptx_desc_parser_agent,
    P2gPptxDescParserAgent,
)


# 数据目录
DATA_DIR = Path(__file__).parent / ".tmp" / "render_design"
OUTPUT_DIR = Path(__file__).parent / ".tmp" / "pptx_specs"


def load_json(filename: str) -> dict:
    """加载 JSON 文件"""
    filepath = DATA_DIR / filename
    if not filepath.exists():
        print(f"Warning: {filepath} not found")
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: dict, filename: str):
    """保存 JSON 文件"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = OUTPUT_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved: {filepath}")


async def test_pptx_desc_parser():
    """测试 pptx_desc 解析 agent"""
    
    print("=" * 60)
    print("Loading data from tests/.tmp/render_design ...")
    print("=" * 60)
    
    # 加载上游数据
    node_render_design = load_json("node_render_design.json")
    
    if not node_render_design:
        print("ERROR: node_render_design.json not found!")
        print("Please run test_p2g_node_render_design_agent.py first.")
        return None
    
    # 统计 pptx 节点数量
    pptx_count = 0
    vlm_count = 0
    for chunk in node_render_design.get("chunks", []):
        for node in chunk.get("nodes", []):
            if node.get("render_method") == "pptx":
                pptx_count += 1
            elif node.get("render_method") == "vlm":
                vlm_count += 1
    
    print(f"\nLoaded node_render_design:")
    print(f"  - Total chunks: {len(node_render_design.get('chunks', []))}")
    print(f"  - PPTX nodes: {pptx_count}")
    print(f"  - VLM nodes: {vlm_count}")
    
    # 构建 state
    request = Paper2GraphRequest(
        target="Test target for pptx desc parsing",
        model="gpt-4o",
    )
    
    state = Paper2GraphState(request=request)
    state.node_render_design = node_render_design
    
    print("\n" + "=" * 60)
    print("Running p2g_pptx_desc_parser_agent ...")
    print("=" * 60)
    
    # 执行 agent
    state = await p2g_pptx_desc_parser_agent(
        state,
        model_name="gpt-4o",
        temperature=0.0,
        max_tokens=8192,  # 较大的 token 限制以处理多个节点
        parser_type="json",
    )
    
    # 获取结果
    pptx_render_specs = getattr(state, "pptx_render_specs", {})
    
    print("\n" + "=" * 60)
    print("Results:")
    print("=" * 60)
    
    if pptx_render_specs:
        print(f"\nTotal specs generated: {len(pptx_render_specs)}")
        
        # 显示每个 spec 的摘要
        for node_id, spec in pptx_render_specs.items():
            element_type = spec.get("element_type", "?")
            text = spec.get("text", "")[:40] if spec.get("text") else "<no text>"
            text_style = spec.get("text_style", {})
            shape_style = spec.get("shape_style", {})
            
            print(f"\n  {node_id}:")
            print(f"    element_type: {element_type}")
            print(f"    text: {text}...")
            print(f"    font: {text_style.get('font_family', '?')} {text_style.get('font_size', '?')}pt")
            print(f"    bold: {text_style.get('bold', False)}, color: {text_style.get('color', '?')}")
            print(f"    fill: {shape_style.get('fill_color', 'none')}, border: {shape_style.get('border_style', '?')}")
        
        # 保存结果
        save_json(pptx_render_specs, "pptx_render_specs.json")
        
        # 验证所有 pptx 节点都有对应的 spec
        missing = []
        for chunk in node_render_design.get("chunks", []):
            for node in chunk.get("nodes", []):
                if node.get("render_method") == "pptx":
                    if node["node_id"] not in pptx_render_specs:
                        missing.append(node["node_id"])
        
        if missing:
            print(f"\n⚠️  Missing specs for nodes: {missing}")
        else:
            print(f"\n✅ All {pptx_count} pptx nodes have corresponding specs!")
    else:
        print("No pptx_render_specs generated!")
        print(f"Agent results: {state.agent_results}")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)
    
    return pptx_render_specs


if __name__ == "__main__":
    asyncio.run(test_pptx_desc_parser())

