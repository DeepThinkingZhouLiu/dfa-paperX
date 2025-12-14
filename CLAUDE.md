# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DataFlow-Agent is an LLM agent framework for building data processing pipelines and workflows. It features modular agent design, workflow orchestration via LangGraph, and a Gradio-based web UI.

## Build & Development Commands

```bash
# Setup environment
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt && pip install -e .

# Run tests
pytest                          # all tests
pytest -k smoke                 # quick smoke test
pytest tests/test_<name>.py     # single test file

# Run web UI
python gradio_app/app.py        # starts at http://127.0.0.1:7860

# CLI scaffolding (generates boilerplate)
dfa create --agent_name <name>      # new agent in dataflow_agent/agentroles/
dfa create --wf_name <name>         # new workflow in dataflow_agent/workflow/
dfa create --prompt_name <name>     # new prompt template
dfa create --gradio_name <name>     # new Gradio page

# Documentation
mkdocs serve                    # preview docs at http://127.0.0.1:8000
```

## Architecture

### Core Components

**State Management** (`dataflow_agent/state.py`):
- `MainState` / `MainRequest`: Base classes for all state/request objects
- `DFState` / `DFRequest`: Main pipeline state with debug, cache, and execution fields
- `Paper2GraphState`: State for paper-to-graph conversion workflows
- States use dataclasses with LangGraph message annotation for conversation history

**Agent System** (`dataflow_agent/agentroles/`):
- `BaseAgent`: Abstract base class defining the agent execution pattern
  - Supports simple mode, ReAct mode (with validation loops), and VLM (vision) mode
  - Auto-registers subclasses via `__init_subclass__` using `role_name` property
  - Key abstract properties: `role_name`, `system_prompt_template_name`, `task_prompt_template_name`
- `AgentRegistry`: Central registry accessed via `AgentRegistry.get(name)`
- Agents can be wrapped as tools via `agent.as_tool(state)` for agent-as-tool patterns

**Workflow System** (`dataflow_agent/workflow/`):
- Files must be named `wf_<name>.py` for auto-discovery
- Use `@register("<name>")` decorator to register workflows
- Run workflows via `await run_workflow("<name>", state)`
- Built on LangGraph's StateGraph for flow control

**Tool Management** (`dataflow_agent/toolkits/tool_manager.py`):
- `ToolManager`: Manages pre-tools (run before LLM) and post-tools (available to LLM)
- Tools can be role-specific or global
- Supports registering agents as callable tools

**Prompt Templates** (`dataflow_agent/promptstemplates/`):
- `PromptsTemplateGenerator`: Renders Jinja2 templates by name
- Templates defined in `prompts_repo.py` with language support (en/zh)

**LLM Callers** (`dataflow_agent/llm_callers/`):
- `TextLLMCaller`: Standard text-based LLM calls
- `VisionLLMCaller`: Multimodal VLM calls (enable via `use_vlm=True` in agent init)

### Key Patterns

**Creating a new Agent**:
```python
from dataflow_agent.agentroles.base_agent import BaseAgent

class MyAgent(BaseAgent):
    @property
    def role_name(self) -> str:
        return "MyAgent"

    @property
    def system_prompt_template_name(self) -> str:
        return "my_agent_system"

    @property
    def task_prompt_template_name(self) -> str:
        return "my_agent_task"
```

**Running an Agent**:
```python
agent = MyAgent.create(tool_manager=tm)
result_state = await agent.execute(state)
```

**Workflow Registration**:
```python
from dataflow_agent.workflow.registry import register

@register("my_workflow")
def create_my_workflow_graph():
    # Return a GraphBuilder instance
    pass
```

## Coding Conventions

- Python 3.9+, 4-space indentation, type hints preferred
- Module names: `snake_case`; Classes: `PascalCase`
- Test files mirror module names: `test_<module>.py`
- Agents: `<name>_agent.py` in `agentroles/`
- Workflows: `wf_<name>.py` in `workflow/`
- Commit style: `feat:`, `fix:`, `refactor:` prefixes
