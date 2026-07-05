from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from prompt_study_notifier.schemas import (
    ScheduleRecord,
    ScheduleUpsert,
    SessionRecord,
    SessionSummary,
    StudyPayload,
    SettingsUpdateRequest,
    TemplateRecord,
    TemplateUpsert,
)
from prompt_study_notifier.scheduler import compute_next_run, infer_interval_minutes_from_cron


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_now_iso() -> str:
    return utc_now().isoformat()


@dataclass(slots=True)
class Database:
    db_path: Path

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS prompt_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    system_prompt TEXT NOT NULL,
                    user_prompt_template TEXT NOT NULL,
                    output_schema_version TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS template_variables (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    label TEXT,
                    description TEXT,
                    example TEXT,
                    required INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(template_id) REFERENCES prompt_templates(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    template_id INTEGER NOT NULL,
                    variables_json TEXT NOT NULL,
                    cron_expr TEXT NOT NULL,
                    interval_minutes INTEGER,
                    timezone TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    notification_enabled INTEGER NOT NULL DEFAULT 1,
                    telegram_enabled INTEGER NOT NULL DEFAULT 0,
                    next_run_at TEXT,
                    last_run_at TEXT,
                    last_session_id INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(template_id) REFERENCES prompt_templates(id)
                );

                CREATE TABLE IF NOT EXISTS generated_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schedule_id INTEGER NOT NULL,
                    template_id INTEGER NOT NULL,
                    render_payload_json TEXT,
                    model_name TEXT NOT NULL,
                    prompt_snapshot_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_text TEXT,
                    generated_at TEXT NOT NULL,
                    generation_seconds REAL,
                    acknowledged_at TEXT,
                    FOREIGN KEY(schedule_id) REFERENCES schedules(id),
                    FOREIGN KEY(template_id) REFERENCES prompt_templates(id)
                );

                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO app_settings(key, value) VALUES('schema_version', '1')"
            )
            generated_session_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(generated_sessions)").fetchall()
            }
            schedule_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(schedules)").fetchall()
            }
            if "interval_minutes" not in schedule_columns:
                connection.execute("ALTER TABLE schedules ADD COLUMN interval_minutes INTEGER")
            if "telegram_enabled" not in schedule_columns:
                connection.execute("ALTER TABLE schedules ADD COLUMN telegram_enabled INTEGER NOT NULL DEFAULT 0")
            if "preferred_speech_voice_uri" not in schedule_columns:
                connection.execute("ALTER TABLE schedules ADD COLUMN preferred_speech_voice_uri TEXT NOT NULL DEFAULT ''")
            if "generation_seconds" not in generated_session_columns:
                connection.execute("ALTER TABLE generated_sessions ADD COLUMN generation_seconds REAL")
            if "acknowledged_at" not in generated_session_columns:
                connection.execute("ALTER TABLE generated_sessions ADD COLUMN acknowledged_at TEXT")
            legacy_schedules = connection.execute(
                "SELECT id, cron_expr, timezone FROM schedules WHERE interval_minutes IS NULL OR interval_minutes <= 0"
            ).fetchall()
            for row in legacy_schedules:
                interval_minutes = self._infer_legacy_interval_minutes(
                    cron_expr=row["cron_expr"],
                    timezone_name=row["timezone"],
                )
                connection.execute(
                    "UPDATE schedules SET interval_minutes = ?, updated_at = ? WHERE id = ?",
                    (interval_minutes, utc_now_iso(), row["id"]),
                )
            connection.commit()

    def get_app_setting(self, key: str, default: str | None = None) -> str | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return default
            return str(row["value"])

    def set_app_setting(self, key: str, value: str) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO app_settings(key, value) VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def get_active_model(self, default_model: str) -> str:
        return self.get_app_setting("active_model", default_model) or default_model

    def get_active_ai_provider(self, default_provider: str) -> str:
        return self.get_app_setting("active_ai_provider", default_provider) or default_provider

    def get_ui_theme(self) -> str:
        theme = self.get_app_setting("ui_theme", "dark") or "dark"
        if theme not in {"dark", "dark_green", "dark_brown"}:
            return "dark"
        return theme

    def update_settings(self, payload: SettingsUpdateRequest) -> None:
        self.set_app_setting("active_ai_provider", payload.active_ai_provider)
        self.set_app_setting("active_model", payload.active_model)
        self.set_app_setting("ui_theme", payload.ui_theme)

    @contextmanager
    def connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def bootstrap_defaults(self) -> None:
        templates = self.list_templates()
        if not templates:
            self.create_template(self._default_template_payload())
            return
        self._migrate_legacy_default_template(templates)

    def _default_template_payload(self) -> TemplateUpsert:
        return TemplateUpsert(
            name="Language study drill",
            description="Generates short study items for any target language and focus area.",
            system_prompt=(
                "You are a precise language tutor. Create concise, educational material that is accurate, "
                "varied, useful for repeated study, and tailored to the target language and learner level."
            ),
            user_prompt_template=(
                "Create a study session for {target_language}. Topic: {topic}. Focus area: {focus_area}. "
                "Learner level: {difficulty}. Produce 5 items with examples, translations when helpful, and short notes."
            ),
            variables=[
                {"name": "target_language", "label": "Target Language", "example": "Spanish"},
                {"name": "topic", "label": "Topic", "example": "restaurant conversations"},
                {"name": "focus_area", "label": "Focus Area", "example": "polite requests in the past tense"},
                {"name": "difficulty", "label": "Difficulty", "example": "A2-B1"},
            ],
        )

    def _migrate_legacy_default_template(self, templates: list[TemplateRecord]) -> None:
        legacy_system_prompt = (
            "You are a precise language tutor. Create concise, educational material that is accurate,"
            " varied, and useful for repeated study."
        )
        legacy_user_prompt = (
            "Create a study session about {topic}. Focus on {focus_area}. Use difficulty {difficulty}. "
            "Produce 5 items with examples and short notes."
        )
        legacy_variable_names = ["topic", "focus_area", "difficulty"]
        for template in templates:
            if (
                template.name == "German cases drill"
                and template.description == "Generates short German examples focused on a chosen case."
                and template.system_prompt == legacy_system_prompt
                and template.user_prompt_template == legacy_user_prompt
                and template.variable_names == legacy_variable_names
            ):
                self.update_template(template.id, self._default_template_payload())
                return

    def create_template(self, payload: TemplateUpsert) -> TemplateRecord:
        now = utc_now_iso()
        with self.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO prompt_templates(
                    name, description, system_prompt, user_prompt_template,
                    output_schema_version, is_active, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.name,
                    payload.description,
                    payload.system_prompt,
                    payload.user_prompt_template,
                    payload.output_schema_version,
                    int(payload.is_active),
                    now,
                    now,
                ),
            )
            template_id = int(cursor.lastrowid)
            for variable in payload.variables:
                connection.execute(
                    """
                    INSERT INTO template_variables(
                        template_id, name, label, description, example, required, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        template_id,
                        variable.name,
                        variable.label,
                        variable.description,
                        variable.example,
                        int(variable.required),
                        now,
                    ),
                )
        return self.get_template(template_id)

    def update_template(self, template_id: int, payload: TemplateUpsert) -> TemplateRecord:
        now = utc_now_iso()
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE prompt_templates
                SET name = ?, description = ?, system_prompt = ?, user_prompt_template = ?,
                    output_schema_version = ?, is_active = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    payload.name,
                    payload.description,
                    payload.system_prompt,
                    payload.user_prompt_template,
                    payload.output_schema_version,
                    int(payload.is_active),
                    now,
                    template_id,
                ),
            )
            connection.execute("DELETE FROM template_variables WHERE template_id = ?", (template_id,))
            for variable in payload.variables:
                connection.execute(
                    """
                    INSERT INTO template_variables(
                        template_id, name, label, description, example, required, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        template_id,
                        variable.name,
                        variable.label,
                        variable.description,
                        variable.example,
                        int(variable.required),
                        now,
                    ),
                )
        return self.get_template(template_id)

    def list_templates(self) -> list[TemplateRecord]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM prompt_templates ORDER BY updated_at DESC, id DESC"
            ).fetchall()
            return [self._hydrate_template(connection, row) for row in rows]

    def get_template(self, template_id: int) -> TemplateRecord:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM prompt_templates WHERE id = ?",
                (template_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Template not found: {template_id}")
            return self._hydrate_template(connection, row)

    def delete_template(self, template_id: int) -> None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT id FROM prompt_templates WHERE id = ?",
                (template_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Template not found: {template_id}")
            dependent_schedule = connection.execute(
                "SELECT id FROM schedules WHERE template_id = ? LIMIT 1",
                (template_id,),
            ).fetchone()
            if dependent_schedule is not None:
                raise ValueError(
                    "Template is used by one or more schedules. Delete those schedules first, then delete the template."
                )
            connection.execute("DELETE FROM generated_sessions WHERE template_id = ?", (template_id,))
            connection.execute("DELETE FROM template_variables WHERE template_id = ?", (template_id,))
            connection.execute("DELETE FROM prompt_templates WHERE id = ?", (template_id,))

    def _hydrate_template(self, connection: sqlite3.Connection, row: sqlite3.Row) -> TemplateRecord:
        variable_rows = connection.execute(
            "SELECT name, label, description, example, required FROM template_variables WHERE template_id = ? ORDER BY id",
            (row["id"],),
        ).fetchall()
        variables = [
            {
                "name": item["name"],
                "label": item["label"],
                "description": item["description"],
                "example": item["example"],
                "required": bool(item["required"]),
            }
            for item in variable_rows
        ]
        return TemplateRecord.model_validate(
            {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "system_prompt": row["system_prompt"],
                "user_prompt_template": row["user_prompt_template"],
                "output_schema_version": row["output_schema_version"],
                "is_active": bool(row["is_active"]),
                "variables": variables,
                "variable_names": [item["name"] for item in variable_rows],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )

    def create_schedule(self, payload: ScheduleUpsert) -> ScheduleRecord:
        now = utc_now()
        self._validate_timezone(payload.timezone)
        interval_minutes = self._resolve_interval_minutes(payload)
        next_run = compute_next_run(interval_minutes, after=now).isoformat()
        with self.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO schedules(
                    name, template_id, variables_json, cron_expr, interval_minutes, timezone,
                    is_active, notification_enabled, telegram_enabled, preferred_speech_voice_uri, next_run_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.name,
                    payload.template_id,
                    json.dumps(payload.variables),
                    payload.cron_expr or "",
                    interval_minutes,
                    payload.timezone,
                    int(payload.is_active),
                    int(payload.notification_enabled),
                    int(payload.telegram_enabled),
                    payload.preferred_speech_voice_uri,
                    next_run if payload.is_active else None,
                    utc_now_iso(),
                    utc_now_iso(),
                ),
            )
        return self.get_schedule(int(cursor.lastrowid))

    def update_schedule(self, schedule_id: int, payload: ScheduleUpsert) -> ScheduleRecord:
        now = utc_now()
        self._validate_timezone(payload.timezone)
        interval_minutes = self._resolve_interval_minutes(payload)
        existing_schedule = self.get_schedule(schedule_id)
        next_run = None
        if payload.is_active and existing_schedule.pending_acknowledgement_count == 0:
            next_run = compute_next_run(interval_minutes, after=now).isoformat()
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE schedules
                SET name = ?, template_id = ?, variables_json = ?, cron_expr = ?, interval_minutes = ?, timezone = ?,
                    is_active = ?, notification_enabled = ?, telegram_enabled = ?, preferred_speech_voice_uri = ?, next_run_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    payload.name,
                    payload.template_id,
                    json.dumps(payload.variables),
                    payload.cron_expr or "",
                    interval_minutes,
                    payload.timezone,
                    int(payload.is_active),
                    int(payload.notification_enabled),
                    int(payload.telegram_enabled),
                    payload.preferred_speech_voice_uri,
                    next_run,
                    utc_now_iso(),
                    schedule_id,
                ),
            )
        return self.get_schedule(schedule_id)

    def delete_schedule(self, schedule_id: int) -> None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT id FROM schedules WHERE id = ?",
                (schedule_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Schedule not found: {schedule_id}")
            connection.execute("DELETE FROM generated_sessions WHERE schedule_id = ?", (schedule_id,))
            connection.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))

    def _hydrate_schedule(self, row: sqlite3.Row) -> ScheduleRecord:
        pending_acknowledgement_count = int(row["pending_acknowledgement_count"]) if "pending_acknowledgement_count" in row.keys() else 0
        return ScheduleRecord.model_validate(
            {
                "id": row["id"],
                "name": row["name"],
                "template_id": row["template_id"],
                "variables": json.loads(row["variables_json"]),
                "interval_minutes": row["interval_minutes"],
                "cron_expr": row["cron_expr"],
                "timezone": row["timezone"],
                "is_active": bool(row["is_active"]),
                "notification_enabled": bool(row["notification_enabled"]),
                "telegram_enabled": bool(row["telegram_enabled"]) if "telegram_enabled" in row.keys() else False,
                "preferred_speech_voice_uri": row["preferred_speech_voice_uri"] if "preferred_speech_voice_uri" in row.keys() else "",
                "next_run_at": row["next_run_at"],
                "last_run_at": row["last_run_at"],
                "last_session_id": row["last_session_id"],
                "awaiting_acknowledgement": pending_acknowledgement_count > 0,
                "pending_acknowledgement_count": pending_acknowledgement_count,
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )

    def update_schedule_after_run(self, schedule_id: int, *, when: datetime, session_id: int | None) -> None:
        schedule = self.get_schedule(schedule_id)
        session = self.get_session(session_id) if session_id is not None else None
        next_run_at = None
        blocks_future_generation = (
            session is not None
            and session.status == "success"
            and session.acknowledged_at is None
            and not schedule.telegram_enabled
        )
        if schedule.is_active and not blocks_future_generation:
            next_run_at = compute_next_run(schedule.interval_minutes, after=when).isoformat()
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE schedules
                SET last_run_at = ?, next_run_at = ?, last_session_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    when.isoformat(),
                    next_run_at,
                    session_id,
                    utc_now_iso(),
                    schedule_id,
                ),
            )

    def create_session(
        self,
        *,
        schedule_id: int,
        template_id: int,
        render_payload: StudyPayload | None,
        model_name: str,
        prompt_snapshot: dict[str, Any],
        status: str,
        error_text: str | None,
        generated_at: datetime | None = None,
        generation_seconds: float | None = None,
    ) -> SessionRecord:
        generated_time = generated_at or utc_now()
        with self.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO generated_sessions(
                    schedule_id, template_id, render_payload_json, model_name,
                    prompt_snapshot_json, status, error_text, generated_at, generation_seconds, acknowledged_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    schedule_id,
                    template_id,
                    json.dumps(render_payload.model_dump()) if render_payload else None,
                    model_name,
                    json.dumps(prompt_snapshot),
                    status,
                    error_text,
                    generated_time.isoformat(),
                    generation_seconds,
                    None,
                ),
            )
        session = self.get_session(int(cursor.lastrowid))
        self.prune_sessions()
        return session

    def get_session(self, session_id: int) -> SessionRecord:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM generated_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Session not found: {session_id}")
        payload = StudyPayload.model_validate(json.loads(row["render_payload_json"])) if row["render_payload_json"] else None
        return SessionRecord(
            id=row["id"],
            schedule_id=row["schedule_id"],
            template_id=row["template_id"],
            render_payload=payload,
            model_name=row["model_name"],
            prompt_snapshot=json.loads(row["prompt_snapshot_json"]),
            status=row["status"],
            error_text=row["error_text"],
            generated_at=row["generated_at"],
            generation_seconds=row["generation_seconds"],
            acknowledged_at=row["acknowledged_at"],
        )

    def list_schedule_terms(self, schedule_id: int) -> list[str]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT render_payload_json
                FROM generated_sessions
                WHERE schedule_id = ? AND status = 'success' AND render_payload_json IS NOT NULL
                ORDER BY generated_at DESC, id DESC
                """,
                (schedule_id,),
            ).fetchall()
        seen: set[str] = set()
        terms: list[str] = []
        for row in rows:
            try:
                payload = StudyPayload.model_validate(json.loads(row["render_payload_json"]))
            except Exception:
                continue
            for item in payload.items:
                term = item.term.strip()
                if not term:
                    continue
                normalized_term = term.casefold()
                if normalized_term in seen:
                    continue
                seen.add(normalized_term)
                terms.append(term)
        return terms

    def list_schedule_history_items(self, schedule_id: int, *, limit: int = 30) -> list[dict[str, str]]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT render_payload_json
                FROM generated_sessions
                WHERE schedule_id = ? AND status = 'success' AND render_payload_json IS NOT NULL
                ORDER BY generated_at DESC, id DESC
                LIMIT ?
                """,
                (schedule_id, limit),
            ).fetchall()
        history_items: list[dict[str, str]] = []
        seen_terms: set[str] = set()
        for row in rows:
            try:
                payload = StudyPayload.model_validate(json.loads(row["render_payload_json"]))
            except Exception:
                continue
            for item in payload.items:
                term = item.term.strip()
                if not term:
                    continue
                normalized_term = term.casefold()
                if normalized_term in seen_terms:
                    continue
                seen_terms.add(normalized_term)
                entry = {"term": term}
                if item.example_source and item.example_source.strip():
                    entry["example_source"] = item.example_source.strip()
                if item.example_target and item.example_target.strip():
                    entry["example_target"] = item.example_target.strip()
                if item.notes and item.notes.strip():
                    entry["notes"] = item.notes.strip()
                history_items.append(entry)
        return history_items

    def prune_sessions(self, *, limit: int = 50) -> None:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT id
                FROM generated_sessions
                WHERE NOT (status = 'success' AND acknowledged_at IS NULL)
                ORDER BY generated_at DESC, id DESC
                LIMIT -1 OFFSET ?
                """,
                (limit,),
            ).fetchall()
            if not rows:
                return
            connection.executemany(
                "DELETE FROM generated_sessions WHERE id = ?",
                [(row["id"],) for row in rows],
            )

    def clear_sessions(self) -> None:
        with self.connection() as connection:
            connection.execute("UPDATE schedules SET last_session_id = NULL, next_run_at = NULL")
            connection.execute("DELETE FROM generated_sessions")
        self._recompute_all_schedule_next_runs()

    def delete_session(self, session_id: int) -> None:
        session = self.get_session(session_id)
        with self.connection() as connection:
            row = connection.execute(
                "SELECT id FROM generated_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Session not found: {session_id}")
            connection.execute(
                "UPDATE schedules SET last_session_id = NULL WHERE last_session_id = ?",
                (session_id,),
            )
            connection.execute(
                "DELETE FROM generated_sessions WHERE id = ?",
                (session_id,),
            )
        self._recompute_schedule_next_run(session.schedule_id)

    def list_sessions(self, *, limit: int = 20, schedule_id: int | None = None) -> list[SessionSummary]:
        schedule_filter = "WHERE schedule_id = ?" if schedule_id is not None else ""
        pending_schedule_filter = "AND schedule_id = ?" if schedule_id is not None else ""
        params: tuple[int, ...]
        if schedule_id is None:
            params = (limit,)
        else:
            params = (schedule_id, limit, schedule_id)
        with self.connection() as connection:
            rows = connection.execute(
                f"""
                WITH recent_sessions AS (
                    SELECT id
                    FROM generated_sessions
                    {schedule_filter}
                    ORDER BY generated_at DESC, id DESC
                    LIMIT ?
                ),
                pending_acknowledgement_sessions AS (
                    SELECT id
                    FROM generated_sessions
                    WHERE status = 'success' AND acknowledged_at IS NULL
                    {pending_schedule_filter}
                )
                SELECT id, schedule_id, template_id, render_payload_json, status, error_text, generated_at, acknowledged_at
                FROM generated_sessions
                WHERE id IN (
                    SELECT id FROM recent_sessions
                    UNION
                    SELECT id FROM pending_acknowledgement_sessions
                )
                ORDER BY generated_at DESC, id DESC
                """,
                params,
            ).fetchall()
            summaries = []
            for row in rows:
                payload = None
                title = None
                topic = None
                if row["render_payload_json"]:
                    try:
                        payload = StudyPayload.model_validate(json.loads(row["render_payload_json"]))
                        title = payload.title
                        topic = payload.topic
                    except Exception:
                        pass  # Ignore parsing errors
                summaries.append(SessionSummary(
                    id=row["id"],
                    schedule_id=row["schedule_id"],
                    template_id=row["template_id"],
                    status=row["status"],
                    generated_at=row["generated_at"],
                    error_text=row["error_text"],
                    title=title,
                    topic=topic,
                    acknowledged_at=row["acknowledged_at"],
                ))
            return summaries

    def list_schedules(self) -> list[ScheduleRecord]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT schedules.*,
                       COALESCE(ack.pending_acknowledgement_count, 0) AS pending_acknowledgement_count
                FROM schedules
                LEFT JOIN (
                    SELECT schedule_id, COUNT(*) AS pending_acknowledgement_count
                    FROM generated_sessions
                    WHERE status = 'success' AND acknowledged_at IS NULL
                    GROUP BY schedule_id
                ) AS ack ON ack.schedule_id = schedules.id
                ORDER BY schedules.updated_at DESC, schedules.id DESC
                """
            ).fetchall()
            return [self._hydrate_schedule(row) for row in rows]

    def list_due_schedules(self, now: datetime | None = None) -> list[ScheduleRecord]:
        threshold = (now or utc_now()).isoformat()
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT schedules.*,
                       COALESCE(ack.pending_acknowledgement_count, 0) AS pending_acknowledgement_count
                FROM schedules
                LEFT JOIN (
                    SELECT schedule_id, COUNT(*) AS pending_acknowledgement_count
                    FROM generated_sessions
                    WHERE status = 'success' AND acknowledged_at IS NULL
                    GROUP BY schedule_id
                ) AS ack ON ack.schedule_id = schedules.id
                WHERE schedules.is_active = 1
                  AND schedules.next_run_at IS NOT NULL
                  AND schedules.next_run_at <= ?
                ORDER BY schedules.next_run_at ASC, schedules.id ASC
                """,
                (threshold,),
            ).fetchall()
            return [self._hydrate_schedule(row) for row in rows]

    def get_schedule(self, schedule_id: int) -> ScheduleRecord:
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT schedules.*,
                       COALESCE(ack.pending_acknowledgement_count, 0) AS pending_acknowledgement_count
                FROM schedules
                LEFT JOIN (
                    SELECT schedule_id, COUNT(*) AS pending_acknowledgement_count
                    FROM generated_sessions
                    WHERE status = 'success' AND acknowledged_at IS NULL
                    GROUP BY schedule_id
                ) AS ack ON ack.schedule_id = schedules.id
                WHERE schedules.id = ?
                """,
                (schedule_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Schedule not found: {schedule_id}")
            return self._hydrate_schedule(row)

    def acknowledge_session(self, session_id: int, *, acknowledged_at: datetime | None = None) -> SessionRecord:
        session = self.get_session(session_id)
        if session.status != "success":
            return session
        if session.acknowledged_at is not None:
            return session
        acknowledged_time = (acknowledged_at or utc_now()).isoformat()
        with self.connection() as connection:
            connection.execute(
                "UPDATE generated_sessions SET acknowledged_at = ? WHERE id = ?",
                (acknowledged_time, session_id),
            )
        self._recompute_schedule_next_run(session.schedule_id, after=datetime.fromisoformat(acknowledged_time))
        return self.get_session(session_id)

    def _recompute_all_schedule_next_runs(self) -> None:
        for schedule in self.list_schedules():
            self._recompute_schedule_next_run(schedule.id)

    def _recompute_schedule_next_run(self, schedule_id: int, *, after: datetime | None = None) -> None:
        schedule = self.get_schedule(schedule_id)
        next_run_at = None
        if schedule.is_active and schedule.pending_acknowledgement_count == 0:
            base_time = after or utc_now()
            next_run_at = compute_next_run(schedule.interval_minutes, after=base_time).isoformat()
        with self.connection() as connection:
            connection.execute(
                "UPDATE schedules SET next_run_at = ?, updated_at = ? WHERE id = ?",
                (next_run_at, utc_now_iso(), schedule_id),
            )

    def _validate_timezone(self, timezone_name: str) -> None:
        try:
            ZoneInfo(timezone_name)
        except Exception as exc:
            raise ValueError(f"Invalid timezone: {timezone_name}") from exc

    def _resolve_interval_minutes(self, payload: ScheduleUpsert) -> int:
        if payload.interval_minutes is not None:
            if payload.interval_minutes <= 0:
                raise ValueError("Interval must be greater than zero minutes.")
            return payload.interval_minutes
        return self._infer_legacy_interval_minutes(
            cron_expr=payload.cron_expr,
            timezone_name=payload.timezone,
        )

    def _infer_legacy_interval_minutes(self, *, cron_expr: str | None, timezone_name: str) -> int:
        if not cron_expr:
            raise ValueError("interval_minutes is required.")
        return infer_interval_minutes_from_cron(cron_expr, timezone_name=timezone_name)
