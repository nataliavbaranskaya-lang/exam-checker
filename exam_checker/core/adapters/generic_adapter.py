from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from exam_checker.core.generic_excel import fill_template
from exam_checker.core.generic_scorer import score_all
from exam_checker.core.models import LevelInfo, PaperData, PaperResult
from exam_checker.core.session_config import SessionConfig


class GenericAdapter:
    """Score papers from an uploaded answer key and session configuration."""

    def __init__(self, config: SessionConfig, answer_key: Dict[int, str]):
        self.config = config
        self.answer_key = answer_key
        self.info = _info_from_config(config)

    def get_key_answer(self, n: int) -> str:
        return self.answer_key.get(n, "")

    def score_papers(self, papers: List[PaperData]) -> List[PaperResult]:
        return score_all(papers, self.answer_key, self.config)

    def fill_template(
        self, template_path: Path, papers: List[PaperData], out_path: Path
    ) -> None:
        results = self.score_papers(papers)
        fill_template(template_path, papers, results, self.config, out_path)


def _info_from_config(config: SessionConfig) -> LevelInfo:
    return LevelInfo(
        code=config.level_code,
        title=config.title,
        question_count=config.question_count,
        max_test_score=config.max_score,
        pass_fail_thresholds=(config.grade_fail_below, config.grade_pass_plus_from),
    )


def build_adapter(config: SessionConfig, answer_key: Dict[int, str], legacy_level=None):
    if not answer_key:
        raise ValueError("Upload an answer key before scoring.")
    return GenericAdapter(config, answer_key)
