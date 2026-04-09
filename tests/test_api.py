import asyncio
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from prompt_study_notifier.app import create_app
from prompt_study_notifier.openai_client import OpenAIResult, OpenAIUsage
from prompt_study_notifier.schemas import ScheduleRecord, ScheduleUpsert, SessionRecord, StudyPayload
from prompt_study_notifier.settings import Settings
from prompt_study_notifier.telegram_client import format_session_message


def build_settings(tmp_path: Path) -> Settings:
    return Settings(
        project_root=tmp_path,
        db_path=tmp_path / "app.db",
        host="127.0.0.1",
        port=8765,
        openai_api_key=None,
        model="gpt-5",
        prompt_cache_retention="in_memory",
        retention_limit=20,
        scheduler_poll_seconds=60,
        telegram_bot_token=None,
        telegram_chat_id=None,
    )


def build_payload(term: str = "Reserva") -> StudyPayload:
    return StudyPayload.model_validate(
        {
            "title": "Spanish drill",
            "topic": "Articles",
            "summary": "Practice article usage.",
            "focus_hint": "Watch agreement.",
            "items": [{"term": term, "translation": "reservation"}],
        }
    )


def build_multi_item_payload() -> StudyPayload:
    return StudyPayload.model_validate(
        {
            "title": "Spanish drill",
            "topic": "Articles",
            "summary": "Practice article usage.",
            "focus_hint": "Watch agreement.",
            "items": [
                {
                    "term": "Reserva",
                    "translation": "reservation",
                    "example_source": "Tengo una reserva.",
                    "example_target": "I have a reservation.",
                },
                {
                    "term": "Mesa",
                    "translation": "table",
                    "example_source": "La mesa está lista.",
                    "example_target": "The table is ready.",
                },
            ],
        }
    )


class FakeOpenAIClient:
    def generate_payload(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        prompt_cache_retention: str | None = None,
    ) -> OpenAIResult:
        return OpenAIResult(
            payload=build_payload(),
            usage=OpenAIUsage(prompt_tokens=10, cached_tokens=0, total_tokens=12),
        )


class FakeTelegramClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def send_session(self, session: object, schedule: object, *, run_source: str) -> None:
        self.calls.append({"session": session, "schedule": schedule, "run_source": run_source})


def test_format_session_message_includes_focus_when_available() -> None:
    session = SessionRecord(
        id=1,
        schedule_id=2,
        template_id=3,
        render_payload=build_payload(),
        model_name="gpt-5",
        prompt_snapshot={"variables": {"difficulty": "A2", "focus_area": "agreement"}},
        status="success",
        generated_at=datetime.now(UTC).isoformat(),
    )
    schedule = ScheduleRecord(
        id=2,
        name="Language study drill",
        template_id=3,
        variables={},
        interval_minutes=60,
        timezone="UTC",
        is_active=True,
        notification_enabled=True,
        telegram_enabled=True,
        created_at=datetime.now(UTC).isoformat(),
        updated_at=datetime.now(UTC).isoformat(),
    )

    message = format_session_message(session, schedule, run_source="scheduled")

    assert "🎯 Focus: Watch agreement." in message
    assert "⏰ Schedule:" not in message
    assert "🏷️ Topic:" not in message
    assert "🗒️" not in message
    assert "🔤 Word:" not in message
def test_format_session_message_omits_focus_when_not_requested_by_template() -> None:
    session = SessionRecord(
        id=1,
        schedule_id=2,
        template_id=3,
        render_payload=build_payload(),
        model_name="gpt-5",
        prompt_snapshot={"variables": {"language": "German", "level": "A2", "topic": "any"}},
        status="success",
        generated_at=datetime.now(UTC).isoformat(),
    )
    schedule = ScheduleRecord(
        id=2,
        name="German - new words",
        template_id=3,
        variables={},
        interval_minutes=60,
        timezone="UTC",
        is_active=True,
        notification_enabled=True,
        telegram_enabled=True,
        created_at=datetime.now(UTC).isoformat(),
        updated_at=datetime.now(UTC).isoformat(),
    )

    message = format_session_message(session, schedule, run_source="scheduled")

    assert "🎯 Focus:" not in message


def test_format_session_message_includes_all_items() -> None:
    session = SessionRecord(
        id=1,
        schedule_id=2,
        template_id=3,
        render_payload=build_multi_item_payload(),
        model_name="gpt-5",
        prompt_snapshot={"variables": {"difficulty": "A2"}},
        status="success",
        generated_at=datetime.now(UTC).isoformat(),
    )
    schedule = ScheduleRecord(
        id=2,
        name="Language study drill",
        template_id=3,
        variables={},
        interval_minutes=60,
        timezone="UTC",
        is_active=True,
        notification_enabled=True,
        telegram_enabled=True,
        created_at=datetime.now(UTC).isoformat(),
        updated_at=datetime.now(UTC).isoformat(),
    )

    message = format_session_message(session, schedule, run_source="scheduled")

    assert "<b>📖 Reserva</b>" in message
    assert "<b>📖 Mesa</b>" in message
    assert "Tengo una reserva." in message
    assert "La mesa está lista." in message
    assert "1. Reserva" not in message
    assert "2. Mesa" not in message
    assert "<b>📖 Reserva</b>\n\n💬 Meaning: reservation" in message
    assert "\n\n<b>📖 Mesa</b>\n\n💬 Meaning: table" in message
    assert "💬 Meaning: reservation" in message


def test_format_session_message_capitalizes_term_headings() -> None:
    session = SessionRecord(
        id=1,
        schedule_id=2,
        template_id=3,
        render_payload=StudyPayload.model_validate(
            {
                "title": "Serbian drill",
                "topic": "Work",
                "summary": "Practice work vocabulary.",
                "focus_hint": None,
                "items": [{"term": "zakazati (pregled)", "translation": "to schedule"}],
            }
        ),
        model_name="gpt-5",
        prompt_snapshot={"variables": {"difficulty": "B1"}},
        status="success",
        generated_at=datetime.now(UTC).isoformat(),
    )
    schedule = ScheduleRecord(
        id=2,
        name="Serbian",
        template_id=3,
        variables={},
        interval_minutes=60,
        timezone="UTC",
        is_active=True,
        notification_enabled=True,
        telegram_enabled=True,
        created_at=datetime.now(UTC).isoformat(),
        updated_at=datetime.now(UTC).isoformat(),
    )

    message = format_session_message(session, schedule, run_source="manual")

    assert "<b>📖 Zakazati (pregled)</b>" in message
    assert "<b>📖 zakazati (pregled)</b>" not in message


def test_format_session_message_prefers_schedule_name_for_title() -> None:
    session = SessionRecord(
        id=1,
        schedule_id=2,
        template_id=3,
        render_payload=build_payload(),
        model_name="gpt-5",
        prompt_snapshot={"schedule_name": "German - new words", "template_name": "New word study", "variables": {"difficulty": "A2"}},
        status="success",
        generated_at=datetime.now(UTC).isoformat(),
    )
    schedule = ScheduleRecord(
        id=2,
        name="German - new words",
        template_id=3,
        variables={},
        interval_minutes=60,
        timezone="UTC",
        is_active=True,
        notification_enabled=True,
        telegram_enabled=True,
        created_at=datetime.now(UTC).isoformat(),
        updated_at=datetime.now(UTC).isoformat(),
    )

    message = format_session_message(session, schedule, run_source="scheduled")

    assert "📘 German - new words" in message
    assert "📘 Spanish drill" not in message
    assert "📘 New word study" not in message


def test_dashboard_and_basic_crud(tmp_path: Path) -> None:
    app = create_app(build_settings(tmp_path))
    client = TestClient(app)

    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert "Prompt Study Notifier" in dashboard.text
    assert "Latest Result" in dashboard.text
    assert "Schedules" in dashboard.text
    assert "data-acknowledge-session-id" in dashboard.text
    assert "Pronounce term" in dashboard.text
    assert "Pronounce example" in dashboard.text
    assert "speechSynthesis" in dashboard.text
    assert "Preferred Voice" in dashboard.text
    assert "speechVoiceInput" in dashboard.text
    assert "Template Editor" not in dashboard.text
    assert "Existing Templates" not in dashboard.text

    templates_page = client.get("/templates")
    assert templates_page.status_code == 200
    assert "Template Editor" in templates_page.text
    assert "Existing Templates" in templates_page.text

    favicon = client.get("/favicon.ico")
    assert favicon.status_code == 204

    settings = client.get("/api/settings")
    assert settings.status_code == 200
    assert settings.json()["active_model"] == "gpt-5"
    assert settings.json()["preferred_speech_voice_uri"] == ""
    assert settings.json()["prompt_cache_retention"] == "in_memory"
    assert "gpt-5.4-mini" in settings.json()["available_models"]

    updated_settings = client.put(
        "/api/settings",
        json={"active_model": "gpt-5.4-mini", "preferred_speech_voice_uri": "com.apple.voice.compact.en-US.Samantha"},
    )
    assert updated_settings.status_code == 200
    assert updated_settings.json()["active_model"] == "gpt-5.4-mini"
    assert updated_settings.json()["preferred_speech_voice_uri"] == "com.apple.voice.compact.en-US.Samantha"
    assert updated_settings.json()["prompt_cache_retention"] == "in_memory"

    templates = client.get("/api/templates")
    assert templates.status_code == 200
    assert len(templates.json()) >= 1

    template = client.post(
        "/api/templates",
        json={
            "name": "Examples",
            "description": "Example template",
            "system_prompt": "You are a tutor.",
            "user_prompt_template": "Teach {topic}",
            "output_schema_version": "v1",
            "is_active": True,
            "variables": [{"name": "topic", "label": "Topic", "required": True}],
        },
    )
    assert template.status_code == 200
    template_id = template.json()["id"]

    preview = client.post(
        "/api/templates/preview",
        json={"user_prompt_template": "Teach {topic}", "variables": {"topic": "articles"}},
    )
    assert preview.status_code == 200
    assert preview.json()["resolved_prompt"] == "Teach articles"

    literal_preview = client.post(
        "/api/templates/preview",
        json={"user_prompt_template": "Teach {{topic}} with {level}", "variables": {"topic": "articles", "level": "B1"}},
    )
    assert literal_preview.status_code == 200
    assert literal_preview.json()["resolved_prompt"] == "Teach {topic} with B1"
    assert literal_preview.json()["variable_names"] == ["level"]

    schedule = client.post(
        "/api/schedules",
        json={
            "name": "Hourly",
            "template_id": template_id,
            "variables": {"topic": "articles"},
            "interval_minutes": 60,
            "timezone": "UTC",
            "is_active": True,
            "notification_enabled": True,
            "telegram_enabled": False,
        },
    )
    assert schedule.status_code == 200
    assert schedule.json()["telegram_enabled"] is False

    sessions = client.get("/api/sessions?limit=5")
    assert sessions.status_code == 200

    cleared = client.delete("/api/sessions")
    assert cleared.status_code == 200
    assert cleared.json()["status"] == "cleared"


def test_acknowledge_session_endpoint_updates_session_and_schedule(tmp_path: Path) -> None:
    app = create_app(build_settings(tmp_path))
    with TestClient(app) as client:
        template = client.get("/api/templates").json()[0]
        schedule = client.post(
            "/api/schedules",
            json={
                "name": "Hourly",
                "template_id": template["id"],
                "variables": {"target_language": "Spanish", "topic": "articles", "focus_area": "verbs", "difficulty": "A2"},
                "interval_minutes": 60,
                "timezone": "UTC",
                "is_active": True,
                "notification_enabled": True,
                "telegram_enabled": False,
            },
        ).json()

        db = app.state.db
        session = db.create_session(
            schedule_id=schedule["id"],
            template_id=template["id"],
            render_payload=build_payload(),
            model_name="gpt-5",
            prompt_snapshot={},
            status="success",
            error_text=None,
        )
        db.update_schedule_after_run(schedule["id"], when=datetime.now(UTC), session_id=session.id)

        response = client.post(f"/api/sessions/{session.id}/acknowledge")

        assert response.status_code == 200
        payload = response.json()
        assert payload["session"]["id"] == session.id
        assert payload["session"]["acknowledged_at"] is not None
        assert payload["schedule"]["id"] == schedule["id"]
        assert payload["schedule"]["awaiting_acknowledgement"] is False
        assert payload["schedule"]["pending_acknowledgement_count"] == 0
        assert payload["schedule"]["next_run_at"] is not None


def test_run_now_endpoint_still_accepts_blocked_schedule(tmp_path: Path) -> None:
    app = create_app(build_settings(tmp_path))
    with TestClient(app) as client:
        template_id = client.get("/api/templates").json()[0]["id"]
        schedule = client.post(
            "/api/schedules",
            json={
                "name": "Hourly",
                "template_id": template_id,
                "variables": {"target_language": "Spanish", "topic": "articles", "focus_area": "verbs", "difficulty": "A2"},
                "interval_minutes": 60,
                "timezone": "UTC",
                "is_active": True,
                "notification_enabled": True,
                "telegram_enabled": False,
            },
        ).json()

        db = app.state.db
        session = db.create_session(
            schedule_id=schedule["id"],
            template_id=template_id,
            render_payload=build_payload(),
            model_name="gpt-5",
            prompt_snapshot={},
            status="success",
            error_text=None,
        )
        db.update_schedule_after_run(schedule["id"], when=datetime.now(UTC), session_id=session.id)

        blocked_schedule = client.get("/api/schedules").json()[0]
        assert blocked_schedule["awaiting_acknowledgement"] is True
        assert blocked_schedule["next_run_at"] is None

        response = client.post(f"/api/schedules/{schedule['id']}/run-now")

        assert response.status_code == 200
        assert response.json()["status"] == "queued"


def test_delete_single_session(tmp_path: Path) -> None:
    app = create_app(build_settings(tmp_path))
    with TestClient(app) as client:
        template = client.post(
            "/api/templates",
            json={
                "name": "Examples",
                "description": "Example template",
                "system_prompt": "You are a tutor.",
                "user_prompt_template": "Teach {topic}",
                "output_schema_version": "v1",
                "is_active": True,
                "variables": [{"name": "topic", "label": "Topic", "required": True}],
            },
        )
        template_id = template.json()["id"]
        schedule = client.post(
            "/api/schedules",
            json={
                "name": "Hourly",
                "template_id": template_id,
                "variables": {"topic": "articles"},
                "interval_minutes": 60,
                "timezone": "UTC",
                "is_active": True,
                "notification_enabled": True,
                "telegram_enabled": False,
            },
        )
        schedule_id = schedule.json()["id"]

        db = app.state.db
        session = db.create_session(
            schedule_id=schedule_id,
            template_id=template_id,
            render_payload=None,
            model_name="gpt-5",
            prompt_snapshot={},
            status="failed",
            error_text="quota",
        )
        db.update_schedule_after_run(schedule_id, when=datetime.now(UTC), session_id=session.id)

        deleted = client.delete(f"/api/sessions/{session.id}")
        assert deleted.status_code == 200
        assert deleted.json()["status"] == "deleted"

        missing = client.get(f"/api/sessions/{session.id}")
        assert missing.status_code == 404


def test_delete_schedule_and_template(tmp_path: Path) -> None:
    app = create_app(build_settings(tmp_path))
    with TestClient(app) as client:
        template = client.post(
            "/api/templates",
            json={
                "name": "Examples",
                "description": "Example template",
                "system_prompt": "You are a tutor.",
                "user_prompt_template": "Teach {topic}",
                "output_schema_version": "v1",
                "is_active": True,
                "variables": [{"name": "topic", "label": "Topic", "required": True}],
            },
        )
        template_id = template.json()["id"]
        schedule = client.post(
            "/api/schedules",
            json={
                "name": "Hourly",
                "template_id": template_id,
                "variables": {"topic": "articles"},
                "interval_minutes": 60,
                "timezone": "UTC",
                "is_active": True,
                "notification_enabled": True,
                "telegram_enabled": False,
            },
        )
        schedule_id = schedule.json()["id"]

        blocked = client.delete(f"/api/templates/{template_id}")
        assert blocked.status_code == 409

        deleted_schedule = client.delete(f"/api/schedules/{schedule_id}")
        assert deleted_schedule.status_code == 200
        assert deleted_schedule.json()["status"] == "deleted"

        deleted_template = client.delete(f"/api/templates/{template_id}")
        assert deleted_template.status_code == 200
        assert deleted_template.json()["status"] == "deleted"


def test_create_schedule_returns_400_for_invalid_timezone(tmp_path: Path) -> None:
    app = create_app(build_settings(tmp_path))
    client = TestClient(app)

    template_id = client.get("/api/templates").json()[0]["id"]
    response = client.post(
        "/api/schedules",
        json={
            "name": "Broken",
            "template_id": template_id,
            "variables": {},
            "interval_minutes": 60,
            "timezone": "Bad/Timezone",
            "is_active": True,
            "notification_enabled": True,
            "telegram_enabled": False,
        },
    )

    assert response.status_code == 400


def test_failed_session_does_not_send_telegram(tmp_path: Path) -> None:
    class FailingOpenAIClient:
        def generate_payload(
            self,
            *,
            model: str,
            system_prompt: str,
            user_prompt: str,
            prompt_cache_retention: str | None = None,
        ) -> OpenAIResult:
            raise ValueError("bad payload")

    telegram_client = FakeTelegramClient()
    app = create_app(build_settings(tmp_path))
    with TestClient(app):
        app.state.scheduler_runtime.telegram_client = telegram_client
        app.state.generation_service.client = FailingOpenAIClient()
        template = app.state.db.list_templates()[0]
        schedule = app.state.db.create_schedule(
            ScheduleUpsert(
                name="Telegram",
                template_id=template.id,
                variables={"target_language": "Spanish", "topic": "articles", "focus_area": "verbs", "difficulty": "A2"},
                interval_minutes=60,
                timezone="UTC",
                is_active=True,
                notification_enabled=True,
                telegram_enabled=False,
            )
        )

        asyncio.run(app.state.scheduler_runtime._run_schedule(schedule.id, run_source="scheduled"))

        assert telegram_client.calls == []


def test_successful_session_sends_telegram_only_when_schedule_telegram_enabled(tmp_path: Path) -> None:
    telegram_client = FakeTelegramClient()
    app = create_app(build_settings(tmp_path))
    with TestClient(app):
        app.state.scheduler_runtime.telegram_client = telegram_client
        app.state.generation_service.client = FakeOpenAIClient()
        template = app.state.db.list_templates()[0]
        disabled_schedule = app.state.db.create_schedule(
            ScheduleUpsert(
                name="No Telegram",
                template_id=template.id,
                variables={"target_language": "Spanish", "topic": "articles", "focus_area": "verbs", "difficulty": "A2"},
                interval_minutes=60,
                timezone="UTC",
                is_active=True,
                notification_enabled=True,
                telegram_enabled=False,
            )
        )
        enabled_schedule = app.state.db.create_schedule(
            ScheduleUpsert(
                name="Telegram",
                template_id=template.id,
                variables={"target_language": "Spanish", "topic": "verbs", "focus_area": "conjugation", "difficulty": "A2"},
                interval_minutes=60,
                timezone="UTC",
                is_active=True,
                notification_enabled=True,
                telegram_enabled=True,
            )
        )

        asyncio.run(app.state.scheduler_runtime._run_schedule(disabled_schedule.id, run_source="scheduled"))
        asyncio.run(app.state.scheduler_runtime._run_schedule(enabled_schedule.id, run_source="scheduled"))

        assert len(telegram_client.calls) == 1
        assert telegram_client.calls[0]["schedule"].id == enabled_schedule.id


def test_database_initialize_adds_telegram_enabled_column_with_default_false(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE prompt_templates (
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

        CREATE TABLE template_variables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            label TEXT,
            description TEXT,
            example TEXT,
            required INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            template_id INTEGER NOT NULL,
            variables_json TEXT NOT NULL,
            cron_expr TEXT NOT NULL,
            interval_minutes INTEGER,
            timezone TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            notification_enabled INTEGER NOT NULL DEFAULT 1,
            next_run_at TEXT,
            last_run_at TEXT,
            last_session_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE generated_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id INTEGER NOT NULL,
            template_id INTEGER NOT NULL,
            render_payload_json TEXT,
            model_name TEXT NOT NULL,
            prompt_snapshot_json TEXT NOT NULL,
            status TEXT NOT NULL,
            error_text TEXT,
            generated_at TEXT NOT NULL
        );

        CREATE TABLE app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        INSERT INTO schedules (
            id, name, template_id, variables_json, cron_expr, interval_minutes, timezone,
            is_active, notification_enabled, next_run_at, last_run_at, last_session_id, created_at, updated_at
        ) VALUES (
            1, 'Legacy', 1, '{}', '', 60, 'UTC', 1, 1, NULL, NULL, NULL, '2026-04-07T00:00:00+00:00', '2026-04-07T00:00:00+00:00'
        );
        """
    )
    connection.close()

    from prompt_study_notifier.db import Database
    database = Database(db_path)
    database.initialize()
    with database.connection() as migrated:
        columns = migrated.execute("PRAGMA table_info(schedules)").fetchall()
    assert any(row["name"] == "telegram_enabled" for row in columns)
    assert database.get_schedule(1).telegram_enabled is False
