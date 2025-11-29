from __future__ import annotations

import asyncio
import os

# 避免导入 agentroles 包时自动导入全部 agent 造成外部依赖错误
os.environ.setdefault("DF_SKIP_AGENTROLE_AUTOINIT", "1")

from dataflow_agent.state import Paper2GraphState, Paper2GraphRequest
from dataflow_agent.agentroles.p2g_target_analyst_agent import p2g_target_analyst
from dataflow_agent.agentroles.p2g_semantic_constructor_agent import p2g_semantic_constructor_agent


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
        "chunks": (
            "有5个参数：\n"
            "(1) chunk_id: chunk的唯一id，命名规则为 c1,c2...,;\n"
            "(2) title: chunk的title名称，不存在时可置空;\n"
            "(3) title_bbox: chunk title的bbox, 通过参数x,y,w,h这4个参数控制，单位是px;\n"
            "(4) summary: 用于描述该chunk的内容和功能;\n"
            "(5) node_ids: 该chunk包含的node的id列表。"
        ),
        "nodes": (
            "有4个参数：\n"
            "(1) node_id: node 的唯一id，命名规则为 n1,n2...,;\n"
            "(2) node_type: node 的类型，取值只能来自于以下列举的类型：text_block/shape/image_placeholder/"
            "table_placeholder/annotation;\n"
            "(3) chunk_id: 当前 node 所属的 chunk 的 id;\n"
            "(4) desc: 详细描述该 node 的内容和功能。"
        ),
        "edges": (
            "有3个参数：\n"
            "(1) edge_id: edge 的唯一id，命名规则为 e1,e2...,;\n"
            "(2) from: 当前 edge 的起点对应的 node_id;\n"
            "(3) to: 当前 edge 的止点对应的 node_id。"
        ),
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



    state = Paper2GraphState()

    state.request = req
    state.request.target = (
        "论文提出的 Early Experience（早期经验）范式，是衔接模仿学习（IL）与强化学习（RL）的核心框架，模型图需突出‘数据构建 - 双方法训练’核心流程：1. 基础输入与数据构建：以专家数据集 D_expert = {(s_i, a_i)}（s_i 为专家状态，a_i 为对应专家动作）为起点，对每个 s_i，从初始 LLM 策略中采样 K 个非专家备选动作 {a_i^1, a_i^2, ..., a_i^K}；在环境中分别执行 a_i（得到未来状态 s_{i+1}）与各 a_i^j（得到未来状态 s_i^j），构建 rollout 三元组数据集 D_rollout = {(s_i, a_i^j, s_i^j)}，以未来状态作为无奖励监督信号。2. 双核心方法分支：① 隐式世界建模（IWM）：输入 D_rollout 中的 (s_i, a_i^j)，让 LLM 策略学习预测对应未来状态 s_i^j，转化为 LLM 的下 token 预测任务，通过负对数似然损失使策略内化环境动态；② 自我反思（SR）：对每个 s_i，对比 a_i 对应的 s_{i+1} 与 a_i^j 对应的 s_i^j，引导 LLM 生成‘专家动作更优’的自然语言解释 c_i^j，构建反思数据集 D_refl = {(s_i, a_i^j, c_i^j)}，联合 D_expert 训练策略，使模型同时预测 c_i^j 与专家动作 a_i。"
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
    # 1. target 解析为 enriched_description
    state = await p2g_target_analyst(state, model_name="gpt-4o", parser_type="json")
    # 2. 语义构建为 semantic_json
    state = await p2g_semantic_constructor_agent(state, model_name="gpt-4o", parser_type="json")
    return state


def test_target_to_semantic_json():
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

    # 简要输出，便于人工查看
    enriched = getattr(final_state, "enriched_description", "")
    print("enriched_description:\n", str(enriched)[:200])
    print("semantic_json summary:", {k: len(sj.get(k, []) or []) for k in ("chunks", "nodes", "edges")})


if __name__ == "__main__":
    # 允许直接 python 运行本脚本进行快速验证
    try:
        s = _make_state()
        fs = asyncio.run(_run_pipeline(s))
        print("enriched_description:\n", str(getattr(fs, "enriched_description", ""))[:500])
        sj = getattr(fs, "semantic_json", {}) if isinstance(fs, Paper2GraphState) else {}
        print("semantic_json summary:", {k: len(sj.get(k, []) or []) for k in ("chunks", "nodes", "edges")})
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise
