# Codex Onboarding

Use this at the start of a new Codex session for this repository.

```text
You are working in the repository `/Users/darkcreation/Documents/git_repos/prompt-study-notifier`.

Before making changes, build a compact mental model of the project and keep it in mind for the rest of the session.

What this repo is:
- A local-first FastAPI app for scheduled study-card generation.
- It stores templates, schedules, sessions, and settings in SQLite.
- It generates structured study payloads through the OpenAI API.
- It has a server-rendered dashboard with inline JS/CSS in Python strings.
- It pushes live updates over WebSocket.
- It supports Telegram delivery for successful runs.

Important architecture:
- App composition: `prompt_study_notifier/app.py`
- DB and migrations: `prompt_study_notifier/db.py`
- Generation flow: `prompt_study_notifier/generation.py`
- Prompt rendering: `prompt_study_notifier/rendering.py`
- Scheduler: `prompt_study_notifier/scheduler.py`
- Schemas/contracts: `prompt_study_notifier/schemas.py`
- Dashboard/UI: `prompt_study_notifier/ui.py`
- Telegram formatting and delivery: `prompt_study_notifier/telegram_client.py`
- Entry point: `prompt_study_notifier/main.py`

Repo conventions:
- Treat the top-level `prompt_study_notifier/` package as the primary live code.
- There is duplicate code in `src/prompt_study_notifier/` and stale/generated output in `build/`.
- Do not assume `src/` is authoritative.
- Be careful not to overwrite unrelated user changes.
- SQLite schema changes must be backward-compatible.
- Keep route handlers thin; move logic into service/db/helpers.
- UI is inline HTML/CSS/JS returned from Python, with no frontend build step.

Runtime/product rules already present in this repo:
- Telegram sending is controlled per schedule with `telegram_enabled`.
- Browser notifications remain separate from Telegram.
- Focus should be shown only when explicitly requested by schedule/template variables such as `focus_area` or `focus`.
- Session display title should prefer the schedule name.
- Telegram cards use bold term headings, capitalized display terms, and looser spacing.
- The app may be launched from an installed package, so after code changes it may require:
  `source .venv/bin/activate && python -m pip install --force-reinstall '.[dev]'`

What I want you to do at the start of the session:
1. Read the key files above.
2. Summarize the architecture in 8-12 bullets.
3. List any duplicated-package or launcher pitfalls you notice.
4. Identify the minimum set of files relevant to the task I ask next.
5. Then proceed with implementation.

When editing:
- Prefer `rg` for search.
- Use `apply_patch` for file edits.
- Run focused tests first when possible.
- Mention if a reinstall into `.venv` is needed for `prompt-study-notifier` to pick up changes.
```
