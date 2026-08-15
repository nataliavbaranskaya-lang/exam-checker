"""Handwritten exam sheets — optional Vision API transcription."""

from __future__ import annotations

import base64
import io
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

DEFAULT_MODELS = {
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-4-20250514",
}

PROVIDER_ENV_KEYS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


@dataclass
class TranscriptionResult:
    surname: str = ""
    name: str = ""
    answers: Dict[int, str] = field(default_factory=dict)
    replacements: Dict[int, str] = field(default_factory=dict)
    uncertain: List[int] = field(default_factory=list)
    notes: str = ""
    provider: str = ""
    model: str = ""


class TranscriptionError(Exception):
    pass


def resolve_api_key(provider: str, override: str = "") -> str:
    key = (override or "").strip()
    if key:
        return key
    env_name = PROVIDER_ENV_KEYS.get(provider, "")
    return (os.environ.get(env_name) or "").strip()


def preprocess_image(image_bytes: bytes, max_width: int = 1800) -> tuple[bytes, str]:
    """Уменьшить большой скан и вернуть PNG + media_type."""
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    w, h = img.size
    if w > max_width:
        ratio = max_width / w
        img = img.resize((max_width, int(h * ratio)), Image.Resampling.LANCZOS)

    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue(), "image/png"


def build_prompt(question_count: int, level_title: str) -> str:
    return f"""You transcribe filled English exam answer sheets ({level_title}).

Read the entire form carefully.

Steps:
1. Surname and first name in the header.
2. Corrections / replacement block (if present): question number → corrected answer.
3. Main answer grid, questions 1–{question_count}.

Rules:
- Use only the student's BLACK handwriting. Ignore red teacher marks.
- Multiple-choice items: Arabic digits only (1/2/3/4).
- Word answers: UPPERCASE Latin letters, NO spaces (e.g. TWENTYSIXTH).
- Email / addresses: as written, uppercase where possible, no spaces.
- Empty cell → "".
- If unreadable, best guess + add question number to "uncertain".

Return ONLY JSON (no markdown):
{{
  "surname": "...",
  "name": "...",
  "answers": {{"1": "...", "2": "...", ... up to {question_count}}},
  "replacements": {{"35": "5"}},
  "uncertain": [14, 20],
  "notes": "brief note on difficult areas"
}}

Keys in answers and replacements are string question numbers."""


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise TranscriptionError("Модель не вернула JSON") from None
        return json.loads(match.group(0))


def _normalize_answer(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    if re.fullmatch(r"[0-9]+", s):
        return s
    s = s.upper()
    s = re.sub(r"\s+", "", s)
    return s


def _parse_int_map(raw: Any) -> Dict[int, str]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[int, str] = {}
    for k, v in raw.items():
        try:
            num = int(str(k).strip())
        except ValueError:
            continue
        out[num] = _normalize_answer(v)
    return out


def parse_transcription_payload(payload: dict) -> TranscriptionResult:
    uncertain_raw = payload.get("uncertain") or []
    uncertain: List[int] = []
    for item in uncertain_raw:
        try:
            uncertain.append(int(item))
        except (TypeError, ValueError):
            pass

    return TranscriptionResult(
        surname=str(payload.get("surname") or "").strip(),
        name=str(payload.get("name") or "").strip(),
        answers=_parse_int_map(payload.get("answers")),
        replacements=_parse_int_map(payload.get("replacements")),
        uncertain=sorted(set(uncertain)),
        notes=str(payload.get("notes") or "").strip(),
    )


def apply_transcription(paper, result: TranscriptionResult) -> None:
    """Записать результат OCR в PaperData."""
    paper.surname = result.surname
    paper.name = result.name
    paper.answers = result.answers
    paper.replacements = result.replacements
    paper.uncertain = result.uncertain
    note_parts = [p for p in [paper.notes, result.notes] if p.strip()]
    if result.uncertain:
        note_parts.append(f"OCR сомнения: {result.uncertain}")
    paper.notes = " | ".join(dict.fromkeys(note_parts))


def transcribe_image(
    image_bytes: bytes,
    question_count: int,
    level_title: str,
    *,
    provider: str = "openai",
    api_key: str = "",
    model: Optional[str] = None,
) -> TranscriptionResult:
    provider = provider.lower().strip()
    key = resolve_api_key(provider, api_key)
    if not key:
        env = PROVIDER_ENV_KEYS.get(provider, "API_KEY")
        raise TranscriptionError(
            f"Нет API-ключа для {provider}. Укажите в интерфейсе или переменной {env}."
        )

    png_bytes, media_type = preprocess_image(image_bytes)
    prompt = build_prompt(question_count, level_title)
    chosen_model = model or DEFAULT_MODELS.get(provider, "")

    if provider == "openai":
        raw_text = _call_openai(key, chosen_model, png_bytes, media_type, prompt)
    elif provider == "anthropic":
        raw_text = _call_anthropic(key, chosen_model, png_bytes, media_type, prompt)
    else:
        raise TranscriptionError(f"Неизвестный провайдер: {provider}")

    payload = _extract_json(raw_text)
    result = parse_transcription_payload(payload)
    result.provider = provider
    result.model = chosen_model

    for n in range(1, question_count + 1):
        result.answers.setdefault(n, "")

    return result


def _call_openai(
    api_key: str,
    model: str,
    image_bytes: bytes,
    media_type: str,
    prompt: str,
) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise TranscriptionError(
            "Установите пакет openai: pip install openai"
        ) from exc

    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    client = OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{media_type};base64,{b64}"},
                        },
                    ],
                }
            ],
        )
    except Exception as exc:
        raise TranscriptionError(f"OpenAI: {exc}") from exc

    return response.choices[0].message.content or ""


def _call_anthropic(
    api_key: str,
    model: str,
    image_bytes: bytes,
    media_type: str,
    prompt: str,
) -> str:
    try:
        import anthropic
    except ImportError as exc:
        raise TranscriptionError(
            "Установите пакет anthropic: pip install anthropic"
        ) from exc

    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    client = anthropic.Anthropic(api_key=api_key)
    try:
        message = client.messages.create(
            model=model,
            max_tokens=8192,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": prompt + "\n\nОтвет — только JSON."},
                    ],
                }
            ],
        )
    except Exception as exc:
        raise TranscriptionError(f"Anthropic: {exc}") from exc

    parts = []
    for block in message.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "\n".join(parts)
