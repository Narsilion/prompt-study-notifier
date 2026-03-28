from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter

from prompt_study_notifier.db import Database
from prompt_study_notifier.openai_client import OpenAIClient, OpenAIClientError
from prompt_study_notifier.rendering import MissingTemplateVariableError, extract_variables, render_prompt
from prompt_study_notifier.schemas import LiveEvent, SessionRecord


class GenerationError(RuntimeError):
    """Raised when generation fails before persistence."""


@dataclass(slots=True)
class GenerationService:
    db: Database
    client: OpenAIClient
    model: str
    retention_limit: int

    def preview_prompt(self, *, user_prompt_template: str, variables: dict[str, object]) -> tuple[str, list[str]]:
        variable_names = extract_variables(user_prompt_template)
        resolved_prompt = render_prompt(user_prompt_template, variables)
        return resolved_prompt, variable_names

    def generate_for_schedule(self, schedule_id: int) -> SessionRecord:
        schedule = self.db.get_schedule(schedule_id)
        template = self.db.get_template(schedule.template_id)
        run_time = datetime.now(UTC)
        started = perf_counter()
        active_model = self.db.get_active_model(self.model)
        prompt_snapshot = {
            "system_prompt": template.system_prompt,
            "user_prompt_template": template.user_prompt_template,
            "variables": schedule.variables,
            "variable_names": template.variable_names,
            "active_model": active_model,
        }
        try:
            rendered_prompt = render_prompt(template.user_prompt_template, schedule.variables)
            prompt_snapshot["rendered_user_prompt"] = rendered_prompt
            render_payload = self.client.generate_payload(
                model=active_model,
                system_prompt=template.system_prompt,
                user_prompt=rendered_prompt,
            )
            session = self.db.create_session(
                schedule_id=schedule.id,
                template_id=template.id,
                render_payload=render_payload,
                model_name=active_model,
                prompt_snapshot=prompt_snapshot,
                status="success",
                error_text=None,
                generated_at=run_time,
                generation_seconds=perf_counter() - started,
            )
        except (MissingTemplateVariableError, OpenAIClientError, ValueError) as exc:
            session = self.db.create_session(
                schedule_id=schedule.id,
                template_id=template.id,
                render_payload=None,
                model_name=active_model,
                prompt_snapshot=prompt_snapshot,
                status="failed",
                error_text=str(exc),
                generated_at=run_time,
                generation_seconds=perf_counter() - started,
            )
        self.db.update_schedule_after_run(schedule.id, when=run_time, session_id=session.id)
        self.db.prune_sessions(limit=self.retention_limit)
        return self.db.get_session(session.id)

    def build_live_event(self, session: SessionRecord, *, run_source: str = "scheduled") -> LiveEvent:
        schedule = self.db.get_schedule(session.schedule_id)
        return LiveEvent(type="session.created", session=session, schedule=schedule, run_source=run_source)
