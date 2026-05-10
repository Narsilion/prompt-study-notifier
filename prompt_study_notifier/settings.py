from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    project_root: Path
    db_path: Path
    host: str
    port: int
    openai_api_key: str | None
    model: str
    prompt_cache_retention: str
    retention_limit: int
    scheduler_poll_seconds: int
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    ai_provider: str = "openai"
    github_models_token: str | None = None
    github_models_token_source: str | None = None
    github_models: list[str] | None = None


def resolve_project_root() -> Path:
    cwd = Path.cwd().resolve()
    if (cwd / "pyproject.toml").exists() and ((cwd / "prompt_study_notifier").exists() or (cwd / "src" / "prompt_study_notifier").exists()):
        return cwd
    return Path(__file__).resolve().parents[2]


def load_settings() -> Settings:
    project_root = resolve_project_root()
    db_path = Path(os.environ.get("PSN_DB_PATH", "./.data/prompt-study-notifier.db")).expanduser()
    if not db_path.is_absolute():
        db_path = project_root / db_path
    github_models = [
        model.strip()
        for model in os.environ.get("PSN_GITHUB_MODELS", "openai/gpt-4.1").split(",")
        if model.strip()
    ]
    return Settings(
        project_root=project_root,
        db_path=db_path,
        host=os.environ.get("PSN_HOST", "127.0.0.1"),
        port=int(os.environ.get("PSN_PORT", "8765")),
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        model=os.environ.get("PSN_MODEL", "gpt-5"),
        prompt_cache_retention=os.environ.get("PSN_PROMPT_CACHE_RETENTION", "in_memory"),
        retention_limit=int(os.environ.get("PSN_RETENTION_LIMIT", "50")),
        scheduler_poll_seconds=int(os.environ.get("PSN_SCHEDULER_POLL_SECONDS", "15")),
        telegram_bot_token=os.environ.get("PSN_TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.environ.get("PSN_TELEGRAM_CHAT_ID"),
        ai_provider=os.environ.get("PSN_AI_PROVIDER", "openai").strip().lower() or "openai",
        github_models_token=os.environ.get("GITHUB_MODELS_TOKEN") or os.environ.get("GITHUB_TOKEN"),
        github_models_token_source=(
            "GITHUB_MODELS_TOKEN"
            if os.environ.get("GITHUB_MODELS_TOKEN")
            else ("GITHUB_TOKEN" if os.environ.get("GITHUB_TOKEN") else None)
        ),
        github_models=github_models or ["openai/gpt-4.1"],
    )
