import os
import sys
import types
from pathlib import Path
import pytest

# 保证优先加载当前仓库的 dataflow_agent，而非外部同名包
_repo_root = Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

"""为隔离导入副作用，注入必要外部依赖的最小桩。
包括：
- dataflow（作为包）及其子模块 cli_funcs.paths / utils.registry
"""
if "dataflow" not in sys.modules:
    dataflow_pkg = types.ModuleType("dataflow")
    dataflow_pkg.__path__ = []  # 标记为包
    sys.modules["dataflow"] = dataflow_pkg

if "dataflow.cli_funcs" not in sys.modules:
    sys.modules["dataflow.cli_funcs"] = types.ModuleType("dataflow.cli_funcs")

if "dataflow.cli_funcs.paths" not in sys.modules:
    paths_mod = types.ModuleType("dataflow.cli_funcs.paths")

    class DataFlowPath:  # 最小实现满足 state.py 调用
        @staticmethod
        def get_dataflow_dir():
            return _repo_root / "dataflow_agent"

        @staticmethod
        def get_dataflow_statics_dir():
            return _repo_root / "static"

    paths_mod.DataFlowPath = DataFlowPath
    sys.modules["dataflow.cli_funcs.paths"] = paths_mod

if "dataflow.utils" not in sys.modules:
    sys.modules["dataflow.utils"] = types.ModuleType("dataflow.utils")

if "dataflow.utils.registry" not in sys.modules:
    reg_mod = types.ModuleType("dataflow.utils.registry")
    # 最小占位对象，满足 from dataflow.utils.registry import OPERATOR_REGISTRY
    reg_mod.OPERATOR_REGISTRY = {}
    sys.modules["dataflow.utils.registry"] = reg_mod

from dataflow_agent.state import DFState

"""预加载 agentroles 包的父模块以及 base_agent 子模块，
以避免触发 agentroles/__init__.py 的“全量导入”。
"""
import importlib.util as _ilu

# 1) 先注册父包占位（标记为包）
if "dataflow_agent.agentroles" not in sys.modules:
    _pkg = types.ModuleType("dataflow_agent.agentroles")
    _pkg.__path__ = [str(_repo_root / "dataflow_agent" / "agentroles")]  # 作为包路径
    sys.modules["dataflow_agent.agentroles"] = _pkg

# 2) 预加载 base_agent 子模块（供 p2g_target_analyst_agent 引用）
_base_path = _repo_root / "dataflow_agent" / "agentroles" / "base_agent.py"
_base_spec = _ilu.spec_from_file_location("dataflow_agent.agentroles.base_agent", _base_path)
_base_mod = _ilu.module_from_spec(_base_spec)
assert _base_spec and _base_spec.loader
_base_spec.loader.exec_module(_base_mod)  # type: ignore
sys.modules["dataflow_agent.agentroles.base_agent"] = _base_mod

# 3) 按文件路径加载目标模块（模块名保持包风格，避免相对导入问题）
_mod_path = _repo_root / "dataflow_agent" / "agentroles" / "p2g_target_analyst_agent.py"
_spec = _ilu.spec_from_file_location("dataflow_agent.agentroles.p2g_target_analyst_agent", _mod_path)
_mod = _ilu.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)  # type: ignore
p2g_target_analyst = _mod.p2g_target_analyst


@pytest.mark.asyncio
async def test_p2g_target_analyst_real_llm():
    """使用真实 LLM 服务进行联调测试。

    需要环境变量：
    - DF_API_URL: OpenAI 兼容 /v1 服务地址
    - DF_API_KEY: API Key
    可选：
    - OPENAI_MODEL: 模型名称（默认 gpt-4o）
    """
    api_url = os.getenv("DF_API_URL")
    api_key = os.getenv("DF_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-5")

    if not api_url or not api_key:
        pytest.skip("缺少 DF_API_URL/DF_API_KEY，跳过真实LLM联调测试")

    state = DFState()
    state.request.language = "zh"
    state.request.target = "我想要绘制ResNet的架构图"
    state.request.chat_api_url = api_url
    state.request.api_key = api_key
    state.request.model = model

    final_state = await p2g_target_analyst(
        state,
        model_name=model,
        temperature=0.2,
        parser_type="text",
    )

    # 断言：仅输出单一字符串并写回 state.enriched_description
    assert hasattr(final_state, "enriched_description")
    assert isinstance(final_state.enriched_description, str)
    assert len(final_state.enriched_description.strip()) > 0

    # agent_results 同步记录应一致
    assert "p2g_target_analyst" in final_state.agent_results
    recorded = final_state.agent_results["p2g_target_analyst"]["results"]
    assert recorded == final_state.enriched_description


if __name__ == "__main__":
    # 允许通过 `python tests/test_p2g_target_analyst.py` 直接联调
    api_url = os.getenv("DF_API_URL")
    api_key = os.getenv("DF_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-5")
    if not api_url or not api_key:
        print("缺少 DF_API_URL/DF_API_KEY，跳过真实LLM联调。建议使用 pytest 运行。")
        sys.exit(0)

    async def _main():
        state = DFState()
        state.request.language = "zh"
        state.request.target = "论文提出的 Early Experience（早期经验）范式，是衔接模仿学习（IL）与强化学习（RL）的核心框架，模型图需突出‘数据构建 - 双方法训练’核心流程：1. 基础输入与数据构建：以专家数据集 D_expert = {(s_i, a_i)}（s_i 为专家状态，a_i 为对应专家动作）为起点，对每个 s_i，从初始 LLM 策略中采样 K 个非专家备选动作 {a_i^1, a_i^2, ..., a_i^K}；在环境中分别执行 a_i（得到未来状态 s_{i+1}）与各 a_i^j（得到未来状态 s_i^j），构建 rollout 三元组数据集 D_rollout = {(s_i, a_i^j, s_i^j)}，以未来状态作为无奖励监督信号。2. 双核心方法分支：① 隐式世界建模（IWM）：输入 D_rollout 中的 (s_i, a_i^j)，让 LLM 策略学习预测对应未来状态 s_i^j，转化为 LLM 的下 token 预测任务，通过负对数似然损失使策略内化环境动态；② 自我反思（SR）：对每个 s_i，对比 a_i 对应的 s_{i+1} 与 a_i^j 对应的 s_i^j，引导 LLM 生成‘专家动作更优’的自然语言解释 c_i^j，构建反思数据集 D_refl = {(s_i, a_i^j, c_i^j)}，联合 D_expert 训练策略，使模型同时预测 c_i^j 与专家动作 a_i。"
        state.request.chat_api_url = api_url
        state.request.api_key = api_key
        state.request.model = model
        # 跳过 agentroles 包的全量自动导入
        os.environ["DF_SKIP_AGENTROLE_AUTOINIT"] = "1"
        final_state = await p2g_target_analyst(state, model_name=model, temperature=0.2, parser_type="text")
        print("==== enriched_description ====")
        print(final_state.enriched_description)

    import asyncio

    asyncio.run(_main())
