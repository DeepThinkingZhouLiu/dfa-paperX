"""测试 6 步完整流水线：target → semantic → chunk_layout → node_layout → layout_constructor → node_render_design

在 test_p2g_layout_pipeline.py 基础上添加 p2g_node_render_design_agent 节点。
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
from dataflow_agent.agentroles.p2g_layout_chunk_planner_agent import p2g_layout_chunk_planner_agent
from dataflow_agent.agentroles.p2g_node_layout_planner_agent import p2g_node_layout_planner_agent as plan_node_layout_for_all_chunks
from dataflow_agent.agentroles.p2g_layout_constructor_agent import p2g_layout_constructor_agent
from dataflow_agent.agentroles.p2g_node_render_design_agent import p2g_node_render_design_agent


def _make_state() -> Paper2GraphState:
    req = Paper2GraphRequest()
    # 提供 design_docs/workflow_design.md 中的 semantic_json_schema/desc 作为约束
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

    req.layout_json_schema = {
        "positions": {
            "chunks": [
                {"chunk_id": "c1", "bbox": {"x": 96, "y": 36,  "w": 728, "h": 972}}
            ],
            "nodes": [
                {"node_id": "n1", "bbox": {"x": 672,  "y": 54,  "w": 576, "h": 86}},
                {"node_id": "n2", "bbox": {"x": 192,  "y": 324, "w": 384, "h": 129}},
            ]
        }
    }

    req.layout_json_desc = {
        "positions": """有 2 个参数：
(1) chunks: 格式为 {chunk_id, bbox}, 其中 chunk_id 为当前 chunk 的 id, bbox 为当前 chunk 的边界框范围, 由 x,y,w 和 h 这四个参数控制, (x, y) 表示矩形边界框左上角顶点坐标, w 和 h 分别表示矩形边界框框的宽度与高度; 
(2) nodes: 格式为 {node_id, bbox}, 其中 node_id 为当前 node 的 id, bbox 为当前 node 的边界框范围, 由 x,y,w 和 h 这四个参数控制, (x, y) 表示矩形边界框左上角顶点坐标, w 和 h 分别表示矩形边界框框的宽度与高度; """
    }

    req.design_json_schema = {
        "global_theme": "NeurIPS-style clean diagram with light background and minimal colors.",
        "node_render": {
            "n1": {"render_method": "pptx"},
            "n2": {"render_method": "vlm", "vlm_prompt": "Icon of raw dataset or CSV file."},
            "n3": {"render_method": "vlm", "vlm_prompt": "Neural network block representing encoder."},
            "n4": {"render_method": "vlm", "vlm_prompt": "Output predictions icon."},
            "n5": {"render_method": "pptx"}
        }
    }

    req.design_json_desc = {
        "global_theme": "用于描述图像的全局风格特征，例如学术论文风格，卡通风格等。默认取值为学术论文模型图风格",
        "node_render": """格式为: node_id: {render_method, vlm_prompt?}, 每个 node_id 中含有 2 个参数：
(1) render_method: 该 node 的渲染方式，有且仅有两种取值: pptx 和 vlm, pptx 表示下游直接使用 pptx 进行渲染，例如文本框、ppt中常见形状等；vlm 表示下游通过调用 vlm 生图模型来绘制该 node；
(2) vlm_prompt: 当且仅当 render_method 为 vlm 时需要写入该字段，用于下游调用 vlm 生成当前节点内容的 prompt 。""",
    }
    
    # 设置 header_json_desc
    req.header_json_desc = {
        "version": "0.5",
        "canvas": {"width": 1920, "height": 1080, "unit": "px"},
        "layout_flow": "left-to-right"
    }

    state = Paper2GraphState()

    state.request = req
    state.request.target = (
        "论文提出的 Early Experience（早期经验）范式，是衔接模仿学习（IL）与强化学习（RL）的核心框架，模型图需突出'数据构建 - 双方法训练'核心流程：1. 基础输入与数据构建：以专家数据集 D_expert = {(s_i, a_i)}（s_i 为专家状态，a_i 为对应专家动作）为起点，对每个 s_i，从初始 LLM 策略中采样 K 个非专家备选动作 {a_i^1, a_i^2, ..., a_i^K}；在环境中分别执行 a_i（得到未来状态 s_{i+1}）与各 a_i^j（得到未来状态 s_i^j），构建 rollout 三元组数据集 D_rollout = {(s_i, a_i^j, s_i^j)}，以未来状态作为无奖励监督信号。2. 双核心方法分支：① 隐式世界建模（IWM）：输入 D_rollout 中的 (s_i, a_i^j)，让 LLM 策略学习预测对应未来状态 s_i^j，转化为 LLM 的下 token 预测任务，通过负对数似然损失使策略内化环境动态；② 自我反思（SR）：对每个 s_i，对比 a_i 对应的 s_{i+1} 与 a_i^j 对应的 s_i^j，引导 LLM 生成'专家动作更优'的自然语言解释 c_i^j，构建反思数据集 D_refl = {(s_i, a_i^j, c_i^j)}，联合 D_expert 训练策略，使模型同时预测 c_i^j 与专家动作 a_i。"
    )

    # 指定必要的 API 配置：读取环境变量 DF_API_URL / DF_API_KEY
    api_url = os.getenv("DF_API_URL", "http://123.129.219.111:3000/v1")
    api_key = os.getenv("DF_API_KEY")
    # 恢复原来的API密钥检查
    assert api_key, "请先 export DF_API_KEY 环境变量后再运行测试"
    state.request.chat_api_url = api_url
    state.request.api_key = api_key
    state.request.language = "zh"
    return state


async def _run_pipeline(state: Paper2GraphState) -> Paper2GraphState:
    """完整的6步流水线：target -> semantic -> chunk_layout -> node_layout -> layout_constructor -> node_render_design

    流程说明：
    1. p2g_target_analyst: 目标解析，生成 enriched_description
    2. p2g_semantic_constructor_agent: 语义构建，生成 semantic_json
    3. p2g_layout_chunk_planner_agent: chunk级布局规划，生成 layout_plan
    4. p2g_node_layout_planner_agent: 节点级布局规划，生成 node_layout_plan
    5. p2g_layout_constructor_agent: 布局构建，生成最终的 layout_json（包含 bbox 坐标）
    6. p2g_node_render_design_agent: 节点渲染设计，生成 node_render_design
    """
    # 1. target 解析为 enriched_description
    state = await p2g_target_analyst(state, model_name="gpt-5.1", parser_type="json")
    
    # 2. 在进入语义构建前, 直接覆盖写回 schema/desc, 确保参数完整
    from dataflow_agent.state import Paper2GraphRequest

    # 若当前没有 request, 补一个; 若已有, 只负责写入 schema/desc
    if getattr(state, "request", None) is None:
        state.request = Paper2GraphRequest()

    # 这里直接使用测试中约定的 schema/desc, 保证与 _make_state 保持一致
    state.request.semantic_json_schema = {
        "chunks": [
            {
                "chunk_id": "c1",
                "title": "Training Pipeline",
                "title_bbox": {"left": 672, "top": 54, "width": 576, "height": 86},
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
    
    # 3. 语义构建为 semantic_json
    state = await p2g_semantic_constructor_agent(state, model_name="gpt-5.1", parser_type="json")
    
    # 4. chunk级布局规划为 layout_plan
    state = await p2g_layout_chunk_planner_agent(state, model_name="gemini-3-pro-preview", parser_type="json")
    
    # 5. 节点级布局规划为 node_layout_plan
    state = await plan_node_layout_for_all_chunks(state, model_name="gemini-3-pro-preview", parser_type="json")
    
    # 6. 布局构建为最终的 layout_json（包含完整 bbox 坐标）
    state = await p2g_layout_constructor_agent(state, model_name="gpt-5.1", parser_type="json")
    
    # 7. 节点渲染设计，生成 node_render_design
    state = await p2g_node_render_design_agent(
        state, 
        model_name="gpt-4o", 
        parser_type="json",
        parallel=False,  # 串行执行便于调试
    )
    
    return state


def test_target_to_node_render_design():
    """完整的6步流水线测试：target -> semantic -> chunk_layout -> node_layout -> layout_constructor -> node_render_design

    将中间结果写入 tests/.tmp/render_design_pipeline 目录, 方便人工检查:
    - enriched_description.json
    - semantic_json.json
    - layout_plan.json
    - node_layout_plan.json
    - layout_json.json
    - node_render_design.json
    """
    state = _make_state()
    try:
        final_state = asyncio.run(_run_pipeline(state))
    except Exception as e:
        # 打印错误以便诊断
        print("Pipeline error:", e)
        assert False, f"pipeline failed: {e}"

    # 断言 enriched_description 非空
    assert getattr(final_state, "enriched_description", None), "enriched_description should not be empty"

    # 断言 semantic_json 已写入
    sj = getattr(final_state, "semantic_json", {})
    assert isinstance(sj, dict), "semantic_json should be a dict"

    # 基本结构断言: 至少包含 chunks/nodes/edges
    for key in ("chunks", "nodes", "edges"):
        assert key in sj, f"semantic_json missing key: {key}"

    # 断言 layout_plan 已写入
    lp = getattr(final_state, "layout_plan", {})
    assert isinstance(lp, dict), "layout_plan should be a dict"
    assert lp, "layout_plan should not be empty"

    # 断言 node_layout_plan 已写入
    nlp = getattr(final_state, "node_layout_plan", {})
    assert isinstance(nlp, dict), "node_layout_plan should be a dict"
    assert nlp, "node_layout_plan should not be empty"

    # 断言 layout_json 已写入
    lj = getattr(final_state, "layout_json", {})
    assert isinstance(lj, dict), "layout_json should be a dict"

    # 基本结构断言: 至少包含 positions
    assert "positions" in lj, "layout_json missing key: positions"
    
    # positions 应该包含 chunks, nodes
    positions = lj["positions"]
    for key in ("chunks", "nodes"):
        assert key in positions, f"layout_json.positions missing key: {key}"

    # 断言 node_render_design 已写入
    nrd = getattr(final_state, "node_render_design", {})
    assert isinstance(nrd, dict), "node_render_design should be a dict"
    
    # node_render_design 结构断言
    assert "chunks" in nrd, "node_render_design missing key: chunks"
    assert "global_style" in nrd, "node_render_design missing key: global_style"
    
    # 验证每个 chunk 的 nodes 渲染设计
    nrd_chunks = nrd.get("chunks", [])
    assert len(nrd_chunks) > 0, "node_render_design.chunks should not be empty"
    
    for chunk in nrd_chunks:
        assert "chunk_id" in chunk, "chunk missing chunk_id"
        assert "nodes" in chunk, "chunk missing nodes"
        
        for node in chunk.get("nodes", []):
            assert "node_id" in node, "node missing node_id"
            assert "render_method" in node, "node missing render_method"
            assert node["render_method"] in ("pptx", "vlm"), f"invalid render_method: {node['render_method']}"
            
            # 如果是 vlm 渲染，应该有 vlm_prompt
            if node["render_method"] == "vlm":
                assert "vlm_prompt" in node, f"vlm node {node['node_id']} missing vlm_prompt"

    # 保存生成的内容到 .tmp/render_design_pipeline 路径下
    tmp_dir = os.path.join(os.path.dirname(__file__), '.tmp/render_design_pipeline')
    os.makedirs(tmp_dir, exist_ok=True)
    
    # 保存 enriched_description
    enriched_desc_path = os.path.join(tmp_dir, 'enriched_description.json')
    with open(enriched_desc_path, 'w', encoding='utf-8') as f:
        json.dump(getattr(final_state, "enriched_description", {}), f, ensure_ascii=False, indent=2)
    
    # 保存 semantic_json
    semantic_json_path = os.path.join(tmp_dir, 'semantic_json.json')
    with open(semantic_json_path, 'w', encoding='utf-8') as f:
        json.dump(sj, f, ensure_ascii=False, indent=2)
    
    # 保存 layout_plan
    layout_plan_path = os.path.join(tmp_dir, 'layout_plan.json')
    with open(layout_plan_path, 'w', encoding='utf-8') as f:
        json.dump(lp, f, ensure_ascii=False, indent=2)
    
    # 保存 node_layout_plan
    node_layout_plan_path = os.path.join(tmp_dir, 'node_layout_plan.json')
    with open(node_layout_plan_path, 'w', encoding='utf-8') as f:
        json.dump(nlp, f, ensure_ascii=False, indent=2)
    
    # 保存 layout_json
    layout_json_path = os.path.join(tmp_dir, 'layout_json.json')
    with open(layout_json_path, 'w', encoding='utf-8') as f:
        json.dump(lj, f, ensure_ascii=False, indent=2)
    
    # 保存 node_render_design
    node_render_design_path = os.path.join(tmp_dir, 'node_render_design.json')
    with open(node_render_design_path, 'w', encoding='utf-8') as f:
        json.dump(nrd, f, ensure_ascii=False, indent=2)

    # 简要输出，便于人工查看
    enriched = getattr(final_state, "enriched_description", "")
    print("enriched_description:\n", str(enriched)[:200])
    print("semantic_json summary:", {k: len(sj.get(k, []) or []) for k in ("chunks", "nodes", "edges")})
    print("layout_plan:", lp)
    print("node_layout_plan chunks:", list(nlp.keys()) if isinstance(nlp, dict) else "N/A")
    print("layout_json summary:", {k: len(positions.get(k, []) or []) for k in ("chunks", "nodes")})
    
    # node_render_design 统计
    total_nodes = sum(len(c.get("nodes", [])) for c in nrd_chunks)
    pptx_count = sum(
        1 for c in nrd_chunks 
        for n in c.get("nodes", []) 
        if n.get("render_method") == "pptx"
    )
    vlm_count = sum(
        1 for c in nrd_chunks 
        for n in c.get("nodes", []) 
        if n.get("render_method") == "vlm"
    )
    print(f"node_render_design summary: {len(nrd_chunks)} chunks, {total_nodes} nodes (pptx: {pptx_count}, vlm: {vlm_count})")
    print(f"Generated files saved to {tmp_dir}")


if __name__ == "__main__":
    # 允许直接 python 运行本脚本进行快速验证
    try:
        s = _make_state()
        fs = asyncio.run(_run_pipeline(s))
        
        # 提取各阶段结果
        sj = getattr(fs, "semantic_json", {}) if isinstance(fs, Paper2GraphState) else {}
        lp = getattr(fs, "layout_plan", {}) if isinstance(fs, Paper2GraphState) else {}
        nlp = getattr(fs, "node_layout_plan", {}) if isinstance(fs, Paper2GraphState) else {}
        lj = getattr(fs, "layout_json", {}) if isinstance(fs, Paper2GraphState) else {}
        nrd = getattr(fs, "node_render_design", {}) if isinstance(fs, Paper2GraphState) else {}
        positions = lj.get("positions", {}) if isinstance(lj, dict) else {}
        
        # 打印摘要
        print("=" * 60)
        print("6步流水线执行完成")
        print("=" * 60)
        print("enriched_description:\n", str(getattr(fs, "enriched_description", ""))[:500])
        print("-" * 60)
        print("semantic_json summary:", {k: len(sj.get(k, []) or []) for k in ("chunks", "nodes", "edges")})
        print("-" * 60)
        print("layout_plan:", lp)
        print("-" * 60)
        print("node_layout_plan chunks:", list(nlp.keys()) if isinstance(nlp, dict) else "N/A")
        print("-" * 60)
        print("layout_json summary:", {k: len(positions.get(k, []) or []) for k in ("chunks", "nodes")})
        print("-" * 60)
        
        # node_render_design 详细输出
        nrd_chunks = nrd.get("chunks", [])
        total_nodes = sum(len(c.get("nodes", [])) for c in nrd_chunks)
        pptx_count = sum(
            1 for c in nrd_chunks 
            for n in c.get("nodes", []) 
            if n.get("render_method") == "pptx"
        )
        vlm_count = sum(
            1 for c in nrd_chunks 
            for n in c.get("nodes", []) 
            if n.get("render_method") == "vlm"
        )
        print(f"node_render_design summary: {len(nrd_chunks)} chunks, {total_nodes} nodes")
        print(f"  - pptx rendering: {pptx_count}")
        print(f"  - vlm rendering: {vlm_count}")
        print(f"  - global_style: {nrd.get('global_style', {})}")
        
        # 保存生成的内容到 .tmp/render_design_pipeline 路径下
        tmp_dir = os.path.join(os.path.dirname(__file__), '.tmp/render_design_pipeline')
        os.makedirs(tmp_dir, exist_ok=True)
        
        # 保存 enriched_description
        enriched_desc_path = os.path.join(tmp_dir, 'enriched_description.json')
        with open(enriched_desc_path, 'w', encoding='utf-8') as f:
            json.dump(getattr(fs, "enriched_description", {}), f, ensure_ascii=False, indent=2)
        
        # 保存 semantic_json
        semantic_json_path = os.path.join(tmp_dir, 'semantic_json.json')
        with open(semantic_json_path, 'w', encoding='utf-8') as f:
            json.dump(sj, f, ensure_ascii=False, indent=2)
        
        # 保存 layout_plan
        layout_plan_path = os.path.join(tmp_dir, 'layout_plan.json')
        with open(layout_plan_path, 'w', encoding='utf-8') as f:
            json.dump(lp, f, ensure_ascii=False, indent=2)
        
        # 保存 node_layout_plan
        node_layout_plan_path = os.path.join(tmp_dir, 'node_layout_plan.json')
        with open(node_layout_plan_path, 'w', encoding='utf-8') as f:
            json.dump(nlp, f, ensure_ascii=False, indent=2)
        
        # 保存 layout_json
        layout_json_path = os.path.join(tmp_dir, 'layout_json.json')
        with open(layout_json_path, 'w', encoding='utf-8') as f:
            json.dump(lj, f, ensure_ascii=False, indent=2)
        
        # 保存 node_render_design
        node_render_design_path = os.path.join(tmp_dir, 'node_render_design.json')
        with open(node_render_design_path, 'w', encoding='utf-8') as f:
            json.dump(nrd, f, ensure_ascii=False, indent=2)
        
        print("=" * 60)
        print(f"Generated files saved to {tmp_dir}")
        print("  - enriched_description.json")
        print("  - semantic_json.json")
        print("  - layout_plan.json")
        print("  - node_layout_plan.json")
        print("  - layout_json.json")
        print("  - node_render_design.json")
    except Exception as e:
        import traceback
        traceback.print_exc()
