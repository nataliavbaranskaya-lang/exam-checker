from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class PaperData:
    file: str
    surname: str = ""
    name: str = ""
    answers: Dict[int, str] = field(default_factory=dict)
    replacements: Dict[int, str] = field(default_factory=dict)
    uncertain: List[int] = field(default_factory=list)
    notes: str = ""

    def to_raw(self) -> dict:
        raw = {
            "file": self.file,
            "surname": self.surname,
            "name": self.name,
            "a": {str(k): v for k, v in self.answers.items()},
            "repl": {str(k): v for k, v in self.replacements.items()},
        }
        if self.uncertain:
            raw["uncertain"] = self.uncertain
        if self.notes:
            raw["notes"] = self.notes
        return raw

    @classmethod
    def from_raw(cls, raw: dict) -> "PaperData":
        uncertain_raw = raw.get("uncertain") or []
        uncertain: List[int] = []
        for item in uncertain_raw:
            try:
                uncertain.append(int(item))
            except (TypeError, ValueError):
                pass
        return cls(
            file=raw["file"],
            surname=raw.get("surname", ""),
            name=raw.get("name", ""),
            answers={int(k): str(v) for k, v in raw.get("a", {}).items()},
            replacements={int(k): str(v) for k, v in raw.get("repl", {}).items()},
            uncertain=uncertain,
            notes=raw.get("notes", ""),
        )


@dataclass
class QuestionError:
    number: int
    student: str
    key: str
    points: str
    detail: str = ""


@dataclass
class PaperResult:
    paper: PaperData
    sections: Dict[str, int]
    total: int
    grade: str
    errors: List[QuestionError] = field(default_factory=list)
    replacements: Dict[int, str] = field(default_factory=dict)


@dataclass
class LevelInfo:
    code: str
    title: str
    question_count: int
    max_test_score: int
    pass_fail_thresholds: tuple[int, int]
