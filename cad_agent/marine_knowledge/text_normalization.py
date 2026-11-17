"""Pure-Python text normalization for Marine CAD drawings (UTF-8, MTEXT, TCVN3)."""

from __future__ import annotations

import re
import unicodedata

# Standard TCVN3 (ABC / TCVN 5712) 1-byte glyph mapping to Unicode NFC.
_TCVN3_CHAR_MAP: dict[str, str] = {
    "¡": "Ă",
    "¢": "Â",
    "£": "Ê",
    "¤": "Ô",
    "¥": "Ơ",
    "¦": "Ư",
    "§": "Đ",
    "¨": "ă",
    "©": "â",
    "ª": "ê",
    "«": "ô",
    "¬": "ơ",
    "\xad": "ư",
    "®": "đ",
    "µ": "à",
    "¶": "ả",
    "·": "ã",
    "¸": "á",
    "¹": "ạ",
    "»": "ằ",
    "¼": "ẳ",
    "½": "ẵ",
    "¾": "ắ",
    "Æ": "ặ",
    "Ç": "ầ",
    "È": "ẩ",
    "É": "ẫ",
    "Ê": "ấ",
    "Ë": "ậ",
    "Ì": "è",
    "Î": "ẻ",
    "Ï": "ẽ",
    "Ð": "é",
    "Ñ": "ẹ",
    "Ò": "ề",
    "Ó": "ể",
    "Ô": "ễ",
    "Õ": "ế",
    "Ö": "ệ",
    "×": "ì",
    "Ø": "ỉ",
    "Ü": "ĩ",
    "Ý": "í",
    "Þ": "ị",
    "ß": "ò",
    "á": "ỏ",
    "â": "õ",
    "ã": "ó",
    "ä": "ọ",
    "å": "ồ",
    "æ": "ổ",
    "ç": "ỗ",
    "è": "ố",
    "é": "ộ",
    "ê": "ờ",
    "ë": "ở",
    "ì": "ỡ",
    "í": "ớ",
    "î": "ợ",
    "ï": "ù",
    "ñ": "ủ",
    "ò": "ũ",
    "ó": "ú",
    "ô": "ụ",
    "õ": "ừ",
    "ö": "ử",
    "÷": "ữ",
    "ø": "ứ",
    "ù": "ự",
    "ú": "ỳ",
    "û": "ỷ",
    "ü": "ỹ",
    "ý": "ý",
    "þ": "ỵ",
}
_TCVN3_TRANS = str.maketrans(_TCVN3_CHAR_MAP)

_EXCLUSIVE_TCVN3_CHARS = frozenset(
    "¡¢£¤¥¦§¨©ª«¬\xad®µ¶·¸¹»¼½¾ÆÇÈÉÊËÌÎÏÐÑÒÓÔÕÖ×ØÜÞßäåæçëìîïñòõö÷øùûüþ"
)
_MID_WORD_TCVN3_RE = re.compile(r"(?:[A-Za-z][ÝÌÐÒÓÕÙ]|uíi|UÍI)")
_MTEXT_FONT_RE = re.compile(r"\\[fF]([^;|\\]+)")
_MTEXT_CODE_RE = re.compile(r"\\(?:[fFcChHwWqQtTaA][^;]*;|[LOloKk~])")
_MTEXT_BREAK_RE = re.compile(r"\\[Pp]")


def strip_mtext_formatting(raw: str) -> tuple[str, str]:
    """Strip AutoCAD MTEXT inline control codes and recover embedded font hints."""
    text = raw or ""
    fonts = _MTEXT_FONT_RE.findall(text)
    font_hint = fonts[0].strip() if fonts else ""
    cleaned = _MTEXT_BREAK_RE.sub("\n", text)
    cleaned = _MTEXT_CODE_RE.sub("", cleaned)
    cleaned = cleaned.replace("{", "").replace("}", "").replace("\\S", "")
    return cleaned.strip(), font_hint


def _looks_like_tcvn3(text: str, font_hint: str) -> bool:
    # Never re-decode text that already contains Unicode characters above Latin-1.
    if any(ord(ch) > 0xFF for ch in text):
        return False
    hint = font_hint.lower()
    if ".vn" in hint or "tcvn" in hint:
        return True
    if any(ch in _EXCLUSIVE_TCVN3_CHARS for ch in text):
        return True
    return bool(_MID_WORD_TCVN3_RE.search(text))


def normalize_marine_cad_text(raw: str, *, font_hint: str = "") -> str:
    """Normalize MTEXT/TCVN3 marine CAD strings into clean Unicode NFC text."""
    stripped, embedded_font = strip_mtext_formatting(raw)
    effective_font = font_hint or embedded_font
    if _looks_like_tcvn3(stripped, effective_font):
        decoded = stripped.translate(_TCVN3_TRANS)
    else:
        decoded = stripped
    return unicodedata.normalize("NFC", decoded).strip()


def fold_marine_search_text(raw: str, *, font_hint: str = "") -> str:
    """Normalize and accent-fold text for deterministic bilingual alias matching."""
    text = normalize_marine_cad_text(raw, font_hint=font_hint)
    text = text.replace("đ", "d").replace("Đ", "D")
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", ascii_only.lower()).strip()
