from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter

from prompt_study_notifier.db import Database
from prompt_study_notifier.openai_client import OpenAIClient, OpenAIClientError, OpenAIUsage
from prompt_study_notifier.rendering import MissingTemplateVariableError, extract_variables, render_prompt
from prompt_study_notifier.schemas import LiveEvent, SessionRecord


class GenerationError(RuntimeError):
    """Raised when generation fails before persistence."""


def _normalize_term(term: str) -> str:
    return term.strip().casefold()


def _extract_primary_term(payload: object) -> str:
    if not hasattr(payload, "items") or not payload.items:
        raise ValueError("Generated payload did not include a first study item term.")
    term = payload.items[0].term.strip()
    if not term:
        raise ValueError("Generated payload did not include a first study item term.")
    return term


@dataclass(slots=True)
class GenerationService:
    db: Database
    client: OpenAIClient
    model: str
    retention_limit: int
    prompt_cache_retention: str = "in_memory"
    uniqueness_history_limit: int = 30

    def preview_prompt(self, *, user_prompt_template: str, variables: dict[str, object]) -> tuple[str, list[str]]:
        variable_names = extract_variables(user_prompt_template)
        resolved_prompt = render_prompt(user_prompt_template, variables)
        return resolved_prompt, variable_names

    def _build_prompt_with_history(
        self,
        rendered_prompt: str,
        *,
        prior_terms: list[str],
        forbidden_term: str | None = None,
    ) -> str:
        if not prior_terms:
            return rendered_prompt
        history_block = [
            "",
            "Do not repeat any previously generated study-card word from this schedule.",
            f"Previously used words: {', '.join(prior_terms)}",
            "Return a different real word. If a candidate would repeat one of the listed words, choose another one.",
        ]
        if forbidden_term:
            history_block.append(f'The word "{forbidden_term}" is forbidden because it was already generated. Choose a different word.')
        return rendered_prompt + "\n".join(history_block)

    def _resolve_prompt_cache_retention(self, model: str) -> tuple[str, str | None]:
        if self.prompt_cache_retention != "24h":
            return "in_memory", None
        if model.startswith("gpt-5") or model.startswith("gpt-4.1"):
            return "24h", None
        return "in_memory", f'Model "{model}" does not use 24h prompt cache retention; falling back to in_memory.'

    def _usage_snapshot(self, usage: OpenAIUsage) -> dict[str, int | float | None]:
        prompt_tokens = usage.prompt_tokens
        cached_tokens = usage.cached_tokens or 0
        uncached_prompt_tokens = None if prompt_tokens is None else max(prompt_tokens - cached_tokens, 0)
        cache_hit_ratio = None
        if prompt_tokens and prompt_tokens > 0:
            cache_hit_ratio = cached_tokens / prompt_tokens
        return {
            "prompt_tokens": prompt_tokens,
            "uncached_prompt_tokens": uncached_prompt_tokens,
            "cached_tokens": cached_tokens,
            "total_tokens": usage.total_tokens,
            "cache_hit_ratio": cache_hit_ratio,
        }

    def generate_for_schedule(self, schedule_id: int) -> SessionRecord:
        schedule = self.db.get_schedule(schedule_id)
        template = self.db.get_template(schedule.template_id)
        run_time = datetime.now(UTC)
        started = perf_counter()
        active_model = self.db.get_active_model(self.model)
        applied_prompt_cache_retention, prompt_cache_retention_note = self._resolve_prompt_cache_retention(active_model)
        prior_terms = self.db.list_schedule_terms(schedule.id)[: self.uniqueness_history_limit]
        generation_attempts: list[dict[str, object]] = []
        prompt_snapshot = {
            "schedule_name": schedule.name,
            "template_name": template.name,
            "system_prompt": template.system_prompt,
            "user_prompt_template": template.user_prompt_template,
            "variables": schedule.variables,
            "variable_names": template.variable_names,
            "active_model": active_model,
            "prior_terms": prior_terms,
            "generation_attempts": generation_attempts,
            "duplicate_term_detected": False,
            "prompt_cache": {
                "requested_retention": self.prompt_cache_retention,
                "applied_retention": applied_prompt_cache_retention,
                "note": prompt_cache_retention_note,
            },
        }
        try:
            rendered_prompt = render_prompt(template.user_prompt_template, schedule.variables)
            duplicate_term: str | None = None
            render_payload = None
            final_prompt = rendered_prompt
            prior_term_keys = {_normalize_term(term) for term in prior_terms}
            for attempt_number in (1, 2):
                attempt_prompt = self._build_prompt_with_history(
                    rendered_prompt,
                    prior_terms=prior_terms,
                    forbidden_term=duplicate_term,
                )
                final_prompt = attempt_prompt
                result = self.client.generate_payload(
                    model=active_model,
                    system_prompt=template.system_prompt,
                    user_prompt=attempt_prompt,
                    prompt_cache_retention=applied_prompt_cache_retention,
                )
                render_payload = result.payload
                usage_snapshot = self._usage_snapshot(result.usage)
                primary_term = _extract_primary_term(render_payload)
                generation_attempts.append(
                    {
                        "attempt": attempt_number,
                        "user_prompt": attempt_prompt,
                        "term": primary_term,
                        "usage": usage_snapshot,
                    }
                )
                prompt_snapshot["openai_usage"] = usage_snapshot
                if _normalize_term(primary_term) not in prior_term_keys:
                    break
                duplicate_term = primary_term
                prompt_snapshot["duplicate_term_detected"] = True
                if attempt_number == 2:
                    raise ValueError(
                        f'Generated duplicate study-card term after retry: "{primary_term}".'
                    )
            if render_payload is None:
                raise ValueError("Generation did not return a study payload.")
            prompt_snapshot["rendered_user_prompt"] = final_prompt
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
