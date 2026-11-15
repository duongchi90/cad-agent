from __future__ import annotations

import pytest

from primitive_ir_lib.vietnamese_encoding import (
    decode_vietnamese_cad_text,
    fold_vietnamese_cad_text,
    strip_mtext_and_extract_font,
)


@pytest.mark.parametrize(
    "phrase",
    [
        "thép góc",
        "Mép boong chính",
        "kèm theo",
        "hầm hàng bù",
        "Sườn thép",
        "THÉP GÓC",
        "MÉP BOONG CHÍNH",
        "LÕM SÀN",
        "Ý NGHĨA KẾT CẤU",
        "10 µm ± 0.5",
        "M6 × 20",
        "A/F = 24",
    ],
)
def test_utf8_vietnamese_and_technical_phrases_remain_uncorrupted(phrase: str) -> None:
    decoded, encoding = decode_vietnamese_cad_text(phrase)
    assert decoded == phrase
    assert encoding == "utf8"


@pytest.mark.parametrize(
    ("raw_text", "font_hint", "doc_encoding", "expected_text", "expected_folded"),
    [
        ("Däc t©m", "", "", "Dọc tâm", "doc tam"),
        ("§N 9", "", "", "ĐN 9", "dn 9"),
        ("®¸y", "", "", "đáy", "day"),
        ("kÕt c©u th©n tµu", "", "", "kết câu thân tàu", "ket cau than tau"),
        ("C©n b»ng mòi", "", "tcvn3", "Cân bằng mũi", "can bang mui"),
        (r"\f.VnArial|b0|i0|c0|p34;Däc t©m\P%%c100", "", "", "Dọc tâm Ø100", "doc tam ø100"),
        ("CA/SC THO/MNG SO/M/S", "vnc.shx", "", "CÁC THÔNG SỐ", "cac thong so"),
        ("BẢN VẼ \u0421\u0410N", "", "", "BẢN VẼ САN", "ban ve can"),
    ],
)
def test_legacy_tcvn3_vnc_mtext_and_cyrillic_decoding_and_single_fold(
    raw_text: str,
    font_hint: str,
    doc_encoding: str,
    expected_text: str,
    expected_folded: str,
) -> None:
    decoded, _ = decode_vietnamese_cad_text(
        raw_text,
        font_hint=font_hint,
        doc_encoding=doc_encoding,
    )
    assert decoded == expected_text
    assert fold_vietnamese_cad_text(raw_text, font_hint=font_hint, doc_encoding=doc_encoding) == expected_folded


def test_mixed_utf8_and_tcvn3_token_decoding_without_corrupting_utf8_words() -> None:
    raw = "Sườn thép Däc t©m kèm theo"
    decoded, encoding = decode_vietnamese_cad_text(raw)
    assert decoded == "Sườn thép Dọc tâm kèm theo"
    assert encoding == "mixed_utf8_tcvn3"


def test_strip_mtext_extracts_font_and_cleans_codes() -> None:
    cleaned, font = strip_mtext_and_extract_font(
        r"{\f.VnArialH|b1|i0;\H2.5;\C1;THÉP \S1^2; GÓC\PCHÍNH}"
    )
    assert font == ".VnArialH"
    assert cleaned == "THÉP 1/2 GÓC CHÍNH"


def test_oversized_text_bypasses_cache_without_error() -> None:
    long_utf8 = " ".join(["thép góc"] * 80)
    assert len(long_utf8) > 512
    decoded, encoding = decode_vietnamese_cad_text(long_utf8)
    assert decoded == long_utf8
    assert encoding == "utf8"
    assert fold_vietnamese_cad_text(long_utf8) == " ".join(["thep goc"] * 80)
