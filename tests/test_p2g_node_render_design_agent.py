"""测试 p2g_node_render_design_agent

读取 tests/.tmp/layout_pipeline 中已有的信息，
直接调用 p2g_node_render_design_agent 生成渲染设计结果。
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
from dataflow_agent.agentroles.p2g_node_render_design_agent import (
    p2g_node_render_design_agent,
    P2gNodeRenderDesignAgent,
)


# 数据目录
DATA_DIR = Path(__file__).parent / ".tmp" / "layout_pipeline"
OUTPUT_DIR = Path(__file__).parent / ".tmp" / "render_design"


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


async def test_node_render_design():
    """测试节点渲染设计 agent"""
    
    print("=" * 60)
    print("Loading data from tests/.tmp/layout_pipeline ...")
    print("=" * 60)
    
    # 加载上游数据
    enriched_description = load_json("enriched_description.json")
    semantic_json = load_json("semantic_json.json")
    layout_plan = load_json("layout_plan.json")
    node_layout_plan = load_json("node_layout_plan.json")
    layout_json = load_json("layout_json.json")
    
    print(f"\nLoaded enriched_description: {bool(enriched_description)}")
    print(f"Loaded semantic_json: {bool(semantic_json)}")
    print(f"  - chunks: {len(semantic_json.get('chunks', []))}")
    print(f"  - nodes: {len(semantic_json.get('nodes', []))}")
    print(f"  - edges: {len(semantic_json.get('edges', []))}")
    print(f"Loaded layout_plan: {bool(layout_plan)}")
    print(f"Loaded node_layout_plan: {bool(node_layout_plan)}")
    print(f"  - chunks: {len(node_layout_plan.get('chunks', []))}")
    print(f"Loaded layout_json: {bool(layout_json)}")
    
    # 构建 state
    request = Paper2GraphRequest(
        target="Test target for node render design",
        model="gpt-4o",
    )
    
    state = Paper2GraphState(request=request)
    state.enriched_description = enriched_description
    state.semantic_json = semantic_json
    state.layout_plan = layout_plan
    state.node_layout_plan = node_layout_plan
    state.layout_json = layout_json
    
    print("\n" + "=" * 60)
    print("Running p2g_node_render_design_agent ...")
    print("=" * 60)
    
    # 执行 agent（串行模式，便于调试）
    state = await p2g_node_render_design_agent(
        state,
        model_name="gpt-4o",
        temperature=0.0,
        max_tokens=4096,
        parser_type="json",
        parallel=False,  # 串行执行便于调试
    )
    
    # 获取结果
    node_render_design = getattr(state, "node_render_design", {})
    
    print("\n" + "=" * 60)
    print("Results:")
    print("=" * 60)
    
    if node_render_design:
        chunks = node_render_design.get("chunks", [])
        global_style = node_render_design.get("global_style", {})
        
        print(f"\nTotal chunks processed: {len(chunks)}")
        print(f"Global style: {json.dumps(global_style, indent=2)}")
        
        for chunk in chunks:
            chunk_id = chunk.get("chunk_id", "unknown")
            nodes = chunk.get("nodes", [])
            style_hints = chunk.get("chunk_style_hints", {})
            
            print(f"\n--- Chunk: {chunk_id} ---")
            print(f"  Nodes: {len(nodes)}")
            print(f"  Style hints: {style_hints}")
            
            for node in nodes:
                node_id = node.get("node_id", "?")
                render_method = node.get("render_method", "?")
                reasoning = node.get("reasoning", "")[:80]
                
                print(f"    - {node_id}: {render_method}")
                if render_method == "pptx":
                    pptx_desc = node.get("pptx_desc", "")[:60]
                    print(f"      pptx_desc: {pptx_desc}...")
                elif render_method == "vlm":
                    vlm_prompt = node.get("vlm_prompt", "")[:60]
                    print(f"      vlm_prompt: {vlm_prompt}...")
                print(f"      reasoning: {reasoning}...")
        
        # 保存结果
        save_json(node_render_design, "node_render_design.json")
        
        # 统计
        total_nodes = sum(len(c.get("nodes", [])) for c in chunks)
        pptx_count = sum(
            1 for c in chunks 
            for n in c.get("nodes", []) 
            if n.get("render_method") == "pptx"
        )
        vlm_count = sum(
            1 for c in chunks 
            for n in c.get("nodes", []) 
            if n.get("render_method") == "vlm"
        )
        
        print(f"\n--- Summary ---")
        print(f"Total nodes: {total_nodes}")
        print(f"PPTX rendering: {pptx_count}")
        print(f"VLM rendering: {vlm_count}")
        
    else:
        print("No node_render_design result!")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)
    
    return node_render_design


async def test_single_chunk():
    """测试单个 chunk 的渲染设计（用于调试）"""
    
    print("=" * 60)
    print("Testing single chunk render design ...")
    print("=" * 60)
    
    # 加载数据
    enriched_description = load_json("enriched_description.json")
    semantic_json = load_json("semantic_json.json")
    node_layout_plan = load_json("node_layout_plan.json")
    
    if not semantic_json.get("chunks"):
        print("No chunks found in semantic_json!")
        return
    
    # 取第一个 chunk 测试
    first_chunk = semantic_json["chunks"][0]
    chunk_id = first_chunk.get("chunk_id", "c1")
    
    # 获取 semantic_desc
    semantic_desc = ""
    if isinstance(enriched_description, dict):
        semantic_desc = enriched_description.get("semantic_desc", "")
    
    # 获取该 chunk 的 nodes
    all_nodes = semantic_json.get("nodes", [])
    chunk_node_ids = set(first_chunk.get("node_ids", []))
    chunk_nodes = [n for n in all_nodes if n.get("node_id") in chunk_node_ids]
    
    # 从 node_layout_plan 获取 role 信息
    role_map = {}
    for cp in node_layout_plan.get("chunks", []):
        if cp.get("chunk_id") == chunk_id:
            for np in cp.get("nodes", []):
                role_map[np.get("node_id", "")] = np.get("role", "")
            break
    
    # 构建 nodes_info
    nodes_info = []
    for node in chunk_nodes:
        node_id = node.get("node_id", "")
        nodes_info.append({
            "node_id": node_id,
            "node_type": node.get("node_type", ""),
            "desc": node.get("desc", ""),
            "role": role_map.get(node_id, ""),
        })
    
    print(f"\nChunk: {chunk_id}")
    print(f"Summary: {first_chunk.get('summary', '')[:100]}...")
    print(f"Nodes: {len(nodes_info)}")
    for ni in nodes_info:
        print(f"  - {ni['node_id']}: {ni['node_type']} / {ni['role']}")
        print(f"    desc: {ni['desc'][:60]}...")
    
    # 构建 chunk context
    chunk_ctx = {
        "chunk_id": chunk_id,
        "chunk_summary": first_chunk.get("summary", ""),
        "nodes_info": nodes_info,
        "semantic_desc": semantic_desc,
    }
    
    # 构建 state
    request = Paper2GraphRequest(
        target="Test single chunk",
        model="gpt-4o",
    )
    state = Paper2GraphState(request=request)
    
    # 创建 agent 并执行
    agent = P2gNodeRenderDesignAgent.create(
        model_name="gpt-4o",
        temperature=0.0,
        max_tokens=4096,
        parser_type="json",
    )
    agent.set_chunk_ctx(chunk_ctx)
    
    print("\n" + "=" * 60)
    print("Executing agent ...")
    print("=" * 60)
    
    await agent.execute(state, use_agent=False)
    
    # 获取结果
    result = state.agent_results.get(agent.role_name, {})
    chunks_results = result.get("chunks", [])
    
    print("\n" + "=" * 60)
    print("Result:")
    print("=" * 60)
    print(json.dumps(chunks_results, ensure_ascii=False, indent=2))
    
    # 保存结果
    if chunks_results:
        save_json(chunks_results[0], f"single_chunk_{chunk_id}_render_design.json")
    
    return chunks_results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test p2g_node_render_design_agent")
    parser.add_argument(
        "--single", 
        action="store_true", 
        help="Test single chunk only (for debugging)"
    )
    args = parser.parse_args()
    
    if args.single:
        asyncio.run(test_single_chunk())
    else:
        asyncio.run(test_node_render_design())
