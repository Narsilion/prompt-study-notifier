from pathlib import Path

from prompt_study_notifier.db import Database
from prompt_study_notifier.generation import GenerationService
from prompt_study_notifier.schemas import StudyPayload, TemplateUpsert, ScheduleUpsert


class FakeClient:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.last_model: str | None = None

    def generate_payload(self, *, model: str, system_prompt: str, user_prompt: str) -> StudyPayload:
        self.last_model = model
        if self.should_fail:
            raise ValueError("invalid payload")
        return StudyPayload.model_validate(
            {
                "title": "Spanish conversation drill",
                "topic": "Restaurant conversations",
                "summary": "Practice polite requests in everyday restaurant situations.",
                "focus_hint": "Pay attention to polite forms and useful service vocabulary.",
                "items": [
                    {
                        "term": "Quisiera pedir",
                        "translation": "I would like to order",
                        "explanation": "Polite phrase for ordering food or drinks.",
                        "example_source": "Quisiera pedir una sopa, por favor.",
                        "example_target": "I would like to order a soup, please.",
                        "notes": "Useful polite opener in restaurants.",
                        "tags": ["restaurant", "politeness"],
                    }
                ],
            }
        )


def _build_service(tmp_path: Path, *, should_fail: bool = False) -> tuple[Database, GenerationService, int]:
    db = Database(tmp_path / "study.db")
    db.initialize()
    template = db.create_template(
        TemplateUpsert(
            name="Template",
            description=None,
            system_prompt="You are a tutor.",
            user_prompt_template="Teach {target_language} about {topic}",
            variables=[{"name": "target_language"}, {"name": "topic"}],
        )
    )
    schedule = db.create_schedule(
        ScheduleUpsert(
            name="Every hour",
            template_id=template.id,
            variables={"target_language": "Spanish", "topic": "restaurant conversations"},
            cron_expr="*/30 * * * *",
            timezone="UTC",
        )
    )
    client = FakeClient(should_fail=should_fail)
    service = GenerationService(db=db, client=client, model="gpt-5", retention_limit=20)
    return db, service, schedule.id


def test_generate_for_schedule_persists_successful_session(tmp_path: Path) -> None:
    db, service, schedule_id = _build_service(tmp_path)
    session = service.generate_for_schedule(schedule_id)
    assert session.status == "success"
    assert session.render_payload is not None
    assert session.generation_seconds is not None
    assert session.generation_seconds >= 0
    schedule = db.get_schedule(schedule_id)
    assert schedule.last_session_id == session.id


def test_generate_for_schedule_persists_failure(tmp_path: Path) -> None:
    _, service, schedule_id = _build_service(tmp_path, should_fail=True)
    session = service.generate_for_schedule(schedule_id)
    assert session.status == "failed"
    assert session.error_text == "invalid payload"
    assert session.generation_seconds is not None


def test_generate_for_schedule_uses_active_model_setting(tmp_path: Path) -> None:
    db, service, schedule_id = _build_service(tmp_path)
    db.set_app_setting("active_model", "gpt-5.4-mini")
    session = service.generate_for_schedule(schedule_id)
    assert session.model_name == "gpt-5.4-mini"


def test_build_live_event_marks_manual_runs(tmp_path: Path) -> None:
    _, service, schedule_id = _build_service(tmp_path)
    session = service.generate_for_schedule(schedule_id)
    event = service.build_live_event(session, run_source="manual")
    assert event.run_source == "manual"
