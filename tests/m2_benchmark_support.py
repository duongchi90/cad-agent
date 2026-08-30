from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cad_agent.live import load_build_evidence, write_build_evidence
from cad_agent.manifest import sha256_file
from dxf_builder_lib.builder import BuildResult, build_dxf
from dxf_builder_lib.reviewer import ReviewResult, review_dxf
from primitive_ir_lib.models import (
    Calibration,
    CircleGeometry,
    CrossValidation,
    LineGeometry,
    Point2D,
    Primitive,
    PrimitiveIRDocument,
    SourceDocument,
    Trace,
    TextData,
)
from semantic_ir_lib.models import PrimitiveIRRef, SemanticIRDocument, SemanticPart


_FIXED_GUID = "{00000000-0000-0000-0000-000000000000}"
_FIXED_EZDXF_BANNER = "1.4.4 @ 1970-01-01T00:00:00+00:00"
_FIXED_DXF_HEADER_DATE = "2451544.5"
_GUID_VALUE = re.compile(rb"\{[0-9A-Fa-f-]{36}\}")
_EZDXF_BANNER = re.compile(rb"1\.4\.4 @ [^\r\n]+")
_DXF_HEADER_DATE = re.compile(
    rb"(  9\r\n\$(?:TDCREATE|TDUCREATE|TDUPDATE|TDUUPDATE)\r\n 40\r\n)[^\r\n]+"
)
_DXF_CLASSES_SECTION = re.compile(
    rb"(  0\r\nSECTION\r\n  2\r\nCLASSES\r\n)(.*?)(  0\r\nENDSEC\r\n)",
    re.DOTALL,
)
_DXF_CLASS_RECORD = b"  0\r\nCLASS\r\n"
_DXF_ENTITIES_SECTION = re.compile(
    rb"  0\r\nSECTION\r\n  2\r\nENTITIES\r\n(.*?)(  0\r\nENDSEC\r\n)",
    re.DOTALL,
)


@dataclass(frozen=True)
class M2Fixture:
    input_path: Path
    staged_dxf: Path
    build: BuildResult
    headless: ReviewResult
    input_sha256: str
    staged_dxf_sha256: str
    build_evidence: Path
    source_bytes: bytes
    source_json: dict[str, Any]


def _primitive_document(root: Path) -> tuple[PrimitiveIRDocument, bytes, dict[str, Any]]:
    calibration = Calibration(
        unit="mm",
        pixel_to_unit_scale=1.0,
        origin_px=(0, 0),
        method="manual_override",
        status="verified",
        reference_note="verified mm calibration",
    )
    line = Primitive(
        id="line-001",
        type="line",
        source="geometry_opencv",
        confidence=1.0,
        trace=Trace(bbox_px=(0, 0, 100, 20), extraction_tool="fixture"),
        geometry=LineGeometry(start=Point2D(0, 0), end=Point2D(100, 0)),
    )
    circle = Primitive(
        id="circle-001",
        type="circle",
        source="geometry_opencv",
        confidence=1.0,
        trace=Trace(bbox_px=(10, 10, 30, 30), extraction_tool="fixture"),
        geometry=CircleGeometry(center=Point2D(40, 40), radius=12.5),
    )
    text = Primitive(
        id="text-001",
        type="text",
        source="text_tesseract",
        confidence=1.0,
        trace=Trace(bbox_px=(5, 60, 50, 80), extraction_tool="fixture"),
        text_data=TextData(
            content="M2 FIXTURE",
            position=Point2D(5, 15),
            rotation_deg=0.0,
            height=2.5,
        ),
    )
    document = PrimitiveIRDocument(
        source_document=SourceDocument(
            file_name="m2_source.json",
            page_index=0,
            image_width_px=100,
            image_height_px=100,
        ),
        calibration=calibration,
        primitives=[line, circle, text],
        cross_validations=[
            CrossValidation(
                id="cv-001",
                text_primitive_id="text-001",
                geometry_primitive_id="line-001",
                status="confirmed",
                text_value=100.0,
                geometry_measured_length=100.0,
                delta_percent=0.0,
            )
        ],
    )
    source_json = document.to_dict()
    source_bytes = json.dumps(
        source_json,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return document, source_bytes, source_json


def _semantic_document() -> SemanticIRDocument:
    return SemanticIRDocument(
        primitive_ir_ref=PrimitiveIRRef(file_name="m2_source.json", primitive_count=3),
        parts=[
            SemanticPart(
                id="part-001",
                part_type="thanh_ngang",
                primitive_ids=["line-001"],
                confidence=1.0,
            )
        ],
        constraints=[],
    )


def _canonicalize_dxf_class_section(data: bytes) -> bytes:
    match = _DXF_CLASSES_SECTION.search(data)
    if match is None:
        return data

    body = match.group(2)
    records = body.split(_DXF_CLASS_RECORD)
    if len(records) <= 2 or records[0]:
        return data

    ordered_records = b"".join(
        _DXF_CLASS_RECORD + record for record in sorted(records[1:])
    )
    replacement = match.group(1) + ordered_records + match.group(3)
    return data[: match.start()] + replacement + data[match.end() :]


def _normalize_staged_dxf_bytes(data: bytes) -> bytes:
    normalized = _GUID_VALUE.sub(_FIXED_GUID.encode("ascii"), data)
    normalized = _EZDXF_BANNER.sub(_FIXED_EZDXF_BANNER.encode("ascii"), normalized)
    normalized = _DXF_HEADER_DATE.sub(
        rb"\g<1>" + _FIXED_DXF_HEADER_DATE.encode("ascii"), normalized
    )
    return _canonicalize_dxf_class_section(normalized)


def _assert_m2_fixture_class_order_is_semantically_safe(data: bytes) -> None:
    upper = data.upper()
    if b"ACAD_PROXY_ENTITY" in upper or b"ACAD_PROXY_OBJECT" in upper:
        raise ValueError("M2 fixture cannot canonicalize DXF class order with proxy records")

    entities = _DXF_ENTITIES_SECTION.search(data)
    if entities is not None and b"\r\n 91\r\n" in entities.group(1):
        raise ValueError(
            "M2 fixture cannot canonicalize DXF class order with entity class-index references"
        )


def headless_metrics(fixture: M2Fixture) -> dict[str, object]:
    review = fixture.headless
    return {
        "primitive_checked_count": review.checked_count,
        "primitive_mismatch_count": len(review.mismatches),
        "component_checked_count": review.component_checked_count,
        "component_mismatch_count": len(review.component_mismatches),
        "dimension_checked_count": review.dimension_checked_count,
        "dimension_mismatch_count": len(review.dimension_mismatches),
        "status": "PASS" if review.passed else "FAIL",
    }


def build_m2_fixture(root: Path) -> M2Fixture:
    root.mkdir(parents=True, exist_ok=True)
    document, source_bytes, source_json = _primitive_document(root)
    input_path = root / "m2_source.json"
    input_path.write_bytes(source_bytes)
    semantic_doc = _semantic_document()
    staged_dxf = root / "staged.dxf"
    build = build_dxf(
        document,
        str(staged_dxf),
        semantic_doc=semantic_doc,
        build_components=True,
        build_dimensions=True,
    )
    headless_before_normalization = review_dxf(build)
    build_evidence = root / "build-evidence.json"
    normalized_bytes = _normalize_staged_dxf_bytes(staged_dxf.read_bytes())
    _assert_m2_fixture_class_order_is_semantically_safe(normalized_bytes)
    staged_dxf.write_bytes(normalized_bytes)
    headless = review_dxf(build)
    if headless != headless_before_normalization:
        raise ValueError("M2 fixture normalization changed headless semantic review")
    write_build_evidence(build_evidence, build)
    loaded = load_build_evidence(build_evidence, staged_dxf)
    if loaded != build:
        build = loaded
    return M2Fixture(
        input_path=input_path,
        staged_dxf=staged_dxf,
        build=build,
        headless=headless,
        input_sha256=sha256_file(input_path),
        staged_dxf_sha256=sha256_file(staged_dxf),
        build_evidence=build_evidence,
        source_bytes=source_bytes,
        source_json=source_json,
    )
