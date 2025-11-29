# Repository Guidelines

## Project Structure & Modules
- `dataflow_agent/`: core Python package (agents, workflows, tools, templates).
- `gradio_app/`: Gradio-based web UI entry (`app.py`) and pages.
- `tests/`: pytest test suite, fixtures, and sample assets.
- `docs/`: MkDocs documentation sources.
- `script/`: helper scripts for running pipelines and demos.

## Build, Test & Development
- Create venv and install dev deps:
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -r requirements-dev.txt && pip install -e .`
- Run tests: `pytest` (or `pytest -k smoke` for a quick check).
- Run web UI locally: `python gradio_app/app.py`.
- Lint/format (if configured): `pre-commit run --all-files` before each commit.

## Coding Style & Naming
- Python: 4-space indentation; prefer type hints and f-strings.
- Modules/packages: `snake_case` (e.g., `papergraph_tools.py`).
- Classes: `PascalCase`; functions and variables: `snake_case`.
- Tests: mirror module name with `test_*.py` under `tests/`.

## Testing Guidelines
- Use `pytest` for all tests; keep them deterministic and isolated.
- Place new tests in `tests/` close to the feature under test.
- Name tests by behavior, e.g., `test_pipeline_builds_valid_graph`.
- Ensure `pytest` passes locally before opening a PR.

## Commit & Pull Request Guidelines
- Follow conventional, descriptive commits, e.g., `feat: add icon generator agent`, `fix: handle empty pipeline config`.
- Keep PRs scoped and linked to an issue or design doc when relevant.
- In PR descriptions, include:
  - Summary of changes and rationale.
  - Testing performed (commands and results).
  - Screenshots or logs for UI or workflow changes when helpful.

