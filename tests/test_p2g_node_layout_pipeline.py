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
from dataflow_agent.agentroles.p2g_node_layout_planner_agent import plan_node_layout_for_all_chunks


def _make_state() -> Paper2GraphState:
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

    state = Paper2GraphState()
    state.request = req
    state.request.target = (
        "论文提出的 Early Experience（早期经验）范式，是衔接模仿学习（IL）与强化学习（RL）的核心框架，模型图需突出'数据构建 - 双方法训练'核心流程："
        "1. 基础输入与数据构建：以专家数据集 D_expert = {(s_i, a_i)}（s_i 为专家状态，a_i 为对应专家动作）为起点，"
        "对每个 s_i，从初始 LLM 策略中采样 K 个非专家备选动作 {a_i^1, ..., a_i^K}，并在环境中分别执行专家动作与非专家动作，"
        "得到未来状态 s_{i+1} 与 s_i^j，构建包含 (s_i, a_i^j, s_i^j) 的无奖励滚动数据集 D_rollout。"
        "2. 双方法训练阶段：基于同一个 D_rollout，分为两条并行分支：IWM（隐式世界建模）和 SR（自我反思）。"
        "IWM 分支中，模型通过预测 s_i^j（将未来状态预测转化为下一个 token 的语言建模任务）来内化环境动态；"
        "SR 分支中，模型对比 s_{i+1} 和 s_i^j，并生成解释 c_i^j（说明专家动作为何更优），形成反思数据集 D_refl，"
        "并与 D_expert 联合训练，使策略同时学会生成专家动作和解释。"
        "3. 策略更新与闭环：两条分支的训练信号共同更新策略参数，得到 π_EE，并可回流到数据构建阶段继续产生早期经验，形成闭环。"
    )
    return state


async def _run_pipeline() -> Paper2GraphState:
    state = _make_state()

    # 1) 目标解析
    state = await p2g_target_analyst(state, model_name="gpt-5.1", parser_type="json")

    # 2) 语义构建
    state = await p2g_semantic_constructor_agent(state, model_name="gpt-5.1", parser_type="json")

    # 3) 布局规划 (layout_plan)
    state = await p2g_chunk_layout_planner_agent(state, model_name="gemini-3-pro-preview", parser_type="json")

    # 4) 节点级布局规划 (node_layout_plan)
    state = await plan_node_layout_for_all_chunks(state, model_name="gemini-3-pro-preview", parser_type="json")

    return state


def test_p2g_node_layout_pipeline() -> None:
    """从 target_analyst -> semantic_constructor -> layout_planner -> node_layout_planner 的流水线测试。

    将中间结果写入 tests/.tmp 目录, 方便人工检查:
    - enriched_description.json
    - semantic_json.json
    - layout_plan.json
    - node_layout_plan.json
    """
    try:
        fs = asyncio.run(_run_pipeline())
        sj = getattr(fs, "semantic_json", {})
        lp = getattr(fs, "layout_plan", {})
        nlp = getattr(fs, "node_layout_plan", {})

        tmp_dir = os.path.join(os.path.dirname(__file__), '.tmp/node_layout')
        os.makedirs(tmp_dir, exist_ok=True)

        # enriched_description
        enriched_desc_path = os.path.join(tmp_dir, 'enriched_description.json')
        with open(enriched_desc_path, 'w', encoding='utf-8') as f:
            json.dump(getattr(fs, "enriched_description", {}), f, ensure_ascii=False, indent=2)

        # semantic_json
        semantic_json_path = os.path.join(tmp_dir, 'semantic_json.json')
        with open(semantic_json_path, 'w', encoding='utf-8') as f:
            json.dump(sj, f, ensure_ascii=False, indent=2)

        # layout_plan
        layout_plan_path = os.path.join(tmp_dir, 'layout_plan.json')
        with open(layout_plan_path, 'w', encoding='utf-8') as f:
            json.dump(lp, f, ensure_ascii=False, indent=2)

        # node_layout_plan
        node_layout_plan_path = os.path.join(tmp_dir, 'node_layout_plan.json')
        with open(node_layout_plan_path, 'w', encoding='utf-8') as f:
            json.dump(nlp, f, ensure_ascii=False, indent=2)

        print(f"Node layout plan generated under {tmp_dir}")
    except Exception:
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    test_p2g_node_layout_pipeline()
