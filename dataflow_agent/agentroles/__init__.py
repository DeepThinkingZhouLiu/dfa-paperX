# dataflow_agent/agentroles/__init__.py
import importlib
import os
from pathlib import Path

# 1) 自动 import 所有 .py 文件
_pkg_path = Path(__file__).resolve().parent
# 允许通过环境变量跳过自动导入，避免测试或特定场景下的循环依赖/外部依赖问题
if not os.getenv("DF_SKIP_AGENTROLE_AUTOINIT"):
    for py in _pkg_path.glob("*.py"):
        if py.stem not in {"__init__", "registry", "base_agent"}:
            importlib.import_module(f"{__name__}.{py.stem}")


from .registry import AgentRegistry
# 2) 对外接口
def get_agent_cls(name: str):
    return AgentRegistry.get(name)

def create_agent(name: str, tool_manager=None, **kwargs):
    cls = get_agent_cls(name)
    return cls.create(tool_manager=tool_manager, **kwargs)

list_agents = AgentRegistry.all
