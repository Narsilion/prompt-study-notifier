from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    cron_expr: str
    timezone: str = "Europe/Belgrade"
    is_active: bool = True
    notification_enabled: bool = True

    @field_validator("cron_expr", mode="before")
    @classmethod
    def strip_cron_expr(cls, value: Any) -> Any:
        if isinstance(value, str):
            return " ".join(value.split())
        return value


class ScheduleRecord(ScheduleUpsert):
    id: int
    next_run_at: str | None = None
    last_run_at: str | None = None
    last_session_id: int | None = None
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
    available_models: list[str] = Field(default_factory=list)
    retention_limit: int
    scheduler_poll_seconds: int
    host: str
    port: int


class SettingsUpdateRequest(BaseModel):
    active_model: str


class RunNowResponse(BaseModel):
    status: str


class HealthResponse(BaseModel):
    status: str = "ok"
    now: datetime
