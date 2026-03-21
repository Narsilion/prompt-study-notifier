from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from prompt_study_notifier.db import Database
from prompt_study_notifier.generation import GenerationService
from prompt_study_notifier.live_updates import LiveUpdateBroker
from prompt_study_notifier.openai_client import OpenAIClient
from prompt_study_notifier.schemas import (
    HealthResponse,
    PromptPreviewRequest,
    PromptPreviewResponse,
    RunNowResponse,
    ScheduleRecord,
    ScheduleUpsert,
    SessionRecord,
    SessionSummary,
    SettingsRecord,
    SettingsUpdateRequest,
    TemplateRecord,
    TemplateUpsert,
)
from prompt_study_notifier.settings import Settings
from prompt_study_notifier.ui import render_dashboard, render_templates_page


class SchedulerRuntime:
    def __init__(self, service: GenerationService, broker: LiveUpdateBroker, poll_seconds: int) -> None:
        self.service = service
        self.broker = broker
        self.poll_seconds = poll_seconds
        self._task: asyncio.Task[None] | None = None
        self._running_schedule_ids: set[int] = set()

    async def start(self) -> None:
        self._task = asyncio.create_task(self._loop(), name="prompt-study-scheduler")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass

    async def enqueue_now(self, schedule_id: int, *, run_source: str = "manual") -> None:
        if schedule_id in self._running_schedule_ids:
            return
        self._running_schedule_ids.add(schedule_id)
        asyncio.create_task(self._run_schedule(schedule_id, run_source=run_source))

    async def _loop(self) -> None:
        while True:
            due_schedules = self.service.db.list_due_schedules()
            for schedule in due_schedules:
                if schedule.id in self._running_schedule_ids:
                    continue
                self._running_schedule_ids.add(schedule.id)
                asyncio.create_task(self._run_schedule(schedule.id, run_source="scheduled"))
            await asyncio.sleep(self.poll_seconds)

    async def _run_schedule(self, schedule_id: int, *, run_source: str) -> None:
        try:
            session = await asyncio.to_thread(self.service.generate_for_schedule, schedule_id)
            event = self.service.build_live_event(session, run_source=run_source)
            await self.broker.broadcast_json(event.model_dump(mode="json"))
        finally:
            self._running_schedule_ids.discard(schedule_id)


def create_app(settings: Settings) -> FastAPI:
    available_models = [
        "gpt-5.4-mini",
        "gpt-5-mini",
        "gpt-5.4",
        "gpt-5",
    ]
    if settings.model not in available_models:
        available_models.insert(0, settings.model)
    db = Database(settings.db_path)
    db.initialize()
    db.set_app_setting("active_model", db.get_active_model(settings.model))
    db.bootstrap_defaults()
    client = OpenAIClient(settings.openai_api_key)
    generation_service = GenerationService(
        db=db,
        client=client,
        model=settings.model,
        retention_limit=settings.retention_limit,
    )
    broker = LiveUpdateBroker()
    runtime = SchedulerRuntime(generation_service, broker, settings.scheduler_poll_seconds)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.db = db
        app.state.generation_service = generation_service
        app.state.live_broker = broker
        app.state.scheduler_runtime = runtime
        await runtime.start()
        yield
        await runtime.stop()

    app = FastAPI(title="Prompt Study Notifier", lifespan=lifespan)

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> str:
        return render_dashboard(
            SettingsRecord(
                model=settings.model,
                active_model=db.get_active_model(settings.model),
                available_models=available_models,
                retention_limit=settings.retention_limit,
                scheduler_poll_seconds=settings.scheduler_poll_seconds,
                host=settings.host,
                port=settings.port,
            )
        )

    @app.get("/templates", response_class=HTMLResponse)
    async def templates_page() -> str:
        return render_templates_page(
            SettingsRecord(
                model=settings.model,
                active_model=db.get_active_model(settings.model),
                available_models=available_models,
                retention_limit=settings.retention_limit,
                scheduler_poll_seconds=settings.scheduler_poll_seconds,
                host=settings.host,
                port=settings.port,
            ),
            db.list_templates(),
        )

    @app.get("/api/settings", response_model=SettingsRecord)
    async def get_settings() -> SettingsRecord:
        return SettingsRecord(
            model=settings.model,
            active_model=db.get_active_model(settings.model),
            available_models=available_models,
            retention_limit=settings.retention_limit,
            scheduler_poll_seconds=settings.scheduler_poll_seconds,
            host=settings.host,
            port=settings.port,
        )

    @app.put("/api/settings", response_model=SettingsRecord)
    async def update_settings(payload: SettingsUpdateRequest) -> SettingsRecord:
        db.update_settings(payload)
        return SettingsRecord(
            model=settings.model,
            active_model=db.get_active_model(settings.model),
            available_models=available_models,
            retention_limit=settings.retention_limit,
            scheduler_poll_seconds=settings.scheduler_poll_seconds,
            host=settings.host,
            port=settings.port,
        )

    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(now=datetime.now(UTC))

    @app.get("/api/templates", response_model=list[TemplateRecord])
    async def list_templates() -> list[TemplateRecord]:
        return db.list_templates()

    @app.post("/api/templates", response_model=TemplateRecord)
    async def create_template(payload: TemplateUpsert) -> TemplateRecord:
        return db.create_template(payload)

    @app.put("/api/templates/{template_id}", response_model=TemplateRecord)
    async def update_template(template_id: int, payload: TemplateUpsert) -> TemplateRecord:
        try:
            return db.update_template(template_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.delete("/api/templates/{template_id}", response_model=RunNowResponse)
    async def delete_template(template_id: int) -> RunNowResponse:
        try:
            db.delete_template(template_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return RunNowResponse(status="deleted")

    @app.post("/api/templates/preview", response_model=PromptPreviewResponse)
    async def preview_template(payload: PromptPreviewRequest) -> PromptPreviewResponse:
        resolved_prompt, variable_names = generation_service.preview_prompt(
            user_prompt_template=payload.user_prompt_template,
            variables=payload.variables,
        )
        return PromptPreviewResponse(resolved_prompt=resolved_prompt, variable_names=variable_names)

    @app.get("/api/schedules", response_model=list[ScheduleRecord])
    async def list_schedules() -> list[ScheduleRecord]:
        return db.list_schedules()

    @app.post("/api/schedules", response_model=ScheduleRecord)
    async def create_schedule(payload: ScheduleUpsert) -> ScheduleRecord:
        try:
            db.get_template(payload.template_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        try:
            return db.create_schedule(payload)
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/schedules/{schedule_id}", response_model=ScheduleRecord)
    async def update_schedule(schedule_id: int, payload: ScheduleUpsert) -> ScheduleRecord:
        try:
            db.get_template(payload.template_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        try:
            return db.update_schedule(schedule_id, payload)
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/schedules/{schedule_id}", response_model=RunNowResponse)
    async def delete_schedule(schedule_id: int) -> RunNowResponse:
        try:
            db.delete_schedule(schedule_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return RunNowResponse(status="deleted")

    @app.post("/api/schedules/{schedule_id}/run-now", response_model=RunNowResponse)
    async def run_schedule_now(schedule_id: int) -> RunNowResponse:
        try:
            db.get_schedule(schedule_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        await runtime.enqueue_now(schedule_id, run_source="manual")
        return RunNowResponse(status="queued")

    @app.get("/api/sessions", response_model=list[SessionSummary])
    async def list_sessions(limit: int = 20) -> list[SessionSummary]:
        return db.list_sessions(limit=limit)

    @app.delete("/api/sessions", response_model=RunNowResponse)
    async def clear_sessions() -> RunNowResponse:
        db.clear_sessions()
        return RunNowResponse(status="cleared")

    @app.get("/api/sessions/{session_id}", response_model=SessionRecord)
    async def get_session(session_id: int) -> SessionRecord:
        try:
            return db.get_session(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.delete("/api/sessions/{session_id}", response_model=RunNowResponse)
    async def delete_session(session_id: int) -> RunNowResponse:
        try:
            db.delete_session(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return RunNowResponse(status="deleted")

    @app.websocket("/api/live")
    async def live_updates(websocket: WebSocket) -> None:
        await broker.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            await broker.disconnect(websocket)
        except Exception:
            await broker.disconnect(websocket)

    return app
