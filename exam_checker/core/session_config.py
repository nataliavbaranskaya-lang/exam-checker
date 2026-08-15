from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class SectionDef:
    id: str
    label: str
    from_q: int
    to_q: int

    @classmethod
    def from_dict(cls, d: dict) -> "SectionDef":
        return cls(
            id=d["id"],
            label=d.get("label", d["id"]),
            from_q=int(d.get("from_q", d.get("from"))),
            to_q=int(d.get("to_q", d.get("to"))),
        )


@dataclass
class WeightedDef:
    max_points: int
    type: str = "positional"

    @classmethod
    def from_dict(cls, d: dict) -> "WeightedDef":
        return cls(max_points=int(d["max_points"]), type=d.get("type", "positional"))


@dataclass
class ExcelColumn:
    col: int
    type: str
    section: str = ""
    formula: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "ExcelColumn":
        return cls(
            col=int(d["col"]),
            type=d["type"],
            section=d.get("section", ""),
            formula=d.get("formula", ""),
        )


@dataclass
class ExcelConfig:
    start_row: int
    columns: List[ExcelColumn]
    style_profile: str = ""
    style_row: Optional[int] = None

    @classmethod
    def from_dict(cls, d: dict) -> "ExcelConfig":
        style_row = d.get("style_row")
        return cls(
            start_row=int(d.get("start_row", 11)),
            columns=[ExcelColumn.from_dict(c) for c in d.get("columns", [])],
            style_profile=str(d.get("style_profile", "")),
            style_row=int(style_row) if style_row is not None else None,
        )


@dataclass
class SessionConfig:
    """Настройки сессии проверки — не зависят от жёстко зашитого уровня в коде."""

    title: str
    level_code: str
    question_count: int
    sections: List[SectionDef]
    grade_fail_below: int
    grade_pass_plus_from: int
    excel: ExcelConfig
    weighted: Dict[int, WeightedDef] = field(default_factory=dict)
    digit_questions: List[int] = field(default_factory=list)
    engine: str = "generic"

    @property
    def max_score(self) -> int:
        base = self.question_count - len(self.weighted)
        extra = sum(w.max_points - 1 for w in self.weighted.values())
        return base + extra

    @classmethod
    def from_dict(cls, d: dict) -> "SessionConfig":
        if not isinstance(d, dict):
            raise ValueError("config должен быть JSON-объектом {...}, не списком")
        weighted_raw = d.get("weighted", {})
        if not isinstance(weighted_raw, dict):
            weighted_raw = {}
        weighted = {
            int(k): WeightedDef.from_dict(v)
            for k, v in weighted_raw.items()
        }
        return cls(
            title=d.get("title", "Exam session"),
            level_code=d.get("level_code", "custom"),
            question_count=int(d["question_count"]),
            sections=[SectionDef.from_dict(s) for s in d["sections"]],
            grade_fail_below=int(d.get("grade_fail_below", 44)),
            grade_pass_plus_from=int(d.get("grade_pass_plus_from", 64)),
            excel=ExcelConfig.from_dict(d.get("excel", {})),
            weighted=weighted,
            digit_questions=[int(x) for x in d.get("digit_questions", [])],
            engine=d.get("engine", "generic"),
        )

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "level_code": self.level_code,
            "question_count": self.question_count,
            "sections": [
                {"id": s.id, "label": s.label, "from_q": s.from_q, "to_q": s.to_q}
                for s in self.sections
            ],
            "grade_fail_below": self.grade_fail_below,
            "grade_pass_plus_from": self.grade_pass_plus_from,
            "weighted": {
                str(k): {"max_points": v.max_points, "type": v.type}
                for k, v in self.weighted.items()
            },
            "digit_questions": self.digit_questions,
            "engine": self.engine,
            "excel": {
                "start_row": self.excel.start_row,
                "columns": [
                    {
                        "col": c.col,
                        "type": c.type,
                        **({"section": c.section} if c.section else {}),
                        **({"formula": c.formula} if c.formula else {}),
                    }
                    for c in self.excel.columns
                ],
            },
        }


PRESETS_DIR = Path(__file__).resolve().parents[1] / "presets"

LEVEL_CHOICES: List[tuple[str, str]] = [
    ("level_35", "Level A — 35 questions"),
    ("level_45", "Level B — 45 questions"),
    ("level_60", "Level C — 60 questions"),
    ("custom", "Custom configuration"),
]


def load_preset(level_code: str) -> SessionConfig:
    if level_code == "custom":
        return default_custom_config()
    path = PRESETS_DIR / f"{level_code}.json"
    if not path.exists():
        return default_custom_config(level_code)
    return SessionConfig.from_dict(json.loads(path.read_text(encoding="utf-8")))


def default_custom_config(level_code: str = "custom") -> SessionConfig:
    return SessionConfig.from_dict(
        {
            "title": "Custom level",
            "level_code": level_code,
            "question_count": 60,
            "sections": [
                {"id": "part1", "label": "Часть 1", "from_q": 1, "to_q": 20},
                {"id": "part2", "label": "Часть 2", "from_q": 21, "to_q": 40},
                {"id": "part3", "label": "Часть 3", "from_q": 41, "to_q": 60},
            ],
            "grade_fail_below": 44,
            "grade_pass_plus_from": 64,
            "excel": {
                "start_row": 11,
                "columns": [
                    {"col": 0, "type": "name"},
                    {"col": 1, "type": "section", "section": "part1"},
                    {"col": 2, "type": "section", "section": "part2"},
                    {"col": 3, "type": "section", "section": "part3"},
                    {"col": 4, "type": "empty"},
                    {"col": 5, "type": "total_formula", "formula": "SUM(B{row}:E{row})"},
                    {
                        "col": 6,
                        "type": "grade_formula",
                        "formula": 'IF(ISBLANK(F{row}),"",IF(F{row}<44,"Fail",IF(F{row}<=63,"Pass","Pass +")))',
                    },
                ],
            },
        }
    )
