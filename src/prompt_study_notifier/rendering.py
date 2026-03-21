from __future__ import annotations

import re
from collections.abc import Mapping


VARIABLE_RE = re.compile(r"{([a-zA-Z_][a-zA-Z0-9_]*)}")


class MissingTemplateVariableError(ValueError):
    """Raised when a prompt template references a missing variable."""


class _SafeDict(dict[str, object]):
    def __missing__(self, key: str) -> object:
        raise MissingTemplateVariableError(f"Missing template variable: {key}")


def extract_variables(template_text: str) -> list[str]:
    return sorted(set(VARIABLE_RE.findall(template_text)))


def render_prompt(template_text: str, variables: Mapping[str, object]) -> str:
    return template_text.format_map(_SafeDict(variables))
