from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from prompt_study_notifier.app import create_app
from prompt_study_notifier.schemas import StudyPayload
from prompt_study_notifier.settings import Settings


def build_settings(tmp_path: Path) -> Settings:
    return Settings(
        project_root=tmp_path,
        db_path=tmp_path / "app.db",
        host="127.0.0.1",
        port=8765,
        openai_api_key=None,
        model="gpt-5",
        retention_limit=20,
        scheduler_poll_seconds=60,
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
    assert "Template Editor" not in dashboard.text
    assert "Existing Templates" not in dashboard.text

    templates_page = client.get("/templates")
    assert templates_page.status_code == 200
    assert "Template Editor" in templates_page.text
    assert "Existing Templates" in templates_page.text

    settings = client.get("/api/settings")
    assert settings.status_code == 200
    assert settings.json()["active_model"] == "gpt-5"
    assert "gpt-5.4-mini" in settings.json()["available_models"]

    updated_settings = client.put("/api/settings", json={"active_model": "gpt-5.4-mini"})
    assert updated_settings.status_code == 200
    assert updated_settings.json()["active_model"] == "gpt-5.4-mini"

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
        },
    )
    assert schedule.status_code == 200

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
        },
    )

    assert response.status_code == 400
