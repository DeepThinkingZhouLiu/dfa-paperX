"""
测试 p2g_layout_constructor_agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
验证完整流水线：target_analyst -> semantic_constructor -> layout_planner -> layout_constructor
"""

from __future__ import annotations

import asyncio
import os
import json

# 避免导入 agentroles 包时自动导入全部 agent 造成外部依赖错误
os.environ.setdefault("DF_SKIP_AGENTROLE_AUTOINIT", "1")

# 修复导入路径问题
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dataflow_agent.state import Paper2GraphState, Paper2GraphRequest
from dataflow_agent.agentroles.p2g_target_analyst_agent import p2g_target_analyst
from dataflow_agent.agentroles.p2g_semantic_constructor_agent import p2g_semantic_constructor_agent
from dataflow_agent.agentroles.p2g_chunk_layout_planner_agent import p2g_chunk_layout_planner_agent
from dataflow_agent.agentroles.p2g_layout_constructor_agent import p2g_layout_constructor_agent


def _make_state() -> Paper2GraphState:
    """构造测试用的 Paper2GraphState"""
    req = Paper2GraphRequest()
    
    # 提供 semantic_json_schema/desc 作为约束
    req.semantic_json_schema = {
        "chunks": [
            {
                "chunk_id": "c1",
                "title": "Training Pipeline",
                "title_bbox": {"x": 672, "y": 54, "w": 576, "h": 86},
                "summary": "Overall training pipeline for the proposed model.",
                "node_ids": ["n1", "n2", "n3", "n4", "n5"],
            }
        ],
        "nodes": [
            {"node_id": "n1", "node_type": "text_block", "chunk_id": "c1", "desc": "Training Pipeline"},
            {"node_id": "n2", "node_type": "shape", "chunk_id": "c1", "desc": "Raw Data"},
            {"node_id": "n3", "node_type": "shape", "chunk_id": "c1", "desc": "Encoder"},
            {"node_id": "n4", "node_type": "shape", "chunk_id": "c1", "desc": "Predictions"},
            {"node_id": "n5", "node_type": "annotation", "chunk_id": "c1", "desc": "We freeze encoder weights."},
        ],
        "edges": [
            {"edge_id": "e1", "from": "n2", "to": "n3"},
            {"edge_id": "e2", "from": "n3", "to": "n4"},
        ],
    }
    req.semantic_json_desc = {
        "chunks": """有5个参数：
(1) chunk_id: chunk的唯一id，命名规则为 c1,c2...,;
(2) title: chunk的title名称，不存在时可置空;
(3) title_bbox: chunk title的bbox, 通过参数x,y,w,h这4个参数控制，单位是px;
(4) summary: 用于描述该chunk的内容和功能;
(5) node_ids: 该chunk包含的node的id列表。""",
        "nodes": """有4个参数：
(1) node_id: node 的唯一id，命名规则为 n1,n2...,;
(2) node_type: node 的类型，取值只能来自于以下列举的类型：text_block/shape/image_placeholder/table_placeholder/annotation;
(3) chunk_id: 当前 node 所属的 chunk 的 id;
(4) desc: 详细描述该 node 的内容和功能。""",
        "edges": """有3个参数：
(1) edge_id: edge 的唯一id，命名规则为 e1,e2...,;
(2) from: 当前 edge 的起点对应的 node_id;
(3) to: 当前 edge 的止点对应的 node_id。"""
    }
    
    # 提供 layout_json_schema（包含画布尺寸）
    req.layout_json_schema = {
        "canvas": {"width": 1920, "height": 1080, "unit": "px"}
    }

    state = Paper2GraphState()
    state.request = req
    state.request.target = (
        "论文提出的 Early Experience（早期经验）范式，是衔接模仿学习（IL）与强化学习（RL）的核心框架，模型图需突出'数据构建 - 双方法训练'核心流程："
        "1. 基础输入与数据构建：以专家数据集 D_expert = {(s_i, a_i)}（s_i 为专家状态，a_i 为对应专家动作）为起点，"
        "对每个 s_i，从初始 LLM 策略中采样 K 个非专家备选动作 {a_i^1, a_i^2, ..., a_i^K}；"
        "在环境中分别执行 a_i（得到未来状态 s_{i+1}）与各 a_i^j（得到未来状态 s_i^j），"
        "构建 rollout 三元组数据集 D_rollout = {(s_i, a_i^j, s_i^j)}，以未来状态作为无奖励监督信号。"
        "2. 双核心方法分支：① 隐式世界建模（IWM）：输入 D_rollout 中的 (s_i, a_i^j)，"
        "让 LLM 策略学习预测对应未来状态 s_i^j，转化为 LLM 的下 token 预测任务，"
        "通过负对数似然损失使策略内化环境动态；② 自我反思（SR）：对每个 s_i，"
        "对比 a_i 对应的 s_{i+1} 与 a_i^j 对应的 s_i^j，"
        "引导 LLM 生成'专家动作更优'的自然语言解释 c_i^j，构建反思数据集 D_refl = {(s_i, a_i^j, c_i^j)}，"
        "联合 D_expert 训练策略，使模型同时预测 c_i^j 与专家动作 a_i。"
    )

    # 指定必要的 API 配置：读取环境变量 DF_API_URL / DF_API_KEY
    api_url = os.getenv("DF_API_URL", "http://123.129.219.111:3000/v1")
    api_key = os.getenv("DF_API_KEY")
    assert api_key, "请先 export DF_API_KEY 环境变量后再运行测试"
    state.request.chat_api_url = api_url
    state.request.api_key = api_key
    state.request.language = "zh"
    return state


async def _run_pipeline(state: Paper2GraphState) -> Paper2GraphState:
    """运行完整流水线: target_analyst -> semantic_constructor -> layout_planner -> layout_constructor
    
    流程：
    1. target_analyst: 生成 enriched_description (semantic_desc + layout_desc)
    2. semantic_constructor: 生成 semantic_json (chunks/nodes/edges)
    3. layout_planner: 生成 layout_plan (grid 级别规划)
    4. layout_constructor: 生成 layout_json (bbox 级别布局) ⭐ NEW
    """
    # Step 1: target 解析为 enriched_description
    print("=" * 60)
    print("Step 1: 运行 p2g_target_analyst...")
    print("=" * 60)
    state = await p2g_target_analyst(state, model_name="gpt-5", parser_type="json")
    
    enriched = getattr(state, "enriched_description", {})
    print(f"✅ enriched_description 已生成")
    print(f"   - semantic_desc 长度: {len(enriched.get('semantic_desc', ''))} 字符")
    print(f"   - layout_desc 长度: {len(enriched.get('layout_desc', ''))} 字符")
    
    # Step 2: 确保 schema/desc 参数完整
    from dataflow_agent.state import Paper2GraphRequest
    if getattr(state, "request", None) is None:
        state.request = Paper2GraphRequest()

    state.request.semantic_json_schema = {
        "chunks": [
            {
                "chunk_id": "c1",
                "title": "Training Pipeline",
                "title_bbox": {"x": 672, "y": 54, "w": 576, "h": 86},
                "summary": "Overall training pipeline for the proposed model.",
                "node_ids": ["n1", "n2", "n3", "n4", "n5"],
            }
        ],
        "nodes": [
            {"node_id": "n1", "node_type": "text_block", "chunk_id": "c1", "desc": "Training Pipeline"},
            {"node_id": "n2", "node_type": "shape", "chunk_id": "c1", "desc": "Raw Data"},
            {"node_id": "n3", "node_type": "shape", "chunk_id": "c1", "desc": "Encoder"},
            {"node_id": "n4", "node_type": "shape", "chunk_id": "c1", "desc": "Predictions"},
            {"node_id": "n5", "node_type": "annotation", "chunk_id": "c1", "desc": "We freeze encoder weights."},
        ],
        "edges": [
            {"edge_id": "e1", "from": "n2", "to": "n3"},
            {"edge_id": "e2", "from": "n3", "to": "n4"},
        ],
    }
    state.request.semantic_json_desc = {
        "chunks": """有5个参数：
(1) chunk_id: chunk的唯一id，命名规则为 c1,c2...,;
(2) title: chunk的title名称，不存在时可置空;
(3) title_bbox: chunk title的bbox, 通过参数x,y,w,h这4个参数控制，单位是px;
(4) summary: 用于描述该chunk的内容和功能;
(5) node_ids: 该chunk包含的node的id列表。""",
        "nodes": """有4个参数：
(1) node_id: node 的唯一id，命名规则为 n1,n2...,;
(2) node_type: node 的类型，取值只能来自于以下列举的类型：text_block/shape/image_placeholder/table_placeholder/annotation;
(3) chunk_id: 当前 node 所属的 chunk 的 id;
(4) desc: 详细描述该 node 的内容和功能。""",
        "edges": """有3个参数：
(1) edge_id: edge 的唯一id，命名规则为 e1,e2...,;
(2) from: 当前 edge 的起点对应的 node_id;
(3) to: 当前 edge 的止点对应的 node_id。"""
    }

    # Step 2: 语义构建为 semantic_json
    print("\n" + "=" * 60)
    print("Step 2: 运行 p2g_semantic_constructor_agent...")
    print("=" * 60)
    state = await p2g_semantic_constructor_agent(state, model_name="gpt-5", parser_type="json")
    
    sj = getattr(state, "semantic_json", {})
    print(f"✅ semantic_json 已生成")
    print(f"   - chunks: {len(sj.get('chunks', []))} 个")
    print(f"   - nodes: {len(sj.get('nodes', []))} 个")
    print(f"   - edges: {len(sj.get('edges', []))} 个")
    
    # Step 3: 布局规划为 layout_plan
    print("\n" + "=" * 60)
    print("Step 3: 运行 p2g_chunk_layout_planner_agent...")
    print("=" * 60)
    state = await p2g_chunk_layout_planner_agent(state, model_name="gpt-5", parser_type="json")
    
    lp = getattr(state, "layout_plan", {})
    print(f"✅ layout_plan 已生成")
    if "global" in lp:
        global_info = lp["global"]
        print(f"   - Grid 规模: {global_info.get('grid_rows')}x{global_info.get('grid_cols')}")
        print(f"   - Flow 方向: {global_info.get('flow_direction')}")
    print(f"   - Chunks 规划: {len(lp.get('chunks', []))} 个")
    
    # Step 4: 布局构造为 layout_json (NEW!)
    print("\n" + "=" * 60)
    print("Step 4: 运行 p2g_layout_constructor_agent (NEW)...")
    print("=" * 60)
    state = await p2g_layout_constructor_agent(state, model_name="gpt-5", parser_type="json")
    
    lj = getattr(state, "layout_json", {})
    print(f"✅ layout_json 已生成")
    print(f"   - 版本: {lj.get('version')}")
    print(f"   - 画布: {lj.get('canvas', {}).get('width')}x{lj.get('canvas', {}).get('height')}")
    print(f"   - Flow: {lj.get('layout_flow')}")
    positions = lj.get("positions", {})
    print(f"   - Chunks bbox: {len(positions.get('chunks', []))} 个")
    print(f"   - Nodes bbox: {len(positions.get('nodes', []))} 个")
    
    return state


def test_full_p2g_pipeline():
    """测试完整 P2G 流水线"""
    state = _make_state()
    try:
        final_state = asyncio.run(_run_pipeline(state))
    except Exception as e:
        print("Pipeline error:", e)
        import traceback
        traceback.print_exc()
        assert False, f"pipeline failed: {e}"

    # 断言各阶段输出
    assert getattr(final_state, "enriched_description", None), "enriched_description should not be empty"
    assert getattr(final_state, "semantic_json", None), "semantic_json should not be empty"
    assert getattr(final_state, "layout_plan", None), "layout_plan should not be empty"
    assert getattr(final_state, "layout_json", None), "layout_json should not be empty"
    
    # 断言 layout_json 结构
    lj = getattr(final_state, "layout_json", {})
    assert "canvas" in lj, "layout_json should contain 'canvas'"
    assert "positions" in lj, "layout_json should contain 'positions'"
    
    positions = lj["positions"]
    assert "chunks" in positions, "positions should contain 'chunks'"
    assert "nodes" in positions, "positions should contain 'nodes'"
    
    # 检查 bbox 完整性
    for chunk_pos in positions["chunks"]:
        assert "chunk_id" in chunk_pos, "each chunk position should have 'chunk_id'"
        assert "bbox" in chunk_pos, "each chunk position should have 'bbox'"
        bbox = chunk_pos["bbox"]
        assert all(k in bbox for k in ["x", "y", "w", "h"]), "bbox should have x,y,w,h"
    
    for node_pos in positions["nodes"]:
        assert "node_id" in node_pos, "each node position should have 'node_id'"
        assert "bbox" in node_pos, "each node position should have 'bbox'"
        bbox = node_pos["bbox"]
        assert all(k in bbox for k in ["x", "y", "w", "h"]), "bbox should have x,y,w,h"
    
    print("\n" + "=" * 60)
    print("✅ 完整流水线测试通过！")
    print("=" * 60)
    
    # 输出 layout_json 详情
    print("\nlayout_json 详细内容:")
    print(json.dumps(lj, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        print("开始测试 P2G 完整流水线（含 layout_constructor）\n")
        s = _make_state()
        fs = asyncio.run(_run_pipeline(s))
        
        print("\n" + "=" * 60)
        print("✅ 流水线执行成功！")
        print("=" * 60)
        
        # 保存 layout_json 到文件（可选）
        lj = getattr(fs, "layout_json", {})
        output_path = os.path.join(os.path.dirname(__file__), ".tmp", "layout_json_output.json")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(lj, f, ensure_ascii=False, indent=2)
        print(f"\nlayout_json 已保存到: {output_path}")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise
