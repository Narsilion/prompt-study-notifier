from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StudyItem(BaseModel):
    term: str
    translation: str | None = None
    explanation: str | None = None
    example_source: str | None = None
    example_target: str | None = None
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)


class StudyPayload(BaseModel):
    title: str
    topic: str
    summary: str
    focus_hint: str | None = None
    items: list[StudyItem] = Field(default_factory=list)


class TemplateVariableDefinition(BaseModel):
    name: str
    label: str | None = None
    description: str | None = None
    example: str | None = None
    required: bool = True


class TemplateUpsert(BaseModel):
    name: str
    description: str | None = None
    system_prompt: str
    user_prompt_template: str
    output_schema_version: str = "v1"
    is_active: bool = True
    variables: list[TemplateVariableDefinition] = Field(default_factory=list)


class TemplateRecord(TemplateUpsert):
    id: int
    created_at: str
    updated_at: str
    variable_names: list[str]
    model_config = ConfigDict(from_attributes=True)


class ScheduleUpsert(BaseModel):
    name: str
    template_id: int
    variables: dict[str, Any] = Field(default_factory=dict)
    interval_minutes: int | None = Field(default=None, ge=1)
    cron_expr: str | None = None
    timezone: str = "Europe/Belgrade"
    is_active: bool = True
    notification_enabled: bool = True
    telegram_enabled: bool = False

    @field_validator("cron_expr", mode="before")
    @classmethod
    def strip_cron_expr(cls, value: Any) -> Any:
        if isinstance(value, str):
            return " ".join(value.split())
        return value

    @model_validator(mode="after")
    def validate_schedule_interval(self) -> "ScheduleUpsert":
        if self.interval_minutes is None and not self.cron_expr:
            raise ValueError("interval_minutes is required.")
        return self


class ScheduleRecord(ScheduleUpsert):
    id: int
    next_run_at: str | None = None
    last_run_at: str | None = None
    last_session_id: int | None = None
    awaiting_acknowledgement: bool = False
    pending_acknowledgement_count: int = 0
    created_at: str
    updated_at: str
    model_config = ConfigDict(from_attributes=True)


class PromptPreviewRequest(BaseModel):
    user_prompt_template: str
    variables: dict[str, Any] = Field(default_factory=dict)


class PromptPreviewResponse(BaseModel):
    resolved_prompt: str
    variable_names: list[str]


class SessionRecord(BaseModel):
    id: int
    schedule_id: int
    template_id: int
    render_payload: StudyPayload | None = None
    model_name: str
    prompt_snapshot: dict[str, Any]
    status: str
    error_text: str | None = None
    generated_at: str
    generation_seconds: float | None = None
    acknowledged_at: str | None = None
    model_config = ConfigDict(from_attributes=True)


class SessionSummary(BaseModel):
    id: int
    schedule_id: int
    template_id: int
    status: str
    generated_at: str
    error_text: str | None = None
    title: str | None = None
    topic: str | None = None
    acknowledged_at: str | None = None


class LiveEvent(BaseModel):
    type: str
    session: SessionRecord
    schedule: ScheduleRecord | None = None
    run_source: str = "scheduled"


class BrowserNotificationPayload(BaseModel):
    title: str
    body: str
    session_id: int


class SettingsRecord(BaseModel):
    model: str
    active_model: str
    active_ai_provider: str = "openai"
    available_ai_providers: list[str] = Field(default_factory=lambda: ["openai"])
    preferred_speech_voice_uri: str = ""
    available_models: list[str] = Field(default_factory=list)
    available_models_by_provider: dict[str, list[str]] = Field(default_factory=dict)
    prompt_cache_retention: str
    retention_limit: int
    scheduler_poll_seconds: int
    host: str
    port: int


class SettingsUpdateRequest(BaseModel):
    active_model: str
    active_ai_provider: str = "openai"
    preferred_speech_voice_uri: str = ""


class ModelListResponse(BaseModel):
    provider: str
    models: list[str] = Field(default_factory=list)
    source: str = "configured"
    detail: str | None = None


class AIDiagnosticsResponse(BaseModel):
    active_ai_provider: str
    active_model: str
    github_token_configured: bool
    github_token_source: str | None = None
    github_token_fingerprint: str | None = None
    active_model_in_configured_github_models: bool
    configured_github_model_count: int


class AIProbeResponse(BaseModel):
    provider: str
    model: str
    status: str
    detail: str | None = None


class RunNowResponse(BaseModel):
    status: str


class AcknowledgeSessionResponse(BaseModel):
    session: SessionRecord
    schedule: ScheduleRecord


class HealthResponse(BaseModel):
    status: str = "ok"
    now: datetime


class PromptCacheRunMetric(BaseModel):
    session_id: int
    generated_at: str
    model_name: str
    status: str
    generation_seconds: float | None = None
    prompt_cache_retention: str | None = None
    prompt_tokens: int | None = None
    uncached_prompt_tokens: int | None = None
    cached_tokens: int | None = None
    cache_hit_ratio: float | None = None


class PromptCacheMetrics(BaseModel):
    total_sessions: int
    sessions_with_usage: int
    sessions_with_cache_hit: int
    prompt_tokens: int
    uncached_prompt_tokens: int
    cached_tokens: int
    cache_hit_ratio: float | None = None
    avg_generation_seconds: float | None = None
    avg_generation_seconds_with_cache_hit: float | None = None
    avg_generation_seconds_without_cache_hit: float | None = None
    runs: list[PromptCacheRunMetric] = Field(default_factory=list)
