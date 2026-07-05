from datetime import UTC, datetime
from pathlib import Path

from prompt_study_notifier.db import Database
from prompt_study_notifier.generation import GenerationService, SERBIAN_VARIANT_INSTRUCTION
from prompt_study_notifier.openai_client import OpenAIResult, OpenAIUsage
from prompt_study_notifier.schemas import StudyPayload, TemplateUpsert, ScheduleUpsert


class FakeClient:
    def __init__(
        self,
        *,
        should_fail: bool = False,
        responses: list[dict[str, object]] | None = None,
        usage_sequence: list[OpenAIUsage] | None = None,
    ) -> None:
        self.should_fail = should_fail
        self.responses = list(responses or [])
        self.usage_sequence = list(usage_sequence or [])
        self.last_model: str | None = None
        self.last_prompt_cache_retention: str | None = None
        self.prompts: list[str] = []

    def generate_payload(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        prompt_cache_retention: str | None = None,
    ) -> OpenAIResult:
        self.last_model = model
        self.last_prompt_cache_retention = prompt_cache_retention
        self.prompts.append(user_prompt)
        if self.should_fail:
            raise ValueError("invalid payload")
        usage = self.usage_sequence.pop(0) if self.usage_sequence else OpenAIUsage(prompt_tokens=1200, cached_tokens=0, total_tokens=1400)
        if self.responses:
            payload = StudyPayload.model_validate(self.responses.pop(0))
        else:
            payload = StudyPayload.model_validate(
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
        return OpenAIResult(payload=payload, usage=usage)


def _build_service(
    tmp_path: Path,
    *,
    should_fail: bool = False,
    responses: list[dict[str, object]] | None = None,
    usage_sequence: list[OpenAIUsage] | None = None,
    prompt_cache_retention: str = "in_memory",
    telegram_enabled: bool = False,
) -> tuple[Database, GenerationService, int, FakeClient]:
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
            interval_minutes=60,
            timezone="UTC",
            telegram_enabled=telegram_enabled,
        )
    )
    client = FakeClient(should_fail=should_fail, responses=responses, usage_sequence=usage_sequence)
    service = GenerationService(
        db=db,
        client=client,
        model="gpt-5",
        retention_limit=20,
        prompt_cache_retention=prompt_cache_retention,
    )
    return db, service, schedule.id, client


def test_generate_for_schedule_persists_successful_session(tmp_path: Path) -> None:
    db, service, schedule_id, _ = _build_service(tmp_path)
    session = service.generate_for_schedule(schedule_id)
    assert session.status == "success"
    assert session.acknowledged_at is None
    assert session.render_payload is not None
    assert session.prompt_snapshot["schedule_name"] == "Every hour"
    assert session.prompt_snapshot["template_name"] == "Template"
    assert session.generation_seconds is not None
    assert session.generation_seconds >= 0
    schedule = db.get_schedule(schedule_id)
    assert schedule.last_session_id == session.id
    assert schedule.next_run_at is None
    assert schedule.awaiting_acknowledgement is True
    assert schedule.pending_acknowledgement_count == 1


def test_generate_for_schedule_adds_serbian_variant_instruction(tmp_path: Path) -> None:
    db, service, schedule_id, client = _build_service(tmp_path)
    schedule = db.get_schedule(schedule_id)
    db.update_schedule(
        schedule_id,
        ScheduleUpsert(
            name=schedule.name,
            template_id=schedule.template_id,
            variables={"target_language": "Serbian", "topic": "work vocabulary"},
            interval_minutes=schedule.interval_minutes,
            timezone=schedule.timezone,
            telegram_enabled=schedule.telegram_enabled,
        ),
    )

    session = service.generate_for_schedule(schedule_id)

    assert session.status == "success"
    assert SERBIAN_VARIANT_INSTRUCTION in client.prompts[-1]
    assert "Avoid Croatian- or Bosnian-specific vocabulary" in session.prompt_snapshot["rendered_user_prompt"]


def test_generate_for_schedule_does_not_add_serbian_variant_instruction_for_other_languages(tmp_path: Path) -> None:
    _, service, schedule_id, client = _build_service(tmp_path)

    session = service.generate_for_schedule(schedule_id)

    assert session.status == "success"
    assert SERBIAN_VARIANT_INSTRUCTION not in client.prompts[-1]


def test_generate_for_schedule_keeps_next_run_for_telegram_enabled_schedule(tmp_path: Path) -> None:
    db, service, schedule_id, _ = _build_service(tmp_path, telegram_enabled=True)
    session = service.generate_for_schedule(schedule_id)
    assert session.status == "success"
    schedule = db.get_schedule(schedule_id)
    assert schedule.next_run_at is not None
    assert schedule.awaiting_acknowledgement is True
    assert schedule.pending_acknowledgement_count == 1


def test_generate_for_schedule_persists_failure(tmp_path: Path) -> None:
    db, service, schedule_id, _ = _build_service(tmp_path, should_fail=True)
    session = service.generate_for_schedule(schedule_id)
    assert session.status == "failed"
    assert session.error_text == "invalid payload"
    assert session.generation_seconds is not None
    schedule = db.get_schedule(schedule_id)
    assert schedule.next_run_at is not None
    assert schedule.awaiting_acknowledgement is False
    assert schedule.pending_acknowledgement_count == 0


def test_generate_for_schedule_uses_active_model_setting(tmp_path: Path) -> None:
    db, service, schedule_id, _ = _build_service(tmp_path)
    db.set_app_setting("active_model", "gpt-5.4-mini")
    session = service.generate_for_schedule(schedule_id)
    assert session.model_name == "gpt-5.4-mini"


def test_build_live_event_marks_manual_runs(tmp_path: Path) -> None:
    _, service, schedule_id, _ = _build_service(tmp_path)
    session = service.generate_for_schedule(schedule_id)
    event = service.build_live_event(session, run_source="manual")
    assert event.run_source == "manual"


def test_list_schedule_terms_returns_distinct_success_terms_for_one_schedule(tmp_path: Path) -> None:
    db, _, schedule_id, _ = _build_service(tmp_path)
    template = db.list_templates()[0]
    other_schedule = db.create_schedule(
        ScheduleUpsert(
            name="Other",
            template_id=template.id,
            variables={"target_language": "German", "topic": "travel"},
            interval_minutes=60,
            timezone="UTC",
        )
    )
    success_payload = StudyPayload.model_validate(
        {
            "title": "Card",
            "topic": "Topic",
            "summary": "Summary",
            "focus_hint": None,
            "items": [
                {
                    "term": "  Erfahrung  ",
                    "translation": "experience",
                    "explanation": "desc",
                    "example_source": "Das ist eine Erfahrung.",
                    "example_target": "That is an experience.",
                    "notes": "note",
                    "tags": [],
                },
                {
                    "term": "  Fahrkarte  ",
                    "translation": "ticket",
                    "explanation": "desc",
                    "example_source": "Ich kaufe eine Fahrkarte.",
                    "example_target": "I am buying a ticket.",
                    "notes": "travel context",
                    "tags": [],
                }
            ],
        }
    )
    duplicate_payload = success_payload.model_copy(
        update={"items": [success_payload.items[0].model_copy(update={"term": "erfahrung"})]}
    )
    empty_items_payload = success_payload.model_copy(update={"items": []})
    db.create_session(
        schedule_id=schedule_id,
        template_id=template.id,
        render_payload=success_payload,
        model_name="gpt-5",
        prompt_snapshot={},
        status="success",
        error_text=None,
    )
    db.create_session(
        schedule_id=schedule_id,
        template_id=template.id,
        render_payload=duplicate_payload,
        model_name="gpt-5",
        prompt_snapshot={},
        status="success",
        error_text=None,
    )
    db.create_session(
        schedule_id=schedule_id,
        template_id=template.id,
        render_payload=None,
        model_name="gpt-5",
        prompt_snapshot={},
        status="failed",
        error_text="bad",
    )
    db.create_session(
        schedule_id=schedule_id,
        template_id=template.id,
        render_payload=empty_items_payload,
        model_name="gpt-5",
        prompt_snapshot={},
        status="success",
        error_text=None,
    )
    db.create_session(
        schedule_id=other_schedule.id,
        template_id=template.id,
        render_payload=success_payload.model_copy(
            update={"items": [success_payload.items[0].model_copy(update={"term": "Wohnung"})]}
        ),
        model_name="gpt-5",
        prompt_snapshot={},
        status="success",
        error_text=None,
    )

    assert db.list_schedule_terms(schedule_id) == ["erfahrung", "Fahrkarte"]
    assert db.list_schedule_history_items(schedule_id) == [
        {
            "term": "erfahrung",
            "example_source": "Das ist eine Erfahrung.",
            "example_target": "That is an experience.",
            "notes": "note",
        },
        {
            "term": "Fahrkarte",
            "example_source": "Ich kaufe eine Fahrkarte.",
            "example_target": "I am buying a ticket.",
            "notes": "travel context",
        },
    ]


def test_generate_for_schedule_appends_prior_terms_to_prompt(tmp_path: Path) -> None:
    db, service, schedule_id, client = _build_service(
        tmp_path,
        responses=[
            {
                "title": "Card",
                "topic": "Topic",
                "summary": "Summary",
                "focus_hint": None,
                "items": [
                    {
                        "term": "Reserva",
                        "translation": "reservation",
                        "explanation": "desc",
                        "example_source": "Tengo una reserva.",
                        "example_target": "I have a reservation.",
                        "notes": "note",
                        "tags": [],
                    }
                ],
            }
        ],
    )
    db.create_session(
        schedule_id=schedule_id,
        template_id=db.list_templates()[0].id,
        render_payload=StudyPayload.model_validate(
            {
                "title": "Seed",
                "topic": "Topic",
                "summary": "Summary",
                "focus_hint": None,
                "items": [
                    {
                        "term": "Quisiera pedir",
                        "translation": "I would like to order",
                        "explanation": "desc",
                        "example_source": "Quisiera pedir una sopa.",
                        "example_target": "I would like to order a soup.",
                        "notes": "note",
                        "tags": [],
                    }
                ],
            }
        ),
        model_name="gpt-5",
        prompt_snapshot={},
        status="success",
        error_text=None,
    )

    session = service.generate_for_schedule(schedule_id)

    assert session.status == "success"
    assert client.prompts[-1].startswith("Teach Spanish about restaurant conversations")
    assert "Recent generated items to avoid:" in client.prompts[-1]
    assert "- term: Quisiera pedir | example: Quisiera pedir una sopa." in client.prompts[-1]
    assert "Avoid reusing listed terms, verbs, example sentences, sentence templates" in client.prompts[-1]
    assert session.prompt_snapshot["prior_terms"] == ["Quisiera pedir"]
    assert session.prompt_snapshot["prior_items"] == [
        {
            "term": "Quisiera pedir",
            "example_source": "Quisiera pedir una sopa.",
            "example_target": "I would like to order a soup.",
            "notes": "note",
        }
    ]
    assert session.prompt_snapshot["duplicate_term_detected"] is False


def test_generate_for_schedule_retries_once_for_duplicate_term(tmp_path: Path) -> None:
    responses = [
        {
            "title": "Card",
            "topic": "Topic",
            "summary": "Summary",
            "focus_hint": None,
            "items": [
                {
                    "term": "Quisiera pedir",
                    "translation": "I would like to order",
                    "explanation": "desc",
                    "example_source": "Quisiera pedir agua.",
                    "example_target": "I would like to order water.",
                    "notes": "note",
                    "tags": [],
                }
            ],
        },
        {
            "title": "Card",
            "topic": "Topic",
            "summary": "Summary",
            "focus_hint": None,
            "items": [
                {
                    "term": "Reserva",
                    "translation": "reservation",
                    "explanation": "desc",
                    "example_source": "Tengo una reserva.",
                    "example_target": "I have a reservation.",
                    "notes": "note",
                    "tags": [],
                }
            ],
        },
    ]
    db, service, schedule_id, client = _build_service(tmp_path, responses=responses)
    db.create_session(
        schedule_id=schedule_id,
        template_id=db.list_templates()[0].id,
        render_payload=StudyPayload.model_validate(
            {
                "title": "Seed",
                "topic": "Topic",
                "summary": "Summary",
                "focus_hint": None,
                "items": [
                    {
                        "term": "Quisiera pedir",
                        "translation": "I would like to order",
                        "explanation": "desc",
                        "example_source": "Quisiera pedir una sopa.",
                        "example_target": "I would like to order a soup.",
                        "notes": "note",
                        "tags": [],
                    }
                ],
            }
        ),
        model_name="gpt-5",
        prompt_snapshot={},
        status="success",
        error_text=None,
    )

    session = service.generate_for_schedule(schedule_id)

    assert session.status == "success"
    assert session.render_payload is not None
    assert session.render_payload.items[0].term == "Reserva"
    assert len(client.prompts) == 2
    assert 'The word "Quisiera pedir" is forbidden because it was already generated.' in client.prompts[1]
    assert session.prompt_snapshot["duplicate_term_detected"] is True
    assert len(session.prompt_snapshot["generation_attempts"]) == 2


def test_generate_for_schedule_fails_when_duplicate_repeats_after_retry(tmp_path: Path) -> None:
    duplicate_response = {
        "title": "Card",
        "topic": "Topic",
        "summary": "Summary",
        "focus_hint": None,
        "items": [
            {
                "term": "Quisiera pedir",
                "translation": "I would like to order",
                "explanation": "desc",
                "example_source": "Quisiera pedir agua.",
                "example_target": "I would like to order water.",
                "notes": "note",
                "tags": [],
            }
        ],
    }
    db, service, schedule_id, client = _build_service(
        tmp_path,
        responses=[duplicate_response, duplicate_response],
    )
    db.create_session(
        schedule_id=schedule_id,
        template_id=db.list_templates()[0].id,
        render_payload=StudyPayload.model_validate(duplicate_response),
        model_name="gpt-5",
        prompt_snapshot={},
        status="success",
        error_text=None,
    )

    session = service.generate_for_schedule(schedule_id)

    assert session.status == "failed"
    assert session.error_text == 'Generated duplicate study-card term after retry: "Quisiera pedir".'
    assert session.prompt_snapshot["duplicate_term_detected"] is True
    assert len(session.prompt_snapshot["generation_attempts"]) == 2
    assert len(client.prompts) == 2


def test_generate_for_schedule_fails_when_primary_term_is_missing(tmp_path: Path) -> None:
    db, service, schedule_id, _ = _build_service(
        tmp_path,
        responses=[
            {
                "title": "Card",
                "topic": "Topic",
                "summary": "Summary",
                "focus_hint": None,
                "items": [],
            }
        ],
    )

    session = service.generate_for_schedule(schedule_id)

    assert session.status == "failed"
    assert session.error_text == "Generated payload did not include any study item terms."


def test_generate_for_schedule_limits_prior_terms_to_most_recent_30(tmp_path: Path) -> None:
    responses = [
        {
            "title": "Fresh card",
            "topic": "Topic",
            "summary": "Summary",
            "focus_hint": None,
            "items": [
                {
                    "term": "Fresh term",
                    "translation": "fresh translation",
                    "explanation": "desc",
                    "example_source": "Fresh source.",
                    "example_target": "Fresh target.",
                    "notes": "note",
                    "tags": [],
                }
            ],
        }
    ]
    db, service, schedule_id, client = _build_service(tmp_path, responses=responses)
    template_id = db.list_templates()[0].id
    for index in range(35):
        db.create_session(
            schedule_id=schedule_id,
            template_id=template_id,
            render_payload=StudyPayload.model_validate(
                {
                    "title": f"Seed {index}",
                    "topic": "Topic",
                    "summary": "Summary",
                    "focus_hint": None,
                    "items": [
                        {
                            "term": f"Term {index}",
                            "translation": f"Translation {index}",
                            "explanation": "desc",
                            "example_source": f"Source {index}",
                            "example_target": f"Target {index}",
                            "notes": "note",
                            "tags": [],
                        }
                    ],
                }
            ),
            model_name="gpt-5",
            prompt_snapshot={},
            status="success",
            error_text=None,
        )

    session = service.generate_for_schedule(schedule_id)

    assert session.status == "success"
    assert session.prompt_snapshot["prior_terms"] == [f"Term {index}" for index in range(34, 4, -1)]
    assert "Recent generated items to avoid:" in client.prompts[-1]
    assert "- term: Term 34 | example: Source 34 | translation: Target 34 | notes: note" in client.prompts[-1]
    assert "Term 4" not in client.prompts[-1]


def test_acknowledging_successful_session_reschedules_from_ack_time(tmp_path: Path) -> None:
    db, service, schedule_id, _ = _build_service(tmp_path)
    session = service.generate_for_schedule(schedule_id)

    acknowledged_at = datetime(2026, 3, 20, 10, 5, tzinfo=UTC)
    acknowledged_session = db.acknowledge_session(session.id, acknowledged_at=acknowledged_at)

    assert acknowledged_session.acknowledged_at == acknowledged_at.isoformat()
    schedule = db.get_schedule(schedule_id)
    assert schedule.awaiting_acknowledgement is False
    assert schedule.pending_acknowledgement_count == 0
    assert schedule.next_run_at == datetime(2026, 3, 20, 11, 5, tzinfo=UTC).isoformat()


def test_acknowledging_one_of_multiple_pending_sessions_keeps_schedule_blocked(tmp_path: Path) -> None:
    db, service, schedule_id, _ = _build_service(tmp_path)
    template_id = db.list_templates()[0].id

    first = db.create_session(
        schedule_id=schedule_id,
        template_id=template_id,
        render_payload=StudyPayload.model_validate(
            {
                "title": "First",
                "topic": "Topic",
                "summary": "Summary",
                "focus_hint": None,
                "items": [{"term": "Uno"}],
            }
        ),
        model_name="gpt-5",
        prompt_snapshot={},
        status="success",
        error_text=None,
        generated_at=datetime(2026, 3, 20, 9, 0, tzinfo=UTC),
    )
    db.update_schedule_after_run(schedule_id, when=datetime(2026, 3, 20, 9, 0, tzinfo=UTC), session_id=first.id)
    second = db.create_session(
        schedule_id=schedule_id,
        template_id=template_id,
        render_payload=StudyPayload.model_validate(
            {
                "title": "Second",
                "topic": "Topic",
                "summary": "Summary",
                "focus_hint": None,
                "items": [{"term": "Dos"}],
            }
        ),
        model_name="gpt-5",
        prompt_snapshot={},
        status="success",
        error_text=None,
        generated_at=datetime(2026, 3, 20, 9, 30, tzinfo=UTC),
    )
    db.update_schedule_after_run(schedule_id, when=datetime(2026, 3, 20, 9, 30, tzinfo=UTC), session_id=second.id)

    db.acknowledge_session(first.id, acknowledged_at=datetime(2026, 3, 20, 10, 5, tzinfo=UTC))

    schedule = db.get_schedule(schedule_id)
    assert schedule.awaiting_acknowledgement is True
    assert schedule.pending_acknowledgement_count == 1
    assert schedule.next_run_at is None

    db.acknowledge_session(second.id, acknowledged_at=datetime(2026, 3, 20, 10, 35, tzinfo=UTC))

    schedule = db.get_schedule(schedule_id)
    assert schedule.awaiting_acknowledgement is False
    assert schedule.pending_acknowledgement_count == 0
    assert schedule.next_run_at == datetime(2026, 3, 20, 11, 35, tzinfo=UTC).isoformat()


def test_prune_sessions_preserves_pending_acknowledgements(tmp_path: Path) -> None:
    db, _, schedule_id, _ = _build_service(tmp_path)
    template_id = db.list_templates()[0].id

    pending = db.create_session(
        schedule_id=schedule_id,
        template_id=template_id,
        render_payload=StudyPayload.model_validate(
            {
                "title": "Pending",
                "topic": "Topic",
                "summary": "Summary",
                "focus_hint": None,
                "items": [{"term": "Pending"}],
            }
        ),
        model_name="gpt-5",
        prompt_snapshot={},
        status="success",
        error_text=None,
        generated_at=datetime(2026, 3, 20, 9, 0, tzinfo=UTC),
    )
    acknowledged_ids = []
    for index in range(3):
        session = db.create_session(
            schedule_id=schedule_id,
            template_id=template_id,
            render_payload=StudyPayload.model_validate(
                {
                    "title": f"Acknowledged {index}",
                    "topic": "Topic",
                    "summary": "Summary",
                    "focus_hint": None,
                    "items": [{"term": f"Ack {index}"}],
                }
            ),
            model_name="gpt-5",
            prompt_snapshot={},
            status="success",
            error_text=None,
            generated_at=datetime(2026, 3, 20, 10 + index, 0, tzinfo=UTC),
        )
        db.acknowledge_session(session.id, acknowledged_at=datetime(2026, 3, 20, 13 + index, 0, tzinfo=UTC))
        acknowledged_ids.append(session.id)

    db.prune_sessions(limit=1)

    summaries = db.list_sessions(limit=10)
    remaining_ids = {session.id for session in summaries}
    assert pending.id in remaining_ids
    assert acknowledged_ids[-1] in remaining_ids
    assert acknowledged_ids[0] not in remaining_ids
    assert acknowledged_ids[1] not in remaining_ids
