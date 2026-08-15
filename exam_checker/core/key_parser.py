from __future__ import annotations

import json
import platform
import re
import subprocess
import tempfile
import zipfile
from io import BytesIO, StringIO
from pathlib import Path
from typing import Dict, List, Union

KeySource = Union[Path, bytes, str]

OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
ZIP_MAGIC = b"PK"

SKIP_TOKENS = {
    "key",
    "listening",
    "reading",
    "use of english",
    "writing",
    "speaking",
    "(",
    ")",
    "-",
    "pre-intermediate b1",
    "pre-intermediate b1-",
    "intermediate-plus (b1+)",
    "elementary (a2)",
}

SKIP_TOKEN_RE = re.compile(
    r"^(pre-intermediate|intermediate|elementary|upper|advanced|b1|b2|a2|a1|plus|\(\)|\(\s*\))$",
    re.I,
)


def parse_key_file(path: Path) -> Dict[int, str]:
    return parse_key_bytes(path.name, path.read_bytes())


def parse_key_bytes(filename: str, data: bytes) -> Dict[int, str]:
    if data.startswith(ZIP_MAGIC):
        return _parse_docx_bytes(data)
    if data.startswith(OLE_MAGIC):
        return _parse_doc_bytes(data)

    suffix = Path(filename).suffix.lower()
    if suffix == ".doc":
        return _parse_doc_bytes(data)
    if suffix == ".docx":
        return _parse_docx_bytes(data)
    if suffix == ".py":
        return _parse_key_py_text(data.decode("utf-8", errors="replace"))
    if suffix == ".json":
        return _parse_key_json(data.decode("utf-8"))
    if suffix == ".csv":
        return _parse_key_csv(data.decode("utf-8"))
    if suffix in {".txt", ".tsv"}:
        return _parse_key_txt(data.decode("utf-8"))
    raise ValueError(
        f"Формат ключа не распознан ({suffix or 'без расширения'}). "
        "Поддерживаются: DOC, DOCX, JSON, CSV, TXT, PY."
    )


def _parse_key_json(text: str) -> Dict[int, str]:
    raw = json.loads(text)
    if isinstance(raw, dict):
        if "answers" in raw:
            raw = raw["answers"]
        return {int(k): str(v) for k, v in raw.items()}
    if isinstance(raw, list):
        out: Dict[int, str] = {}
        for item in raw:
            out[int(item["q"])] = str(item["answer"])
        return dict(sorted(out.items()))
    raise ValueError("JSON ключа: ожидается объект {номер: ответ} или список {q, answer}")


def _parse_key_csv(text: str) -> Dict[int, str]:
    import csv

    out: Dict[int, str] = {}
    reader = csv.reader(StringIO(text))
    rows = list(reader)
    if not rows:
        return out
    header = [h.strip().lower() for h in rows[0]]
    if "q" in header or "question" in header or "номер" in header:
        q_idx = next(
            i for i, h in enumerate(header) if h in ("q", "question", "номер", "n")
        )
        a_idx = next(
            i for i, h in enumerate(header) if h in ("answer", "key", "ответ", "a")
        )
        for row in rows[1:]:
            if len(row) > max(q_idx, a_idx):
                out[int(row[q_idx].strip())] = row[a_idx].strip()
    else:
        for row in rows:
            if len(row) >= 2 and row[0].strip().isdigit():
                out[int(row[0].strip())] = row[1].strip()
    return dict(sorted(out.items()))


def _parse_key_txt(text: str) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
        elif "\t" in line:
            k, v = line.split("\t", 1)
        elif re.match(r"^\d+\s+", line):
            k, v = line.split(None, 1)
        else:
            continue
        if k.strip().isdigit():
            out[int(k.strip())] = v.strip()
    return dict(sorted(out.items()))


def _parse_key_py_text(text: str) -> Dict[int, str]:
    ns: dict = {}
    exec(text, ns)
    out: Dict[int, str] = {}
    for name, val in ns.items():
        if name.startswith("KEY_") and isinstance(val, dict):
            for k, v in val.items():
                out[int(k)] = str(v)
        elif name == "KEY" and isinstance(val, dict):
            for k, v in val.items():
                out[int(k)] = str(v)
        elif name == "KEY_Q1" and isinstance(val, list):
            out[1] = "".join(val)
        elif name.startswith("KEY_Q") and isinstance(val, list):
            m = re.match(r"KEY_Q(\d+)$", name)
            if m:
                out[int(m.group(1))] = "".join(val)
    return dict(sorted(out.items()))


def _key_looks_valid(key: Dict[int, str]) -> bool:
    if len(key) < 5:
        return False
    for v in key.values():
        if len(v) > 40:
            return False
        if sum(ch.isalpha() for ch in v if "A" <= ch.upper() <= "Z") > 12:
            return False
    return True


def _parse_doc_tab_table_text(text: str) -> Dict[int, str]:
    pairs = re.findall(r"(\d{1,2})\x07(\d)", text)
    if len(pairs) < 5:
        return {}
    out: Dict[int, str] = {}
    for q, ans in pairs:
        qi = int(q)
        if qi not in out:
            out[qi] = ans
    return dict(sorted(out.items()))


def _parse_doc_via_textutil(data: bytes) -> Dict[int, str]:
    if platform.system() != "Darwin":
        return {}
    import os

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        text = subprocess.check_output(
            ["textutil", "-convert", "txt", "-stdout", tmp_path],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8", errors="ignore")
    except (OSError, subprocess.CalledProcessError, FileNotFoundError):
        return {}
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    tab_key = _parse_doc_tab_table_text(text)
    if _key_looks_valid(tab_key):
        return tab_key
    tokens = [t.strip() for t in re.split(r"[\x07\x0b\x0c]+", text) if t.strip()]
    parsed = _parse_key_tokens(tokens)
    return parsed if _key_looks_valid(parsed) else {}


def _parse_doc_bytes(data: bytes) -> Dict[int, str]:
    textutil_key = _parse_doc_via_textutil(data)
    if _key_looks_valid(textutil_key):
        return textutil_key

    try:
        from olefile import OleFileIO
    except ImportError as exc:
        raise ImportError(
            "Для KEY.doc установите olefile: pip install olefile"
        ) from exc

    ole = OleFileIO(BytesIO(data))
    raw = ole.openstream("WordDocument").read()
    tokens: List[str] = []
    for encoding in ("cp1251", "latin1", "utf-16le"):
        text = raw.decode(encoding, errors="ignore")
        tab_key = _parse_doc_tab_table_text(text)
        if _key_looks_valid(tab_key):
            return tab_key
        tokens = _tokens_from_doc_text(text)
        if len(tokens) >= 10:
            break
    if not tokens:
        raise ValueError("Не удалось извлечь текст из KEY.doc")
    parsed = _parse_key_tokens(tokens)
    if _key_looks_valid(parsed):
        return parsed
    if _key_looks_valid(textutil_key):
        return textutil_key
    return parsed


def _parse_docx_bytes(data: bytes) -> Dict[int, str]:
    with zipfile.ZipFile(BytesIO(data)) as zf:
        xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
    tokens = re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml)
    tokens = [t.strip() for t in tokens if t.strip()]
    if not tokens:
        raise ValueError("Не удалось извлечь текст из KEY.docx")
    return _parse_key_tokens(tokens)


def _tokens_from_doc_text(text: str) -> List[str]:
    parts = re.split(r"[\x07\x0b\x0c]", text)
    tokens: List[str] = []
    for part in parts:
        s = re.sub(r"[\x00-\x06\x08-\x1f\x7f-\x9f]", "", part)
        s = re.sub(r"\s+", " ", s).strip()
        if not s or len(s) > 100:
            continue
        alnum = sum(ch.isalnum() for ch in s)
        if alnum == 0:
            continue
        if alnum < len(s) * 0.35 and len(s) > 8:
            continue
        if len(s) > 15 and re.search(r"\b(LISTENING|READING|USE OF ENGLISH|KEY)\b", s, re.I):
            for piece in re.split(
                r"(?=\bListening\b)|(?=\bReading\b)|(?=\bUse of English\b)|(?=\bKEY\b)",
                s,
                flags=re.I,
            ):
                piece = piece.strip(" -")
                if piece:
                    tokens.extend(_split_merged_header(piece))
            continue
        tokens.append(s)
    return tokens


def _split_merged_header(piece: str) -> List[str]:
    out: List[str] = []
    for chunk in re.split(r"\s{2,}", piece):
        chunk = chunk.strip()
        if chunk:
            out.append(chunk)
    return out or [piece]


def _should_skip_token(token: str) -> bool:
    t = token.strip()
    if not t:
        return True
    low = re.sub(r"\s+", " ", t.lower())
    if low in SKIP_TOKENS:
        return True
    if SKIP_TOKEN_RE.match(low):
        return True
    if re.fullmatch(r"\d{5,}", t):
        return True
    if len(t) == 1 and t in {"(", ")", "-"}:
        return True
    return False


def _parse_key_tokens(tokens: List[str]) -> Dict[int, str]:
    start = 0
    for i, token in enumerate(tokens):
        if token.strip().upper() == "KEY":
            start = i + 1
            break

    work = [t.strip() for t in tokens[start:] if t.strip() and not _should_skip_token(t)]
    out: Dict[int, str] = {}
    i = 0
    while i < len(work):
        token = work[i]
        if not re.fullmatch(r"\d+", token):
            i += 1
            continue

        q = int(token)
        if q < 1 or q > 120:
            i += 1
            continue
        if q in out:
            i += 1
            continue
        if i + 1 >= len(work):
            break

        answer, nxt = _consume_answer(work, i + 1, q)
        if answer:
            out[q] = answer
        i = nxt if nxt > i else i + 1

    return dict(sorted(out.items()))


def _consume_answer(tokens: List[str], start: int, question: int) -> tuple[str, int]:
    if start >= len(tokens):
        return "", start

    first = tokens[start]

    if _is_word_like_answer(first):
        parts = [first]
        j = start + 1
        while j < len(tokens):
            if _is_question_start(tokens, j):
                break
            if _should_skip_token(tokens[j]):
                j += 1
                continue
            parts.append(tokens[j])
            j += 1
        return _normalize_answer(" ".join(parts)), j

    if re.fullmatch(r"\d", first):
        digits = [first]
        j = start + 1
        positional = question in {1, 2, 10, 11}
        while j < len(tokens) and re.fullmatch(r"\d", tokens[j]):
            cand = tokens[j]
            if positional:
                if len(cand) >= 2 and int(cand) >= 10:
                    break
                if len(digits) == 1 and j + 1 < len(tokens):
                    ahead = tokens[j + 1]
                    if re.fullmatch(r"\d+", ahead) and int(ahead) >= 40:
                        break
            elif _is_question_start(tokens, j):
                break
            digits.append(cand)
            j += 1
        if len(digits) > 1 and positional:
            return "".join(digits), j
        if len(digits) > 1 and _looks_like_positional_chain(
            digits, tokens, j, question
        ):
            return "".join(digits), j
        return digits[0], start + 1

    if re.fullmatch(r"\d+", first):
        return _normalize_answer(first), start + 1

    return _normalize_answer(first), start + 1


def _is_word_like_answer(token: str) -> bool:
    if re.search(r"[A-Za-z/@]", token):
        return True
    if "/" in token:
        return True
    return False


def _looks_like_positional_chain(
    digits: List[str], tokens: List[str], j: int, question: int
) -> bool:
    if len(digits) < 2:
        return False
    if question not in {1, 2, 10, 11}:
        return False
    if j < len(tokens):
        nxt = tokens[j]
        if re.fullmatch(r"\d+", nxt) and int(nxt) >= 10:
            return True
        if _is_word_like_answer(nxt):
            return True
    return len(digits) >= 4


def _is_question_start(tokens: List[str], j: int) -> bool:
    if j >= len(tokens):
        return False
    cand = tokens[j].strip()
    if _should_skip_token(cand):
        return False
    if not re.fullmatch(r"\d+", cand):
        return False
    q = int(cand)
    if q < 1 or q > 120:
        return False
    if j + 1 >= len(tokens):
        return True
    nxt = tokens[j + 1].strip()
    if _should_skip_token(nxt):
        return True
    if _is_word_like_answer(nxt):
        return True
    if re.fullmatch(r"\d", nxt):
        return True
    if re.fullmatch(r"\d+", nxt) and int(cand) >= 10:
        return True
    return False


def _normalize_answer(value: str) -> str:
    value = re.sub(r"\s+", " ", value.strip())
    if re.fullmatch(r"\d+", value):
        return value
    if re.search(r"[A-Za-z]", value):
        return value.replace(" ", "")
    return value.upper()
