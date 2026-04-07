from datetime import UTC, datetime

from prompt_study_notifier.scheduler import compute_next_run, infer_interval_minutes_from_cron, parse_cron_expr


def test_parse_cron_expr_accepts_standard_expression() -> None:
    schedule = parse_cron_expr("*/15 9-17 * * 1-5")
    assert 15 in schedule.minute
    assert 9 in schedule.hour
    assert 5 in schedule.day_of_week


def test_compute_next_run_returns_future_utc_datetime() -> None:
    after = datetime(2026, 3, 20, 10, 5, tzinfo=UTC)
    next_run = compute_next_run(60, after=after)
    assert next_run == datetime(2026, 3, 20, 11, 5, tzinfo=UTC)


def test_infer_interval_minutes_from_cron_uses_smallest_gap() -> None:
    assert infer_interval_minutes_from_cron("0 * * * *", timezone_name="UTC") == 60
