from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from prompt_study_notifier.schemas import StudyPayload


OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
class OpenAIClientError(RuntimeError):
    """Raised when the OpenAI request fails."""


@dataclass(slots=True)
class OpenAIUsage:
    prompt_tokens: int | None = None
    cached_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(slots=True)
class OpenAIResult:
    payload: StudyPayload
    usage: OpenAIUsage


class OpenAIClient:
    def __init__(self, api_key: str | None) -> None:
        self.api_key = api_key

    def generate_payload(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        prompt_cache_retention: str | None = None,
    ) -> OpenAIResult:
        if not self.api_key:
            raise OpenAIClientError("OPENAI_API_KEY is not configured")

        schema = {
            "name": "study_payload",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "topic": {"type": "string"},
                    "summary": {"type": "string"},
                    "focus_hint": {"type": ["string", "null"]},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "term": {"type": "string"},
                                "translation": {"type": ["string", "null"]},
                                "explanation": {"type": ["string", "null"]},
                                "example_source": {"type": ["string", "null"]},
                                "example_target": {"type": ["string", "null"]},
                                "notes": {"type": ["string", "null"]},
                                "tags": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": ["term", "translation", "explanation", "example_source", "example_target", "notes", "tags"],
                        },
                    },
                },
                "required": ["title", "topic", "summary", "focus_hint", "items"],
            },
            "strict": True,
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        user_prompt
                        + "\n\nReturn valid JSON only. Do not include markdown fences or prose outside the JSON object."
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": schema,
            },
        }
        if prompt_cache_retention:
            payload["prompt_cache_retention"] = prompt_cache_retention
        request = Request(
            OPENAI_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=90) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise OpenAIClientError(f"OpenAI request failed with status {exc.code}: {detail}") from exc
        except URLError as exc:
            raise OpenAIClientError(f"OpenAI request failed: {exc.reason}") from exc

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OpenAIClientError(f"Unexpected OpenAI response shape: {body}") from exc
        usage_payload = body.get("usage") or {}
        prompt_token_details = usage_payload.get("prompt_tokens_details") or {}
        usage = OpenAIUsage(
            prompt_tokens=usage_payload.get("prompt_tokens"),
            cached_tokens=prompt_token_details.get("cached_tokens"),
            total_tokens=usage_payload.get("total_tokens"),
        )
        return OpenAIResult(payload=StudyPayload.model_validate_json(content), usage=usage)
