from __future__ import annotations

from exam_checker.core.adapters.generic_adapter import build_adapter


def get_adapter(config, answer_key: dict, legacy_level: str | None = None):
    return build_adapter(config, answer_key)
