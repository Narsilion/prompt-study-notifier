from prompt_study_notifier.rendering import MissingTemplateVariableError, extract_variables, render_prompt


def test_extract_variables_returns_unique_sorted_names() -> None:
    assert extract_variables("Study {topic} with {difficulty} and {topic}") == ["difficulty", "topic"]


def test_render_prompt_substitutes_values() -> None:
    rendered = render_prompt("Focus on {topic} at {level}", {"topic": "cases", "level": "A2"})
    assert rendered == "Focus on cases at A2"


def test_render_prompt_raises_for_missing_variable() -> None:
    try:
        render_prompt("Focus on {topic}", {})
    except MissingTemplateVariableError as exc:
        assert "topic" in str(exc)
    else:
        raise AssertionError("Expected missing variable error")
