from __future__ import annotations

import random
import re
from collections.abc import Mapping


VARIABLE_RE = re.compile(r"(?<!{){([a-zA-Z_][a-zA-Z0-9_]*)}(?!})")
RANDOM_DEFAULTS: dict[str, tuple[str, ...]] = {
    "gender": ("masculine", "feminine", "neuter"),
}


class MissingTemplateVariableError(ValueError):
    """Raised when a prompt template references a missing variable."""


class _SafeDict(dict[str, object]):
    def __missing__(self, key: str) -> object:
        if key in RANDOM_DEFAULTS:
            return random.choice(RANDOM_DEFAULTS[key])
        raise MissingTemplateVariableError(f"Missing template variable: {key}")


def extract_variables(template_text: str) -> list[str]:
    return sorted(set(VARIABLE_RE.findall(template_text)))


def render_prompt(template_text: str, variables: Mapping[str, object]) -> str:
    resolved_variables = dict(variables)
    for key, choices in RANDOM_DEFAULTS.items():
        value = resolved_variables.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            resolved_variables.pop(key, None)
    return template_text.format_map(_SafeDict(resolved_variables))
