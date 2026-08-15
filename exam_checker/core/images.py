from __future__ import annotations

import io
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ACCEPTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif"}
ACCEPTED_PDF_SUFFIX = {".pdf"}
ACCEPTED_SCAN_SUFFIXES = ACCEPTED_IMAGE_SUFFIXES | ACCEPTED_PDF_SUFFIX

DEFAULT_PDF_DPI = 200


def normalize_image(uploaded_name: str, data: bytes) -> Tuple[str, bytes]:
    suffix = Path(uploaded_name).suffix.lower()
    if suffix not in ACCEPTED_IMAGE_SUFFIXES:
        raise ValueError(f"Формат не поддерживается: {suffix}")

    if suffix in {".heic", ".heif"}:
        try:
            import pillow_heif
            from PIL import Image

            pillow_heif.register_heif_opener()
            img = Image.open(io.BytesIO(data))
            out = io.BytesIO()
            img.save(out, format="PNG")
            stem = Path(uploaded_name).stem
            return f"{stem}.png", out.getvalue()
        except ImportError as exc:
            raise ImportError(
                "Для HEIC установите: pip install pillow-heif pillow"
            ) from exc

    return uploaded_name, data


def pdf_pages_to_images(
    uploaded_name: str,
    data: bytes,
    dpi: int = DEFAULT_PDF_DPI,
) -> List[Tuple[str, bytes]]:
    """Каждая страница PDF → отдельный PNG (одна работа = одна страница)."""
    try:
        import fitz
    except ImportError as exc:
        raise ImportError(
            "Для PDF установите: pip install pymupdf"
        ) from exc

    doc = fitz.open(stream=data, filetype="pdf")
    stem = Path(uploaded_name).stem
    pages: List[Tuple[str, bytes]] = []
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    try:
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            page_id = f"{stem}_p{page_index + 1:03d}"
            pages.append((page_id, pix.tobytes("png")))
    finally:
        doc.close()

    return pages


def ingest_scans(
    uploads: Iterable[Tuple[str, bytes]],
    dpi: int = DEFAULT_PDF_DPI,
) -> Tuple[Dict[str, bytes], List[str], Dict[str, int]]:
    """
    Принимает пары (имя файла, байты).
    Возвращает словарь id→PNG, список ошибок и статистику загрузки.
    """
    images: Dict[str, bytes] = {}
    errors: List[str] = []
    stats = {"photos": 0, "pdf_files": 0, "pdf_pages": 0}

    for name, data in uploads:
        suffix = Path(name).suffix.lower()
        try:
            if suffix in ACCEPTED_PDF_SUFFIX:
                pages = pdf_pages_to_images(name, data, dpi=dpi)
                if not pages:
                    errors.append(f"{name}: PDF без страниц")
                    continue
                stats["pdf_files"] += 1
                stats["pdf_pages"] += len(pages)
                for page_id, png_data in pages:
                    unique_id = page_id
                    n = 2
                    while unique_id in images:
                        unique_id = f"{page_id}_{n}"
                        n += 1
                    images[unique_id] = png_data
            elif suffix in ACCEPTED_IMAGE_SUFFIXES:
                norm_name, norm_data = normalize_image(name, data)
                page_id = stem_id(norm_name)
                unique_id = page_id
                n = 2
                while unique_id in images:
                    unique_id = f"{page_id}_{n}"
                    n += 1
                images[unique_id] = norm_data
                stats["photos"] += 1
            else:
                errors.append(f"{name}: неподдерживаемый формат {suffix}")
        except Exception as exc:
            errors.append(f"{name}: {exc}")

    return images, errors, stats


def format_ingest_summary(stats: Dict[str, int], total: int) -> str:
    parts: List[str] = []
    if stats.get("photos"):
        parts.append(f"{stats['photos']} фото")
    if stats.get("pdf_files"):
        parts.append(
            f"{stats['pdf_files']} PDF ({stats['pdf_pages']} стр.)"
        )
    if not parts:
        return ""
    body = " + ".join(parts)
    return f"Загружено: {body} → **{total}** работ"


def stem_id(filename: str) -> str:
    return Path(filename).stem
