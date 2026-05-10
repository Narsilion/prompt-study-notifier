from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from prompt_study_notifier.schemas import StudyPayload


OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODELS_API_URL = "https://api.openai.com/v1/models"
GITHUB_MODELS_API_URL = "https://models.github.ai/inference/chat/completions"
GITHUB_MODELS_CATALOG_API_URL = "https://models.github.ai/catalog/models"
GITHUB_MODELS_API_VERSION = "2026-03-10"


class AIClientError(RuntimeError):
    """Raised when an AI provider request fails."""


class OpenAIClientError(AIClientError):
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

    def list_models(self) -> list[str]:
        if not self.api_key:
            raise OpenAIClientError("OPENAI_API_KEY is not configured")
        request = Request(
            OPENAI_MODELS_API_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise OpenAIClientError(f"OpenAI models request failed with status {exc.code}: {detail}") from exc
        except URLError as exc:
            raise OpenAIClientError(f"OpenAI models request failed: {exc.reason}") from exc
        models = body.get("data") if isinstance(body, dict) else None
        if not isinstance(models, list):
            raise OpenAIClientError(f"Unexpected OpenAI models response shape: {body}")
        ids = [str(model.get("id") or "").strip() for model in models if isinstance(model, dict)]
        return sorted({model_id for model_id in ids if _is_openai_text_generation_model(model_id)})

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


class GitHubModelsClient:
    def __init__(self, token: str | None) -> None:
        self.token = token

    def list_models(self) -> list[str]:
        if not self.token:
            raise AIClientError("GITHUB_MODELS_TOKEN is not configured")
        request = Request(
            GITHUB_MODELS_CATALOG_API_URL,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": GITHUB_MODELS_API_VERSION,
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise AIClientError(f"GitHub Models catalog request failed with status {exc.code}: {detail}") from exc
        except URLError as exc:
            raise AIClientError(f"GitHub Models catalog request failed: {exc.reason}") from exc
        if not isinstance(body, list):
            raise AIClientError(f"Unexpected GitHub Models catalog response shape: {body}")
        ids: list[str] = []
        for model in body:
            if not isinstance(model, dict):
                continue
            inputs = model.get("supported_input_modalities")
            outputs = model.get("supported_output_modalities")
            if not isinstance(inputs, list) or not isinstance(outputs, list):
                continue
            if "text" not in inputs or "text" not in outputs:
                continue
            model_id = str(model.get("id") or "").strip()
            if model_id:
                ids.append(model_id)
        return sorted(set(ids))

    def generate_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
        schema: dict[str, object],
    ) -> dict[str, object]:
        if not self.token:
            raise AIClientError("GITHUB_MODELS_TOKEN is not configured")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": user_prompt
                    + "\n\nReturn valid JSON only. Do not include markdown fences or prose outside the JSON object.",
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
            },
        }
        request = Request(
            GITHUB_MODELS_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": GITHUB_MODELS_API_VERSION,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=90) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            if exc.code == 403 and "No access to model" in detail:
                raise AIClientError(
                    f"GitHub Models denied access to {model}. Choose another GitHub model in Settings, "
                    "or set PSN_GITHUB_MODELS to models available to this GitHub account."
                ) from exc
            raise AIClientError(f"GitHub Models request failed with status {exc.code}: {detail}") from exc
        except URLError as exc:
            raise AIClientError(f"GitHub Models request failed: {exc.reason}") from exc
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIClientError(f"Unexpected GitHub Models response shape: {body}") from exc
        data = json.loads(str(content))
        if not isinstance(data, dict):
            raise AIClientError("GitHub Models response was not a JSON object")
        return data

    def generate_payload(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        prompt_cache_retention: str | None = None,
    ) -> OpenAIResult:
        if not self.token:
            raise AIClientError("GITHUB_MODELS_TOKEN is not configured")
        schema = _study_payload_json_schema()
        payload = _chat_payload(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=schema,
        )
        request = Request(
            GITHUB_MODELS_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": GITHUB_MODELS_API_VERSION,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=90) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            if exc.code == 403 and "No access to model" in detail:
                raise AIClientError(
                    f"GitHub Models denied access to {model}. Choose another GitHub model in Settings, "
                    "or set PSN_GITHUB_MODELS to models available to this GitHub account."
                ) from exc
            raise AIClientError(f"GitHub Models request failed with status {exc.code}: {detail}") from exc
        except URLError as exc:
            raise AIClientError(f"GitHub Models request failed: {exc.reason}") from exc

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIClientError(f"Unexpected GitHub Models response shape: {body}") from exc
        usage_payload = body.get("usage") if isinstance(body, dict) else {}
        usage_payload = usage_payload if isinstance(usage_payload, dict) else {}
        prompt_token_details = usage_payload.get("prompt_tokens_details") or {}
        prompt_token_details = prompt_token_details if isinstance(prompt_token_details, dict) else {}
        usage = OpenAIUsage(
            prompt_tokens=usage_payload.get("prompt_tokens"),
            cached_tokens=prompt_token_details.get("cached_tokens"),
            total_tokens=usage_payload.get("total_tokens"),
        )
        return OpenAIResult(payload=StudyPayload.model_validate_json(str(content)), usage=usage)


def _study_payload_json_schema() -> dict[str, object]:
    return {
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


def _chat_payload(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    schema: dict[str, object],
) -> dict[str, object]:
    return {
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


def _is_openai_text_generation_model(model_id: str) -> bool:
    if not model_id:
        return False
    excluded_prefixes = (
        "text-embedding",
        "dall-e",
        "tts",
        "whisper",
        "omni-moderation",
        "babbage",
        "davinci",
    )
    if model_id.startswith(excluded_prefixes):
        return False
    included_prefixes = ("gpt-", "chatgpt-", "o1", "o3", "o4")
    return model_id.startswith(included_prefixes)
