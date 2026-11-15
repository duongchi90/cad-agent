"""UTF-8-safe Vietnamese CAD encoding normalization and single accent-folding helper.

Safely strips AutoCAD MTEXT formatting, recovers embedded font hints, and decodes
TCVN3 (ABC), BK-VNC slash notation (e.g., ``vnc.shx``), and Cyrillic OCR homoglyphs
without corrupting modern UTF-8 Vietnamese or SI/engineering symbols.
"""

from __future__ import annotations

import functools
import re
import unicodedata
from typing import Dict, FrozenSet, Tuple

# Verified TCVN3 (ABC / TCVN 5712) -> Unicode NFC mapping calibrated against CAD DXFs.
_TCVN3_CHAR_MAP: Dict[str, str] = {
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

# Latin-1 chars that are valid UTF-8 Vietnamese NFC vowels MUST NEVER trigger unhinted TCVN3.
_UTF8_LATIN1_VIET_CHARS: FrozenSet[str] = frozenset(
    "àáâãèéêìíòóôõùúýÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝ"
)
# Also exclude contextual signs handled by regex guards: '§' (section), '×' (multiply), 'µ' (SI micro).
_TCVN3_EXCLUSIVE_CHARS: FrozenSet[str] = (
    frozenset(_TCVN3_CHAR_MAP)
    - _UTF8_LATIN1_VIET_CHARS
    - frozenset({"§", "×", "µ"})
)

_UTF8_EXCLUSIVE_VIET_CHARS: FrozenSet[str] = frozenset(
    "ăđơưĂĐƠƯ"
    "ạảấầẩẫậắằẳẵặ"
    "ẹẻẽếềểễệ"
    "ỉị"
    "ọỏốồổỗộớờởỡợ"
    "ụủứừửữự"
    "ỳỷỹỵ"
    "ẠẢẤẦẨẪẬẮẰẲẴẶ"
    "ẸẺẼẾỀỂỄỆ"
    "ỈỊ"
    "ỌỎỐỒỔỖỘỚỜỞỠỢ"
    "ỤỦỨỪỬỮỰ"
    "ỲỶỸỴ"
)

_VNC_SLASH_BASE: Dict[Tuple[str, str], str] = {
    ("A", "M"): "Â",
    ("A", "W"): "Ă",
    ("E", "M"): "Ê",
    ("O", "M"): "Ô",
    ("O", "W"): "Ơ",
    ("U", "W"): "Ư",
    ("a", "m"): "â",
    ("a", "w"): "ă",
    ("e", "m"): "ê",
    ("o", "m"): "ô",
    ("o", "w"): "ơ",
    ("u", "w"): "ư",
}

_VNC_TONES: Dict[str, Dict[str, str]] = {
    "A": {"S": "Á", "F": "À", "R": "Ả", "X": "Ã", "J": "Ạ"},
    "E": {"S": "É", "F": "È", "R": "Ẻ", "X": "Ẽ", "J": "Ẹ"},
    "I": {"S": "Í", "F": "Ì", "R": "Ỉ", "X": "Ĩ", "J": "Ị"},
    "O": {"S": "Ó", "F": "Ò", "R": "Ỏ", "X": "Õ", "J": "Ọ"},
    "U": {"S": "Ú", "F": "Ù", "R": "Ủ", "X": "Ũ", "J": "Ụ"},
    "Y": {"S": "Ý", "F": "Ỳ", "R": "Ỷ", "X": "Ỹ", "J": "Ỵ"},
    "Â": {"S": "Ấ", "F": "Ầ", "R": "Ẩ", "X": "Ẫ", "J": "Ậ"},
    "Ă": {"S": "Ắ", "F": "Ằ", "R": "Ẳ", "X": "Ẵ", "J": "Ặ"},
    "Ê": {"S": "Ế", "F": "Ề", "R": "Ể", "X": "Ễ", "J": "Ệ"},
    "Ô": {"S": "Ố", "F": "Ồ", "R": "Ổ", "X": "Ỗ", "J": "Ộ"},
    "Ơ": {"S": "Ớ", "F": "Ờ", "R": "Ở", "X": "Ỡ", "J": "Ợ"},
    "Ư": {"S": "Ứ", "F": "Ừ", "R": "Ử", "X": "Ữ", "J": "Ự"},
    "a": {"S": "á", "F": "à", "R": "ả", "X": "ã", "J": "ạ"},
    "e": {"S": "é", "F": "è", "R": "ẻ", "X": "ẽ", "J": "ẹ"},
    "i": {"S": "í", "F": "ì", "R": "ỉ", "X": "ĩ", "J": "ị"},
    "o": {"S": "ó", "F": "ò", "R": "ỏ", "X": "õ", "J": "ọ"},
    "u": {"S": "ú", "F": "ù", "R": "ủ", "X": "ũ", "J": "ụ"},
    "y": {"S": "ý", "F": "ỳ", "R": "ỷ", "X": "ỹ", "J": "ỵ"},
    "â": {"S": "ấ", "F": "ầ", "R": "ẩ", "X": "ẫ", "J": "ậ"},
    "ă": {"S": "ắ", "F": "ằ", "R": "ẳ", "X": "ẵ", "J": "ặ"},
    "ê": {"S": "ế", "F": "ề", "R": "ể", "X": "ễ", "J": "ệ"},
    "ô": {"S": "ố", "F": "ồ", "R": "ổ", "X": "ỗ", "J": "ộ"},
    "ơ": {"S": "ớ", "F": "ờ", "R": "ở", "X": "ỡ", "J": "ợ"},
    "ư": {"S": "ứ", "F": "ừ", "R": "ử", "X": "ữ", "J": "ự"},
}

_CYRILLIC_LOOKALIKES = str.maketrans({
    "А": "A",
    "В": "B",
    "Е": "E",
    "К": "K",
    "М": "M",
    "Н": "H",
    "О": "O",
    "Р": "P",
    "С": "C",
    "Т": "T",
    "Х": "X",
    "І": "I",
    "а": "a",
    "е": "e",
    "к": "k",
    "м": "m",
    "о": "o",
    "р": "p",
    "с": "c",
    "т": "t",
    "х": "x",
    "і": "i",
    "л": "l",
    "п": "n",
})

_MTEXT_FONT_RE = re.compile(r"\\f([^|;\\{}]+)(?:\|[^;]*)?;", re.I)
_VNC_TOKEN_RE = re.compile(
    r"(?<![0-9/])([Dd]/[Dd]|[AEIOUYaeiouy]/(?:[MWmw](?:/[SFRXJsfrxj])?|[SFRXJsfrxj]))(?=[A-Za-zÀ-ỹ.,:;!?)\]\s]|$)"
)
_TCVN3_FONT_RE = re.compile(r"(?:^\.?vn(?!i)|vnc|tcvn|abc)", re.I)
_SI_MICRO_RE = re.compile(r"(?:^|[\d\s])µ[mMsSVAWgGFH](?=$|[^A-Za-zÀ-ỹ])")
_CACHE_MAX_LEN = 512


def strip_mtext_and_extract_font(raw_text: str) -> Tuple[str, str]:
    """Strip AutoCAD MTEXT formatting & control codes while recovering the first inline font."""
    if not raw_text:
        return "", ""
    m_font = _MTEXT_FONT_RE.search(raw_text)
    font_hint = m_font.group(1).strip() if m_font else ""

    out = raw_text
    out = re.sub(r"\\S([^;^\\]*)\^([^;\\]*);", r"\1/\2", out)
    out = out.replace("\\P", " ").replace("\\~", " ")
    out = re.sub(r"\\[fFHWCQTAplok][^;\\{}]*;", "", out)
    out = re.sub(r"\\[LlOoKk]", "", out)
    out = out.replace("{", "").replace("}", "")
    out = re.sub(r"\s+", " ", out).strip()
    return out, font_hint


def _apply_autocad_symbol_codes(text: str) -> str:
    """Expand %%d/%%c/%%p/%%u after charset decoding so Ø does not collide with TCVN3."""
    out = re.sub(r"%%[dD]", "°", text)
    out = re.sub(r"%%[cC]", "Ø", out)
    out = re.sub(r"%%[pP]", "±", out)
    out = re.sub(r"%%[uUoO]", "", out)
    return out


def _contains_unhinted_tcvn3_signal(text: str) -> bool:
    """Return True if text carries unmistakable TCVN3 bytes and no exclusive UTF-8 Vietnamese."""
    if any(ch in _UTF8_EXCLUSIVE_VIET_CHARS for ch in text):
        return False
    if any(ch in _TCVN3_EXCLUSIVE_CHARS for ch in text):
        return True
    if "µ" in text:
        without_si = _SI_MICRO_RE.sub(" ", text)
        if "µ" in without_si:
            return True
    if "§" in text and re.search(r"§[A-Za-z]", text):
        return True
    if re.search(r"[a-z]Ý[a-z]", text):
        return True
    if re.search(r"(?<!\d)[A-Za-zÀ-þ]×[A-Za-zÀ-þ]", text):
        return True
    return False


def _decode_vnc_slash(text: str, *, explicit_vnc: bool = False) -> Tuple[str, bool]:
    """Decode BK-VNC ASCII slash-accent Vietnamese like 'CA/SC THO/MNG SO/M/S'."""
    if "/" not in text:
        return text, False
    changed = False

    def _repl(match: re.Match[str]) -> str:
        nonlocal changed
        seq = match.group(1)
        parts = seq.split("/")
        if len(parts) == 2 and parts[0] in ("D", "d") and parts[1] in ("D", "d"):
            changed = True
            return "Đ" if parts[0] == "D" else "đ"
        base = parts[0]
        mod = parts[1].upper()
        if len(parts) == 3:
            key = (base, mod if base.isupper() else mod.lower())
            mod_char = _VNC_SLASH_BASE.get(key)
            if mod_char:
                toned = _VNC_TONES.get(mod_char, {}).get(parts[2].upper())
                if toned:
                    changed = True
                    return toned
        elif len(parts) == 2:
            if mod in ("M", "W"):
                key = (base, mod if base.isupper() else mod.lower())
                mod_char = _VNC_SLASH_BASE.get(key)
                if mod_char:
                    changed = True
                    return mod_char
            else:
                toned = _VNC_TONES.get(base, {}).get(mod)
                if toned:
                    changed = True
                    return toned
        return seq

    out_tokens = []
    for tok in text.split(" "):
        m_vnc = _VNC_TOKEN_RE.search(tok) if "/" in tok else None
        if m_vnc:
            core = tok.strip(".,:;!?()[]")
            has_double_mod = "/M/" in tok or "/W/" in tok or "/m/" in tok or "/w/" in tok
            is_embedded_word = len(core) > len(m_vnc.group(1))
            alpha_only = [c for c in core if c.isalpha()]
            upper_ratio = sum(1 for c in alpha_only if c.isupper()) / max(1, len(alpha_only))
            if explicit_vnc or has_double_mod or (is_embedded_word and upper_ratio >= 0.7):
                tok = _VNC_TOKEN_RE.sub(_repl, tok)
        out_tokens.append(tok)
    return " ".join(out_tokens), changed


def _decode_vietnamese_cad_text_impl(
    raw_text: str,
    font_hint: str = "",
    doc_encoding: str = "",
) -> Tuple[str, str]:
    """Decode CAD MTEXT, TCVN3, and BK-VNC without corrupting UTF-8 Vietnamese."""
    cleaned, inline_font = strip_mtext_and_extract_font(raw_text or "")
    if not cleaned:
        return "", "empty"

    effective_font = inline_font or font_hint
    font_is_tcvn3 = bool(effective_font and _TCVN3_FONT_RE.search(effective_font))
    explicit_vnc = doc_encoding == "bk_vnc" or bool(effective_font and "vnc" in effective_font.lower())
    has_utf8_viet = any(ch in _UTF8_EXCLUSIVE_VIET_CHARS for ch in cleaned)

    encoding_used = "utf8"
    decoded = cleaned

    if font_is_tcvn3 and not has_utf8_viet:
        decoded = decoded.translate(_TCVN3_TRANS)
        encoding_used = "tcvn3"
    elif has_utf8_viet:
        toks = []
        tok_changed = False
        for tok in decoded.split(" "):
            if _contains_unhinted_tcvn3_signal(tok):
                toks.append(tok.translate(_TCVN3_TRANS))
                tok_changed = True
            else:
                toks.append(tok)
        if tok_changed:
            decoded = " ".join(toks)
            encoding_used = "mixed_utf8_tcvn3"
    elif _contains_unhinted_tcvn3_signal(decoded):
        decoded = decoded.translate(_TCVN3_TRANS)
        encoding_used = "tcvn3"
    elif doc_encoding == "tcvn3":
        if any(ch in _TCVN3_CHAR_MAP for ch in decoded) and not re.search(r"\d\s*×\s*\d", decoded):
            decoded = decoded.translate(_TCVN3_TRANS)
            encoding_used = "tcvn3_doc_context"

    if encoding_used.startswith("tcvn3") and effective_font and effective_font.upper().endswith("H"):
        if re.search(r"[A-Z].*[A-Z]", cleaned):
            decoded = decoded.upper()

    vnc_decoded, vnc_hit = _decode_vnc_slash(decoded, explicit_vnc=explicit_vnc)
    if vnc_hit:
        decoded = vnc_decoded
        encoding_used = "bk_vnc" if encoding_used == "utf8" else f"{encoding_used}+bk_vnc"

    decoded = _apply_autocad_symbol_codes(decoded)
    return decoded, encoding_used


@functools.lru_cache(maxsize=16384)
def _decode_cached(raw_text: str, font_hint: str, doc_encoding: str) -> Tuple[str, str]:
    return _decode_vietnamese_cad_text_impl(raw_text, font_hint, doc_encoding)


def decode_vietnamese_cad_text(
    raw_text: str,
    font_hint: str = "",
    doc_encoding: str = "",
) -> Tuple[str, str]:
    """Decode CAD MTEXT/TCVN3/BK-VNC text with bounded LRU caching for short strings."""
    if raw_text and len(raw_text) > _CACHE_MAX_LEN:
        return _decode_vietnamese_cad_text_impl(raw_text, font_hint, doc_encoding)
    return _decode_cached(raw_text, font_hint, doc_encoding)


def _fold_vietnamese_cad_text_impl(
    text: str,
    font_hint: str = "",
    doc_encoding: str = "",
) -> str:
    decoded, _ = decode_vietnamese_cad_text(text, font_hint=font_hint, doc_encoding=doc_encoding)
    if decoded.isascii():
        return " ".join(decoded.lower().replace("_", " ").split())
    out = decoded.translate(_CYRILLIC_LOOKALIKES)
    out = out.replace("đ", "d").replace("Đ", "D")
    out = unicodedata.normalize("NFD", out)
    out = "".join(ch for ch in out if unicodedata.category(ch) != "Mn")
    return " ".join(out.lower().replace("_", " ").split())


@functools.lru_cache(maxsize=16384)
def _fold_cached(text: str, font_hint: str, doc_encoding: str) -> str:
    return _fold_vietnamese_cad_text_impl(text, font_hint, doc_encoding)


def fold_vietnamese_cad_text(
    text: str,
    font_hint: str = "",
    doc_encoding: str = "",
) -> str:
    """Single accent-folding helper combining safe CAD decoding, homoglyph cleanup, and NFD fold."""
    if text and len(text) > _CACHE_MAX_LEN:
        return _fold_vietnamese_cad_text_impl(text, font_hint, doc_encoding)
    return _fold_cached(text, font_hint, doc_encoding)


__all__ = [
    "decode_vietnamese_cad_text",
    "fold_vietnamese_cad_text",
    "strip_mtext_and_extract_font",
]
