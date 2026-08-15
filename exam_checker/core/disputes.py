from __future__ import annotations

from typing import List

from exam_checker.core.models import PaperData


def find_disputes(paper: PaperData, question_count: int) -> List[str]:
    flags: List[str] = []
    if not paper.surname.strip():
        flags.append("surname missing")
    if not paper.name.strip():
        flags.append("first name missing")
    if paper.replacements:
        flags.append(f"corrections present: {paper.replacements}")
    if paper.uncertain:
        flags.append(f"OCR: review questions {paper.uncertain}")
    empty = [
        n
        for n in range(1, question_count + 1)
        if not (paper.replacements.get(n) or paper.answers.get(n) or "").strip()
    ]
    if empty:
        flags.append(f"empty answers: {empty}")
    extra = [n for n in paper.answers if n > question_count]
    if extra:
        flags.append(f"answers outside grid (>{question_count}): {extra}")
    return flags
