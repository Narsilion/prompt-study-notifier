from pathlib import Path

from fastapi.testclient import TestClient

from prompt_study_notifier.app import create_app
from prompt_study_notifier.openai_client import OpenAIUsage
from prompt_study_notifier.schemas import ScheduleUpsert, StudyPayload
from prompt_study_notifier.settings import Settings


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


def test_prompt_cache_metrics_endpoint_aggregates_cached_runs(tmp_path: Path) -> None:
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
        db.create_session(
            schedule_id=schedule["id"],
            template_id=template["id"],
            render_payload=build_payload(),
            model_name="gpt-5",
            prompt_snapshot={
                "prompt_cache": {"applied_retention": "in_memory"},
                "openai_usage": {
                    "prompt_tokens": 1500,
                    "uncached_prompt_tokens": 300,
                    "cached_tokens": 1200,
                    "cache_hit_ratio": 0.8,
                },
            },
            status="success",
            error_text=None,
            generation_seconds=1.2,
        )
        db.create_session(
            schedule_id=schedule["id"],
            template_id=template["id"],
            render_payload=build_payload("Articulo"),
            model_name="gpt-5",
            prompt_snapshot={
                "prompt_cache": {"applied_retention": "in_memory"},
                "openai_usage": {
                    "prompt_tokens": 1500,
                    "uncached_prompt_tokens": 1500,
                    "cached_tokens": 0,
                    "cache_hit_ratio": 0.0,
                },
            },
            status="success",
            error_text=None,
            generation_seconds=2.4,
        )

        response = client.get("/api/metrics/prompt-cache?limit=10")

        assert response.status_code == 200
        payload = response.json()
        assert payload["total_sessions"] == 2
        assert payload["sessions_with_usage"] == 2
        assert payload["sessions_with_cache_hit"] == 1
        assert payload["prompt_tokens"] == 3000
        assert payload["uncached_prompt_tokens"] == 1800
        assert payload["cached_tokens"] == 1200
        assert payload["cache_hit_ratio"] == 0.4
        assert len(payload["runs"]) == 2


def test_generation_records_prompt_cache_usage(tmp_path: Path) -> None:
    app = create_app(build_settings(tmp_path))
    with TestClient(app):
        db = app.state.db
        service = app.state.generation_service
        template = db.list_templates()[0]
        schedule = db.create_schedule(
            ScheduleUpsert(
                name="Every hour",
                template_id=template.id,
                variables={
                    "target_language": "Spanish",
                    "topic": "restaurant conversations",
                    "focus_area": "verbs",
                    "difficulty": "A2",
                },
                interval_minutes=60,
                timezone="UTC",
            )
        )
        captured_retention: list[str | None] = []

        class FakeClient:
            def generate_payload(self, *, model: str, system_prompt: str, user_prompt: str, prompt_cache_retention: str | None = None):
                from prompt_study_notifier.openai_client import OpenAIResult

                captured_retention.append(prompt_cache_retention)
                return OpenAIResult(
                    payload=StudyPayload.model_validate(
                        {
                            "title": "Spanish conversation drill",
                            "topic": "Restaurant conversations",
                            "summary": "Practice polite requests.",
                            "focus_hint": "Polite forms.",
                            "items": [{"term": "Reserva", "translation": "reservation"}],
                        }
                    ),
                    usage=OpenAIUsage(prompt_tokens=1400, cached_tokens=1050, total_tokens=1600),
                )

        service.client = FakeClient()
        session = service.generate_for_schedule(schedule.id)

        assert session.prompt_snapshot["openai_usage"]["prompt_tokens"] == 1400
        assert session.prompt_snapshot["openai_usage"]["cached_tokens"] == 1050
        assert session.prompt_snapshot["openai_usage"]["uncached_prompt_tokens"] == 350
        assert session.prompt_snapshot["prompt_cache"]["applied_retention"] == "in_memory"
        assert captured_retention == ["in_memory"]


def test_generation_downgrades_unsupported_24h_prompt_cache_retention(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    settings.prompt_cache_retention = "24h"
    app = create_app(settings)
    with TestClient(app):
        db = app.state.db
        db.set_app_setting("active_model", "o4-mini")
        service = app.state.generation_service
        template = db.list_templates()[0]
        schedule = db.create_schedule(
            ScheduleUpsert(
                name="Every hour",
                template_id=template.id,
                variables={
                    "target_language": "Spanish",
                    "topic": "restaurant conversations",
                    "focus_area": "verbs",
                    "difficulty": "A2",
                },
                interval_minutes=60,
                timezone="UTC",
            )
        )
        captured_retention: list[str | None] = []

        class FakeClient:
            def generate_payload(self, *, model: str, system_prompt: str, user_prompt: str, prompt_cache_retention: str | None = None):
                from prompt_study_notifier.openai_client import OpenAIResult

                captured_retention.append(prompt_cache_retention)
                return OpenAIResult(
                    payload=StudyPayload.model_validate(
                        {
                            "title": "Spanish conversation drill",
                            "topic": "Restaurant conversations",
                            "summary": "Practice polite requests.",
                            "focus_hint": "Polite forms.",
                            "items": [{"term": "Reserva", "translation": "reservation"}],
                        }
                    ),
                    usage=OpenAIUsage(prompt_tokens=1200, cached_tokens=600, total_tokens=1400),
                )

        service.client = FakeClient()
        session = service.generate_for_schedule(schedule.id)

        assert session.prompt_snapshot["prompt_cache"]["requested_retention"] == "24h"
        assert session.prompt_snapshot["prompt_cache"]["applied_retention"] == "in_memory"
        assert "falling back to in_memory" in session.prompt_snapshot["prompt_cache"]["note"]
        assert captured_retention == ["in_memory"]
