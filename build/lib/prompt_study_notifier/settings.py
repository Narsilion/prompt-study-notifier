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
    retention_limit: int
    scheduler_poll_seconds: int


def load_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[2]
    db_path = Path(os.environ.get("PSN_DB_PATH", "./.data/prompt-study-notifier.db")).expanduser()
    if not db_path.is_absolute():
        db_path = project_root / db_path
    return Settings(
        project_root=project_root,
        db_path=db_path,
        host=os.environ.get("PSN_HOST", "127.0.0.1"),
        port=int(os.environ.get("PSN_PORT", "8765")),
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        model=os.environ.get("PSN_MODEL", "gpt-5"),
        retention_limit=int(os.environ.get("PSN_RETENTION_LIMIT", "50")),
        scheduler_poll_seconds=int(os.environ.get("PSN_SCHEDULER_POLL_SECONDS", "15")),
    )
