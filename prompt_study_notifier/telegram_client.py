from __future__ import annotations

from html import escape
import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from prompt_study_notifier.schemas import ScheduleRecord, SessionRecord


TELEGRAM_API_BASE_URL = "https://api.telegram.org"


class TelegramClientError(RuntimeError):
    """Raised when a Telegram request fails."""


def _extract_level(session: SessionRecord, tags: list[str] | None = None) -> str | None:
    variables = session.prompt_snapshot.get("variables") if isinstance(session.prompt_snapshot, dict) else None
    if isinstance(variables, dict):
        difficulty = variables.get("difficulty")
        if isinstance(difficulty, str) and difficulty.strip():
            return difficulty.strip()
    for tag in tags or []:
        normalized = tag.strip().upper()
        if normalized in {"A1", "A2", "B1", "B2", "C1", "C2"}:
            return normalized
    return None


def _display_term(term: str | None) -> str:
    value = (term or "").strip()
    if not value:
        return ""
    return value[:1].upper() + value[1:]


def _should_show_focus(session: SessionRecord) -> bool:
    variables = session.prompt_snapshot.get("variables") if isinstance(session.prompt_snapshot, dict) else None
    if not isinstance(variables, dict):
        return False
    for key in ("focus_area", "focus"):
        value = variables.get(key)
        if isinstance(value, str) and value.strip():
            return True
    return False


def _display_title(session: SessionRecord) -> str:
    schedule_name = session.prompt_snapshot.get("schedule_name") if isinstance(session.prompt_snapshot, dict) else None
    if isinstance(schedule_name, str) and schedule_name.strip():
        return schedule_name.strip()
    return session.render_payload.title


def format_session_message(session: SessionRecord, schedule: ScheduleRecord, *, run_source: str) -> str:
    if session.render_payload is None:
        raise ValueError("Telegram messages require a successful session payload.")

    run_label = "Manual" if run_source == "manual" else "Scheduled"
    lines = [f"📘 {escape(schedule.name or _display_title(session))}"]
    if session.render_payload.items:
        first_item = session.render_payload.items[0]
        level = _extract_level(session, first_item.tags)
        if level:
            lines.extend(["", f"🏷️ Level: {escape(level)}"])
        if session.render_payload.focus_hint and _should_show_focus(session):
            lines.extend(["", f"🎯 Focus: {escape(session.render_payload.focus_hint)}"])
        for item in session.render_payload.items:
            lines.extend(["", f"<b>📖 {escape(_display_term(item.term))}</b>"])
            if item.translation:
                lines.extend(["", f"💬 Meaning: {escape(item.translation)}"])
            if item.explanation:
                lines.extend(["", f"🧠 {escape(item.explanation)}"])
            if item.example_source:
                lines.extend(["", f"📝 Example: {escape(item.example_source)}"])
            if item.example_target:
                lines.append(f"🌐 Translation: {escape(item.example_target)}")
            if item.notes:
                lines.extend(["", f"📎 Note: {escape(item.notes)}"])
    lines.extend(["", f"⏰ Schedule: {escape(schedule.name)}", f"⚙️ Run: {escape(run_label)}"])
    return "\n".join(lines)


@dataclass(slots=True)
class TelegramClient:
    bot_token: str
    chat_id: str

    def send_session(self, session: SessionRecord, schedule: ScheduleRecord, *, run_source: str) -> None:
        if session.status != "success" or session.render_payload is None:
            return

        message = format_session_message(session, schedule, run_source=run_source)
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "disable_web_page_preview": True,
            "parse_mode": "HTML",
        }
        request = Request(
            f"{TELEGRAM_API_BASE_URL}/bot{self.bot_token}/sendMessage",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise TelegramClientError(f"Telegram request failed with status {exc.code}: {detail}") from exc
        except URLError as exc:
            raise TelegramClientError(f"Telegram request failed: {exc.reason}") from exc

        if not body.get("ok"):
            raise TelegramClientError(f"Telegram request failed: {body}")
