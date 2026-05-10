# Prompt Study Notifier

Local-first web application that generates study material from scheduled prompts and pushes updates into an open browser dashboard.

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Setup](#setup)
- [Run](#run)
- [Environment](#environment)
- [Tests](#tests)

## Features

- reusable prompt templates with variable substitution
- schedules stored in SQLite
- OpenAI or GitHub Models-backed generation with strict JSON validation
- recent session history
- live dashboard updates over WebSocket
- browser notifications for new content when permission is granted

## Requirements

- Python 3.14+
- `OPENAI_API_KEY` or `GITHUB_MODELS_TOKEN`/`GITHUB_TOKEN`

## Setup

```bash
cd /Users/darkcreation/Documents/git_repos/prompt-study-notifier
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
export OPENAI_API_KEY="your_api_key_here"
# or:
export PSN_AI_PROVIDER="github"
export GITHUB_MODELS_TOKEN="your_github_models_token"
```

If you use `pyenv` or similar local version managers, the repo now targets Python `3.14`.

In `zsh`, quote the extras spec:

```bash
python -m pip install -e '.[dev]'
```

## Run

```bash
prompt-study-notifier
```

Default URL: `http://127.0.0.1:8765`

After local code changes, restart with an editable reinstall so the console script uses the latest package:

```bash
.venv/bin/python -m pip install -e '.[dev]' && prompt-study-notifier
```

## Environment

- `OPENAI_API_KEY` required for real OpenAI generation
- `PSN_AI_PROVIDER` default `openai`; set to `github` for GitHub Models
- `GITHUB_MODELS_TOKEN` or `GITHUB_TOKEN` required for real GitHub Models generation
- `PSN_GITHUB_MODELS` comma-separated GitHub Models fallback list, default `openai/gpt-4.1`
- `PSN_MODEL` default `gpt-5`
- `PSN_HOST` default `127.0.0.1`
- `PSN_PORT` default `8765`
- `PSN_DB_PATH` default `./.data/prompt-study-notifier.db`
- `PSN_RETENTION_LIMIT` default `50`
- `PSN_SCHEDULER_POLL_SECONDS` default `15`

## Tests

```bash
pytest
```
