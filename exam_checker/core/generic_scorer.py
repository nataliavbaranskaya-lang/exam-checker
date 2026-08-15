from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Tuple

from exam_checker.core.models import PaperData, PaperResult, QuestionError
from exam_checker.core.session_config import SessionConfig


def norm_blank(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.upper().strip()
    s = re.sub(r"\s+", "", s)
    return s


def norm_word(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.upper().strip()
    s = re.sub(r"[^A-Z0-9@]+", "", s)
    return s


def norm_digit(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s or "")).strip().upper()
    s = re.sub(r"\s+", "", s)
    if not s:
        return ""
    if s[0] in "123":
        return s[0]
    return norm_blank(s)


def score_positions(student: str, key: str, mx: int) -> int:
    st = list(student.replace(" ", ""))
    k = list(key.replace(" ", ""))
    n = max(len(st), len(k))
    err = sum(1 for i in range(n) if i >= len(st) or i >= len(k) or st[i] != k[i])
    return max(0, mx - err)


def answer_ok(student: str, key: str, *, digits_only: bool = False) -> bool:
    st = (student or "").strip()
    if not st:
        return False
    alts = [a.strip() for a in key.split("/") if a.strip()]
    if digits_only or (len(alts) == 1 and alts[0] in ("1", "2", "3", "4", "5", "6", "7", "8", "9")):
        return norm_digit(st) in {norm_digit(a) for a in alts}
    st_n = norm_word(st)
    return st_n in {norm_word(a) for a in alts}


def final_answers(paper: PaperData) -> Dict[int, str]:
    out = dict(paper.answers)
    for n, v in paper.replacements.items():
        out[n] = v
    return out


def score_question(
    n: int, student: str, key: str, config: SessionConfig
) -> Tuple[int, int]:
    """Returns (points earned, max points for question)."""
    if n in config.weighted:
        w = config.weighted[n]
        if w.type == "positional":
            pts = score_positions(student, key, w.max_points)
            return pts, w.max_points
    digits_only = n in config.digit_questions
    ok = answer_ok(student, key, digits_only=digits_only)
    return (1, 1) if ok else (0, 1)


def score_paper(
    paper: PaperData, key: Dict[int, str], config: SessionConfig
) -> PaperResult:
    fa = final_answers(paper)
    detail: Dict[int, int] = {}
    errors: List[QuestionError] = []
    total = 0

    for n in range(1, config.question_count + 1):
        key_val = key.get(n, "")
        st = fa.get(n, "") or ""
        pts, mx = score_question(n, st, key_val, config)
        detail[n] = pts
        total += pts
        if pts < mx:
            if not st.strip():
                errors.append(
                    QuestionError(n, "(пусто)", key_val, f"{pts}/{mx}", "нет ответа")
                )
            else:
                extra = ""
                if n in config.weighted and config.weighted[n].type == "positional":
                    extra = f", ошибки позиций"
                errors.append(
                    QuestionError(n, st, key_val, f"{pts}/{mx}", extra.strip(", "))
                )

    sections: Dict[str, int] = {}
    for sec in config.sections:
        sections[sec.id] = sum(
            detail.get(n, 0) for n in range(sec.from_q, sec.to_q + 1)
        )

    grade = grade_for_total(total, config)
    return PaperResult(
        paper=paper,
        sections=sections,
        total=total,
        grade=grade,
        errors=errors,
        replacements=dict(paper.replacements),
    )


def grade_for_total(total: int, config: SessionConfig) -> str:
    if total < config.grade_fail_below:
        return "Fail"
    if total < config.grade_pass_plus_from:
        return "Pass"
    return "Pass +"


def score_all(
    papers: List[PaperData], key: Dict[int, str], config: SessionConfig
) -> List[PaperResult]:
    return [score_paper(p, key, config) for p in papers]
