from datetime import UTC, datetime

from prompt_study_notifier.scheduler import compute_next_run, parse_cron_expr


def test_parse_cron_expr_accepts_standard_expression() -> None:
    schedule = parse_cron_expr("*/15 9-17 * * 1-5")
    assert 15 in schedule.minute
    assert 9 in schedule.hour
    assert 5 in schedule.day_of_week


def test_compute_next_run_returns_future_utc_datetime() -> None:
    after = datetime(2026, 3, 20, 10, 5, tzinfo=UTC)
    next_run = compute_next_run("*/30 * * * *", timezone_name="UTC", after=after)
    assert next_run == datetime(2026, 3, 20, 10, 30, tzinfo=UTC)
