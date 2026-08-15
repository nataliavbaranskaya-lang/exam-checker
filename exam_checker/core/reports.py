from __future__ import annotations

import io
from typing import Any, Dict, List

from exam_checker.core.models import PaperData, PaperResult
from exam_checker.core.session_config import SessionConfig

SECTION_SHORT_NAMES = {
    "listening": "Listening",
    "reading": "Reading",
    "uoe": "UoE",
}


def section_column_name(sec_id: str, sec_label: str) -> str:
    return SECTION_SHORT_NAMES.get(sec_id, sec_label)


def results_table_rows(
    results: List[PaperResult], config: SessionConfig
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for r in sorted(
        results,
        key=lambda x: (x.paper.surname.lower(), x.paper.name.lower()),
    ):
        row: Dict[str, Any] = {
            "Фамилия": r.paper.surname,
            "Имя": r.paper.name,
        }
        for sec in config.sections:
            col = section_column_name(sec.id, sec.label)
            row[col] = r.sections.get(sec.id, 0)
        row["Баллы"] = r.total
        row["Оценка"] = r.grade
        rows.append(row)
    return rows


def results_summary_stats(results: List[PaperResult]) -> Dict[str, Any]:
    if not results:
        return {"count": 0, "fail": 0, "pass": 0, "pass_plus": 0, "avg": 0.0}
    return {
        "count": len(results),
        "fail": sum(1 for r in results if r.grade == "Fail"),
        "pass": sum(1 for r in results if r.grade == "Pass"),
        "pass_plus": sum(1 for r in results if r.grade == "Pass +"),
        "avg": sum(r.total for r in results) / len(results),
    }


def format_summary(results: List[PaperResult], level_title: str) -> str:
    lines = [
        f"{level_title} — результаты проверки.",
        "Поле замен учтено; красные пометки на бланках не используются.",
        "",
    ]
    for r in results:
        sec = r.sections
        if "uoe" in sec:
            lines.append(
                f"{r.paper.file}  {r.paper.surname} {r.paper.name}:  "
                f"L={sec.get('listening', 0)}  R={sec.get('reading', 0)}  "
                f"UoE={sec.get('uoe', 0)}  Σ={r.total}  {r.grade}"
            )
        else:
            lines.append(
                f"{r.paper.file}  {r.paper.surname} {r.paper.name}:  "
                f"L={sec.get('listening', 0)}  R={sec.get('reading', 0)}  "
                f"UoE={sec.get('uoe', 0)}  Σ={r.total}  {r.grade}"
            )
        if r.replacements:
            lines.append(f"  замены: {r.replacements}")
    fail = sum(1 for r in results if r.grade == "Fail")
    pass_ = sum(1 for r in results if r.grade == "Pass")
    passp = sum(1 for r in results if r.grade == "Pass +")
    avg = sum(r.total for r in results) / len(results) if results else 0
    lines.extend(
        [
            "",
            f"Итого: {len(results)} работ | Fail {fail} | Pass {pass_} | Pass+ {passp}",
            f"Средний балл: {avg:.1f}",
        ]
    )
    return "\n".join(lines) + "\n"


def format_errors_detailed(results: List[PaperResult]) -> str:
    lines: List[str] = []
    for r in results:
        sec = r.sections
        lines.append(
            f"{r.paper.file} | {r.paper.surname} {r.paper.name} | "
            f"L={sec.get('listening', 0)} R={sec.get('reading', 0)} "
            f"UoE={sec.get('uoe', 0)} TOTAL={r.total} {r.grade}"
        )
        for err in r.errors:
            extra = f" | {err.detail}" if err.detail else ""
            lines.append(
                f"  Q{err.number}: ответ='{err.student}' | ключ='{err.key}' | "
                f"{err.points}{extra}"
            )
        lines.append("")
    return "\n".join(lines)


def results_to_csv_bytes(results: List[PaperResult]) -> bytes:
    import csv

    buf = io.StringIO()
    if not results:
        return b""
    fields = ["file", "surname", "name", "listening", "reading", "uoe", "total", "grade"]
    w = csv.DictWriter(buf, fieldnames=fields)
    w.writeheader()
    for r in results:
        w.writerow(
            {
                "file": r.paper.file,
                "surname": r.paper.surname,
                "name": r.paper.name,
                "listening": r.sections.get("listening", 0),
                "reading": r.sections.get("reading", 0),
                "uoe": r.sections.get("uoe", 0),
                "total": r.total,
                "grade": r.grade,
            }
        )
    return buf.getvalue().encode("utf-8")
