# Project Overview
Prompt Study Notifier is a local-first FastAPI app that stores prompt templates, schedules prompt runs, generates structured study payloads via the OpenAI API, persists results in SQLite, and pushes live updates to a browser dashboard over WebSocket.

# Architecture
- Runtime composition lives in `prompt_study_notifier/app.py`: it wires `Database`, `OpenAIClient`, `GenerationService`, `LiveUpdateBroker`, and an in-process `SchedulerRuntime` into one FastAPI app.
- Persistence is direct `sqlite3`, not an ORM. `prompt_study_notifier/db.py` owns schema creation, light migrations, CRUD for templates/schedules/sessions, app settings, and default data bootstrap.
- Generation flow is synchronous business logic in `prompt_study_notifier/generation.py`: load schedule/template, render variables, call OpenAI, persist success/failure session, update next run, prune old sessions, emit a `LiveEvent`.
- Prompt rendering is simple Python `str.format_map` with extracted `{variable}` names in `prompt_study_notifier/rendering.py`. Missing variables raise `MissingTemplateVariableError`; `gender` has a random fallback.
- Scheduling uses a custom 5-field cron parser in `prompt_study_notifier/scheduler.py` with `zoneinfo`. No external scheduler library is used.
- UI is server-rendered HTML/CSS/JS returned as strings from `prompt_study_notifier/ui.py`; there is no frontend build step.
- `prompt_study_notifier/schemas.py` defines the API contract and stored payload shapes with Pydantic v2 models.

# Key Entrypoints
- CLI entrypoint: `prompt-study-notifier` -> `prompt_study_notifier.main:main`
- App factory: `prompt_study_notifier.app:create_app`
- Dashboard page: `GET /`
- Templates page: `GET /templates`
- JSON API: `/api/settings`, `/api/templates`, `/api/schedules`, `/api/sessions`
- Live updates WebSocket: `/api/live`
- Test coverage starts in `tests/test_api.py`, `tests/test_generation.py`, `tests/test_scheduler.py`, `tests/test_rendering.py`, `tests/test_settings.py`

# Conventions
- Edit the top-level `prompt_study_notifier/` package unless you are intentionally reconciling the duplicate `src/prompt_study_notifier/` tree. `pyproject.toml` packages `prompt_study_notifier*` from `.`; tests also import the top-level package.
- Keep new API shapes in `schemas.py` first, then update DB hydration/serialization and route handlers to match.
- DB writes are explicit SQL per method. Schema changes should extend `Database.initialize()` with backward-compatible migration logic.
- Route handlers stay thin; nontrivial work belongs in `Database`, `GenerationService`, `rendering.py`, or scheduler helpers.
- The UI is plain inline JavaScript embedded in Python string builders. Preserve that style unless doing a larger frontend refactor.
- Settings come from environment variables via `load_settings()` and from `app_settings` in SQLite for mutable runtime settings such as `active_model`.

# Development
- Create env and install dev deps with Python 3.14: `python3.14 -m venv .venv && source .venv/bin/activate && python -m pip install -e '.[dev]'`
- Run app: `prompt-study-notifier`
- Default local URL: `http://127.0.0.1:8765`
- Run tests: `pytest`
- Default DB location: `./.data/prompt-study-notifier.db`
- Useful env vars: `OPENAI_API_KEY`, `PSN_MODEL`, `PSN_HOST`, `PSN_PORT`, `PSN_DB_PATH`, `PSN_RETENTION_LIMIT`, `PSN_SCHEDULER_POLL_SECONDS`

# Constraints
- OpenAI integration uses raw `urllib.request` against `/v1/chat/completions` with JSON-schema output enforcement; failures are persisted as failed sessions rather than raised through the scheduler loop.
- Scheduler execution is in-process and poll-based. There is no job queue, no distributed lock, and deduplication only tracks currently running schedule IDs in memory.
- SQLite is the single source of truth; concurrent behavior and migrations should be treated conservatively.
- The repository currently contains generated/build artifacts and duplicated package trees (`build/`, top-level package, `src/` package). Avoid editing generated output and do not assume `src/` is the live code path.
- The worktree may already contain unrelated edits; do not overwrite them when reconciling duplicated files.
