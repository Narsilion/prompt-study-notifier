from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter

from prompt_study_notifier.db import Database
from prompt_study_notifier.openai_client import AIClientError, OpenAIClient, OpenAIUsage
from prompt_study_notifier.rendering import MissingTemplateVariableError, extract_variables, render_prompt
from prompt_study_notifier.schemas import LiveEvent, SessionRecord


class GenerationError(RuntimeError):
    """Raised when generation fails before persistence."""


SERBIAN_VARIANT_INSTRUCTION = (
    "Serbian variant requirements: If the target language is Serbian, use standard Serbian only. "
    "Default to Ekavian Serbian as used in Serbia unless the schedule explicitly requests another Serbian standard. "
    "Avoid Croatian- or Bosnian-specific vocabulary, spelling, and constructions. "
    "Keep all Serbian terms and examples consistent with the same Serbian variant."
)
SERBIAN_MARKERS = ("serbian", "srpski", "srpska", "srpsko", "српски", "српска", "српско")


def _normalize_term(term: str) -> str:
    return term.strip().casefold()


def _extract_item_terms(payload: object) -> list[str]:
    if not hasattr(payload, "items") or not payload.items:
        raise ValueError("Generated payload did not include any study item terms.")
    terms = [item.term.strip() for item in payload.items if item.term.strip()]
    if not terms:
        raise ValueError("Generated payload did not include any study item terms.")
    return terms


def _mentions_serbian(value: object) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.casefold()
    return any(marker in normalized for marker in SERBIAN_MARKERS)


def _should_apply_serbian_variant_instruction(*, schedule_name: str, template_name: str, variables: dict[str, object]) -> bool:
    if _mentions_serbian(schedule_name) or _mentions_serbian(template_name):
        return True
    for key, value in variables.items():
        if "language" in key.casefold() and _mentions_serbian(value):
            return True
    return False


def _apply_language_variant_instructions(
    rendered_prompt: str,
    *,
    schedule_name: str,
    template_name: str,
    variables: dict[str, object],
) -> str:
    if not _should_apply_serbian_variant_instruction(
        schedule_name=schedule_name,
        template_name=template_name,
        variables=variables,
    ):
        return rendered_prompt
    return f"{rendered_prompt}\n\n{SERBIAN_VARIANT_INSTRUCTION}"


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
        prior_items: list[dict[str, str]],
        forbidden_term: str | None = None,
    ) -> str:
        if not prior_items:
            return rendered_prompt
        history_lines = []
        for item in prior_items:
            details = [f"term: {item['term']}"]
            if item.get("example_source"):
                details.append(f"example: {item['example_source']}")
            if item.get("example_target"):
                details.append(f"translation: {item['example_target']}")
            if item.get("notes"):
                details.append(f"notes: {item['notes']}")
            history_lines.append(f"- {' | '.join(details)}")
        history_block = [
            "",
            "Do not repeat or closely paraphrase recently generated study-card content from this schedule.",
            "Recent generated items to avoid:",
            *history_lines,
            "Avoid reusing listed terms, verbs, example sentences, sentence templates, subjects, contexts, key nouns, translations, or notes.",
            "If a candidate would overlap with the recent history, choose a different term, example, context, and structure.",
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
        prior_items = self.db.list_schedule_history_items(schedule.id, limit=self.uniqueness_history_limit)
        prior_terms = list(dict.fromkeys(item["term"] for item in prior_items))
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
            "prior_items": prior_items,
            "generation_attempts": generation_attempts,
            "duplicate_term_detected": False,
            "prompt_cache": {
                "requested_retention": self.prompt_cache_retention,
                "applied_retention": applied_prompt_cache_retention,
                "note": prompt_cache_retention_note,
            },
        }
        try:
            rendered_prompt = _apply_language_variant_instructions(
                render_prompt(template.user_prompt_template, schedule.variables),
                schedule_name=schedule.name,
                template_name=template.name,
                variables=schedule.variables,
            )
            duplicate_term: str | None = None
            render_payload = None
            final_prompt = rendered_prompt
            prior_term_keys = {_normalize_term(term) for term in prior_terms}
            for attempt_number in (1, 2):
                attempt_prompt = self._build_prompt_with_history(
                    rendered_prompt,
                    prior_items=prior_items,
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
                generated_terms = _extract_item_terms(render_payload)
                primary_term = generated_terms[0]
                generation_attempts.append(
                    {
                        "attempt": attempt_number,
                        "user_prompt": attempt_prompt,
                        "term": primary_term,
                        "terms": generated_terms,
                        "usage": usage_snapshot,
                    }
                )
                prompt_snapshot["openai_usage"] = usage_snapshot
                duplicate_term = next((term for term in generated_terms if _normalize_term(term) in prior_term_keys), None)
                if duplicate_term is None:
                    break
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
        except (MissingTemplateVariableError, AIClientError, ValueError) as exc:
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
