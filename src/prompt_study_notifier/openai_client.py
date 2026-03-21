from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from prompt_study_notifier.schemas import StudyPayload


OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIClientError(RuntimeError):
    """Raised when the OpenAI request fails."""


class OpenAIClient:
    def __init__(self, api_key: str | None) -> None:
        self.api_key = api_key

    def generate_payload(self, *, model: str, system_prompt: str, user_prompt: str) -> StudyPayload:
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
        return StudyPayload.model_validate_json(content)
