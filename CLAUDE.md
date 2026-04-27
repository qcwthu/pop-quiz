# Repository Guidelines

## Project Structure & Module Organization
- `src/pop_quiz/` holds the FastAPI app, CLI, game logic, and WebSocket handlers.
- `src/pop_quiz/static/` contains the HTML/CSS/JS for host and participant views.
- `tests/` contains pytest suites such as `test_state.py` and `test_handlers.py`.
- `examples/` and `generated/` store quiz YAML samples (`.yml`/`.yaml`).
- `scripts/` includes tooling like `build-zipapp.sh` for portable builds.

## Build, Test, and Development Commands
- `uv sync` installs dev dependencies in the local environment.
- `uv run pop-quiz /path/to/quiz.yaml` runs the server with a quiz file.
- `OPENAI_API_KEY=... uv run pop-quiz` generates a quiz via OpenAI and runs.
- `uv run pytest` runs the full test suite.
- `uv run ruff check src/ tests/` runs lint checks.
- `uv run ruff format src/ tests/` formats code to project standards.
- `./scripts/build-zipapp.sh` builds a `.pyz` in `dist/`.

## Coding Style & Naming Conventions
- Python 3.11+, 4-space indentation, and 79-char line length (see Ruff config).
- Use `ruff format` for formatting and `ruff check` for linting.
- Name modules and functions in `snake_case`; classes in `PascalCase`.
- Keep quiz data as YAML with clear titles and `questions` lists.

## Testing Guidelines
- Tests use `pytest` and `pytest-asyncio`.
- Name tests `test_*.py` with `test_*` functions; keep async tests explicit.
- Add coverage for scoring, state transitions, and WebSocket handlers when changed.

## Commit & Pull Request Guidelines
- No Git history is available in this checkout; use concise, imperative messages.
- If you use prefixes, keep them consistent (e.g., `feat:`, `fix:`).
- PRs should include a brief summary, test commands run, and UI screenshots when relevant.

## Configuration & Secrets
- `OPENAI_API_KEY` enables quiz generation; do not commit secrets to the repo.
- CLI flags like `--host`, `--port`, and `--no-browser` control runtime behavior.
