from __future__ import annotations

import json

from prompt_study_notifier.db import Database
from prompt_study_notifier.schemas import PromptCacheMetrics, PromptCacheRunMetric


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def build_prompt_cache_metrics(db: Database, *, limit: int = 50) -> PromptCacheMetrics:
    with db.connection() as connection:
        rows = connection.execute(
            """
            SELECT id, generated_at, model_name, status, generation_seconds, prompt_snapshot_json
            FROM generated_sessions
            ORDER BY generated_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    runs: list[PromptCacheRunMetric] = []
    prompt_tokens_total = 0
    uncached_prompt_tokens_total = 0
    cached_tokens_total = 0
    sessions_with_usage = 0
    sessions_with_cache_hit = 0
    generation_seconds_values: list[float] = []
    generation_seconds_with_cache_hit: list[float] = []
    generation_seconds_without_cache_hit: list[float] = []
    for row in rows:
        try:
            prompt_snapshot = json.loads(row["prompt_snapshot_json"])
        except Exception:
            prompt_snapshot = {}
        usage = prompt_snapshot.get("openai_usage") or {}
        prompt_cache = prompt_snapshot.get("prompt_cache") or {}
        prompt_tokens = usage.get("prompt_tokens")
        uncached_prompt_tokens = usage.get("uncached_prompt_tokens")
        cached_tokens = usage.get("cached_tokens")
        cache_hit_ratio = usage.get("cache_hit_ratio")
        generation_seconds = row["generation_seconds"]
        if isinstance(prompt_tokens, int):
            sessions_with_usage += 1
            prompt_tokens_total += prompt_tokens
            uncached_prompt_tokens_total += uncached_prompt_tokens if isinstance(uncached_prompt_tokens, int) else prompt_tokens
            cached_tokens_total += cached_tokens if isinstance(cached_tokens, int) else 0
            if isinstance(cached_tokens, int) and cached_tokens > 0:
                sessions_with_cache_hit += 1
        if isinstance(generation_seconds, (int, float)):
            generation_seconds_values.append(float(generation_seconds))
            if isinstance(cached_tokens, int) and cached_tokens > 0:
                generation_seconds_with_cache_hit.append(float(generation_seconds))
            else:
                generation_seconds_without_cache_hit.append(float(generation_seconds))
        runs.append(
            PromptCacheRunMetric(
                session_id=row["id"],
                generated_at=row["generated_at"],
                model_name=row["model_name"],
                status=row["status"],
                generation_seconds=generation_seconds,
                prompt_cache_retention=prompt_cache.get("applied_retention"),
                prompt_tokens=prompt_tokens if isinstance(prompt_tokens, int) else None,
                uncached_prompt_tokens=uncached_prompt_tokens if isinstance(uncached_prompt_tokens, int) else None,
                cached_tokens=cached_tokens if isinstance(cached_tokens, int) else None,
                cache_hit_ratio=cache_hit_ratio if isinstance(cache_hit_ratio, (int, float)) else None,
            )
        )
    overall_cache_hit_ratio = None
    if prompt_tokens_total > 0:
        overall_cache_hit_ratio = cached_tokens_total / prompt_tokens_total
    return PromptCacheMetrics(
        total_sessions=len(rows),
        sessions_with_usage=sessions_with_usage,
        sessions_with_cache_hit=sessions_with_cache_hit,
        prompt_tokens=prompt_tokens_total,
        uncached_prompt_tokens=uncached_prompt_tokens_total,
        cached_tokens=cached_tokens_total,
        cache_hit_ratio=overall_cache_hit_ratio,
        avg_generation_seconds=_average(generation_seconds_values),
        avg_generation_seconds_with_cache_hit=_average(generation_seconds_with_cache_hit),
        avg_generation_seconds_without_cache_hit=_average(generation_seconds_without_cache_hit),
        runs=runs,
    )
