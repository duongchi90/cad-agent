"""Primitive IR Serialization, Deserialization, and Roundtrip Integrity Engine.

Research Reference Engine comparing Strategies A-D for Topic 26:
PRIMITIVE_IR_SERIALIZATION_ROUNDTRIP_INTEGRITY_V1.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import math
import re
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

# Import production types
from primitive_ir_lib.models import (
    ArcGeometry as ProdArcGeometry,
    Calibration as ProdCalibration,
    CircleGeometry as ProdCircleGeometry,
    CrossValidation as ProdCrossValidation,
    LineGeometry as ProdLineGeometry,
    Point2D as ProdPoint2D,
    Primitive as ProdPrimitive,
    PrimitiveIRDocument as ProdPrimitiveIRDocument,
    SourceDocument as ProdSourceDocument,
    TextData as ProdTextData,
    Trace as ProdTrace,
    Validation as ProdValidation,
)
from primitive_ir_lib.validator import validate_document as prod_validate_document
from semantic_ir_lib.io_utils import (
    _primitive_ir_document_from_dict as prod_deserializer,
)


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_VALID_TYPES = {"line", "circle", "arc", "text"}
_VALID_SOURCES = {
    "geometry_opencv",
    "geometry_external_ai",
    "text_tesseract",
    "text_vision",
}
_VALID_ROLES = {
    "dimension_value",
    "title_block_field",
    "drawing_code",
    "general_note",
    "table_cell",
    "unknown",
}
_VALID_VALIDATION_STATUS = {
    "unreviewed",
    "reviewer1_pass",
    "reviewer1_fail",
    "reviewer2_pass",
    "reviewer2_fail",
    "repaired",
}
_VALID_CV_STATUS = {"confirmed", "conflict", "unverified"}
_VALID_CALIBRATION_UNITS = {"mm", "cm", "m"}
_VALID_CALIBRATION_METHODS = {
    "known_dimension_reference",
    "title_block_scale",
    "manual_override",
}
_VALID_CALIBRATION_STATUS = {"verified", "needs_verification"}


def _is_finite_num(val: Any) -> bool:
    return isinstance(val, (int, float)) and not isinstance(val, bool) and math.isfinite(val)


# ==============================================================================
# Canonical JSON Serializer (RFC 8259 strict)
# ==============================================================================

def canonical_json_dumps(data: Any) -> str:
    """Serialize dictionary/list to canonical deterministic JSON string.
    
    Enforces RFC 8259 compliance (no NaN/Infinity) and deterministic key sorting.
    """
    def _check_finite(obj: Any) -> None:
        if isinstance(obj, float):
            if not math.isfinite(obj):
                raise ValueError(f"Non-finite float not allowed in canonical JSON: {obj}")
        elif isinstance(obj, dict):
            for k, v in obj.items():
                if not isinstance(k, str):
                    raise TypeError(f"Dictionary key must be string, got: {type(k)}")
                _check_finite(v)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                _check_finite(item)

    _check_finite(data)
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_sha256(data: Any) -> str:
    """Compute deterministic SHA-256 of canonical JSON payload."""
    serialized = canonical_json_dumps(data)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# ==============================================================================
# Deep Schema Validator (Strategy D Engine)
# ==============================================================================

def deep_validate_document(doc: Dict[str, Any]) -> List[str]:
    """Exhaustive schema validator enforcing primitive_ir.schema.json constraints.
    
    Catches all structural, numeric, enum, and referential errors.
    """
    errors: List[str] = []
    if not isinstance(doc, dict):
        return ["Document must be a JSON object"]

    # 1. Top-level required keys
    for key in ("schema_version", "source_document", "calibration", "primitives"):
        if key not in doc:
            errors.append(f"Missing required document field: '{key}'")

    schema_version = doc.get("schema_version")
    if schema_version != "1.0.0":
        errors.append(f"Invalid schema_version: '{schema_version}', expected '1.0.0'")

    # 2. Source Document
    sd = doc.get("source_document")
    if not isinstance(sd, dict):
        errors.append("source_document must be an object")
    else:
        for req in ("file_name", "page_index", "image_width_px", "image_height_px"):
            if req not in sd:
                errors.append(f"source_document missing required field: '{req}'")
        if "page_index" in sd and (isinstance(sd["page_index"], bool) or not isinstance(sd["page_index"], int) or sd["page_index"] < 0):
            errors.append(f"source_document.page_index must be a non-negative integer")
        for dim in ("image_width_px", "image_height_px"):
            if dim in sd and (isinstance(sd[dim], bool) or not isinstance(sd[dim], int) or sd[dim] < 1):
                errors.append(f"source_document.{dim} must be an integer >= 1")
        if "sha256" in sd and sd["sha256"] is not None:
            if not isinstance(sd["sha256"], str) or not _SHA256_RE.fullmatch(sd["sha256"]):
                errors.append("source_document.sha256 must be a 64-char lowercase hex string")

    # 3. Calibration
    cal = doc.get("calibration")
    if not isinstance(cal, dict):
        errors.append("calibration must be an object")
    else:
        for req in ("unit", "pixel_to_unit_scale", "origin_px", "method"):
            if req not in cal:
                errors.append(f"calibration missing required field: '{req}'")
        unit = cal.get("unit")
        if unit not in _VALID_CALIBRATION_UNITS:
            errors.append(f"calibration.unit '{unit}' not in {_VALID_CALIBRATION_UNITS}")
        scale = cal.get("pixel_to_unit_scale")
        if not _is_finite_num(scale) or scale <= 0.0:
            errors.append(f"calibration.pixel_to_unit_scale must be a finite positive number, got: {scale}")
        origin = cal.get("origin_px")
        if not isinstance(origin, (list, tuple)) or len(origin) != 2 or not all(_is_finite_num(x) for x in origin):
            errors.append(f"calibration.origin_px must be a 2-element array of finite numbers, got: {origin}")
        method = cal.get("method")
        if method not in _VALID_CALIBRATION_METHODS:
            errors.append(f"calibration.method '{method}' not in {_VALID_CALIBRATION_METHODS}")
        status = cal.get("status", "verified")
        if status not in _VALID_CALIBRATION_STATUS:
            errors.append(f"calibration.status '{status}' not in {_VALID_CALIBRATION_STATUS}")
        if "source_sha256" in cal and cal["source_sha256"] is not None:
            if not isinstance(cal["source_sha256"], str) or not _SHA256_RE.fullmatch(cal["source_sha256"]):
                errors.append("calibration.source_sha256 must be a 64-char lowercase hex string")

    # 4. Primitives
    primitives = doc.get("primitives", [])
    if not isinstance(primitives, list):
        errors.append("primitives must be an array")
        return errors

    primitive_ids: set[str] = set()
    for i, prim in enumerate(primitives):
        prefix = f"primitives[{i}] (id={prim.get('id') if isinstance(prim, dict) else None})"
        if not isinstance(prim, dict):
            errors.append(f"{prefix}: primitive must be an object")
            continue

        for req in ("id", "type", "source", "confidence", "layer", "handle", "trace", "validation"):
            if req not in prim:
                errors.append(f"{prefix}: missing required field '{req}'")

        pid = prim.get("id")
        if not isinstance(pid, str) or not pid:
            errors.append(f"{prefix}: id must be a non-empty string")
        elif pid in primitive_ids:
            errors.append(f"{prefix}: duplicate primitive id '{pid}'")
        else:
            primitive_ids.add(pid)

        ptype = prim.get("type")
        if ptype not in _VALID_TYPES:
            errors.append(f"{prefix}: invalid type '{ptype}'")

        source = prim.get("source")
        if source not in _VALID_SOURCES:
            errors.append(f"{prefix}: invalid source '{source}'")

        conf = prim.get("confidence")
        if not _is_finite_num(conf) or not (0.0 <= conf <= 1.0):
            errors.append(f"{prefix}: confidence must be a finite number in [0.0, 1.0], got: {conf}")

        # Trace
        trace = prim.get("trace")
        if not isinstance(trace, dict):
            errors.append(f"{prefix}: trace must be an object")
        else:
            bbox = trace.get("bbox_px")
            if not isinstance(bbox, (list, tuple)) or len(bbox) != 4 or not all(_is_finite_num(x) for x in bbox):
                errors.append(f"{prefix}: trace.bbox_px must be 4 finite numbers, got: {bbox}")
            if source == "geometry_external_ai":
                for shafield in ("verification_request_sha256", "verification_result_sha256"):
                    val = trace.get(shafield)
                    if not isinstance(val, str) or not _SHA256_RE.fullmatch(val):
                        errors.append(f"{prefix}: external AI geometry requires valid '{shafield}'")

        # Validation
        val = prim.get("validation")
        if not isinstance(val, dict):
            errors.append(f"{prefix}: validation must be an object")
        else:
            vstatus = val.get("status")
            if vstatus not in _VALID_VALIDATION_STATUS:
                errors.append(f"{prefix}: validation.status '{vstatus}' invalid")

        # Geometry vs TextData
        if ptype == "text":
            if "text_data" not in prim or not isinstance(prim["text_data"], dict):
                errors.append(f"{prefix}: type='text' requires text_data object")
            else:
                td = prim["text_data"]
                for req in ("content", "position", "rotation_deg", "height"):
                    if req not in td:
                        errors.append(f"{prefix}: text_data missing required '{req}'")
                if "content" in td and not isinstance(td["content"], str):
                    errors.append(f"{prefix}: text_data.content must be string")
                pos = td.get("position")
                if not isinstance(pos, dict) or "x" not in pos or "y" not in pos or not _is_finite_num(pos["x"]) or not _is_finite_num(pos["y"]):
                    errors.append(f"{prefix}: text_data.position must be an object with finite x, y")
                rot = td.get("rotation_deg")
                if not _is_finite_num(rot):
                    errors.append(f"{prefix}: text_data.rotation_deg must be finite number")
                h = td.get("height")
                if not _is_finite_num(h) or h <= 0.0:
                    errors.append(f"{prefix}: text_data.height must be positive finite number, got: {h}")
                pv = td.get("parsed_value")
                if pv is not None and not _is_finite_num(pv):
                    errors.append(f"{prefix}: text_data.parsed_value must be null or finite number")
                srole = td.get("semantic_role", "unknown")
                if srole not in _VALID_ROLES:
                    errors.append(f"{prefix}: text_data.semantic_role '{srole}' invalid")
        elif ptype in ("line", "circle", "arc"):
            if "geometry" not in prim or not isinstance(prim["geometry"], dict):
                errors.append(f"{prefix}: type='{ptype}' requires geometry object")
            else:
                geom = prim["geometry"]
                if ptype == "line":
                    for pt_key in ("start", "end"):
                        if pt_key not in geom or not isinstance(geom[pt_key], dict):
                            errors.append(f"{prefix}: line geometry missing '{pt_key}'")
                        else:
                            pt = geom[pt_key]
                            if "x" not in pt or "y" not in pt or not _is_finite_num(pt["x"]) or not _is_finite_num(pt["y"]):
                                errors.append(f"{prefix}: line geometry '{pt_key}' must have finite x, y")
                elif ptype == "circle":
                    if "center" not in geom or not isinstance(geom["center"], dict):
                        errors.append(f"{prefix}: circle geometry missing 'center'")
                    else:
                        c = geom["center"]
                        if "x" not in c or "y" not in c or not _is_finite_num(c["x"]) or not _is_finite_num(c["y"]):
                            errors.append(f"{prefix}: circle center must have finite x, y")
                    r = geom.get("radius")
                    if not _is_finite_num(r) or r <= 0.0:
                        errors.append(f"{prefix}: circle radius must be positive finite number, got: {r}")
                elif ptype == "arc":
                    if "center" not in geom or not isinstance(geom["center"], dict):
                        errors.append(f"{prefix}: arc geometry missing 'center'")
                    else:
                        c = geom["center"]
                        if "x" not in c or "y" not in c or not _is_finite_num(c["x"]) or not _is_finite_num(c["y"]):
                            errors.append(f"{prefix}: arc center must have finite x, y")
                    r = geom.get("radius")
                    if not _is_finite_num(r) or r <= 0.0:
                        errors.append(f"{prefix}: arc radius must be positive finite number, got: {r}")
                    for ang in ("start_angle_deg", "end_angle_deg"):
                        if ang not in geom or not _is_finite_num(geom[ang]):
                            errors.append(f"{prefix}: arc geometry '{ang}' must be finite number")

    # 5. Cross Validations
    cvs = doc.get("cross_validations", [])
    if not isinstance(cvs, list):
        errors.append("cross_validations must be an array")
    else:
        for i, cv in enumerate(cvs):
            prefix = f"cross_validations[{i}] (id={cv.get('id') if isinstance(cv, dict) else None})"
            if not isinstance(cv, dict):
                errors.append(f"{prefix}: cross_validation must be an object")
                continue
            for req in ("id", "text_primitive_id", "geometry_primitive_id", "status"):
                if req not in cv:
                    errors.append(f"{prefix}: missing required field '{req}'")
            status = cv.get("status")
            if status not in _VALID_CV_STATUS:
                errors.append(f"{prefix}: status '{status}' invalid")
            t_id = cv.get("text_primitive_id")
            if t_id and t_id not in primitive_ids:
                errors.append(f"{prefix}: text_primitive_id '{t_id}' not found in primitives")
            g_id = cv.get("geometry_primitive_id")
            if g_id and g_id not in primitive_ids:
                errors.append(f"{prefix}: geometry_primitive_id '{g_id}' not found in primitives")
            for num_field in ("text_value", "geometry_measured_length", "delta_percent", "match_threshold_percent"):
                val = cv.get(num_field)
                if val is not None and not _is_finite_num(val):
                    errors.append(f"{prefix}: '{num_field}' must be finite number, got: {val}")

    return errors


# ==============================================================================
# Extended Lossless Deserializer (Strategy D Engine)
# ==============================================================================

def deserialize_primitive_ir_document_lossless(data: Dict[str, Any]) -> ProdPrimitiveIRDocument:
    """Deserialize dictionary into ProdPrimitiveIRDocument preserving ALL fields.
    
    Preserves:
    - verification_request_sha256 & verification_result_sha256 on Trace
    - 'needs_verification' on Calibration without crashing
    - ArcGeometry center, radius, angles
    - Validation notes even if empty string
    - CrossValidation exact fields
    """
    sd_data = data["source_document"]
    source_document = ProdSourceDocument(
        file_name=sd_data["file_name"],
        page_index=sd_data["page_index"],
        image_width_px=sd_data["image_width_px"],
        image_height_px=sd_data["image_height_px"],
        sha256=sd_data.get("sha256"),
    )

    cal_data = data["calibration"]
    calibration = ProdCalibration(
        unit=cal_data["unit"],
        pixel_to_unit_scale=cal_data["pixel_to_unit_scale"],
        origin_px=tuple(cal_data["origin_px"]),
        method=cal_data["method"],
        reference_note=cal_data.get("reference_note"),
        status=cal_data.get("status", "verified"),
        source_sha256=cal_data.get("source_sha256"),
    )

    primitives: List[ProdPrimitive] = []
    for p_data in data.get("primitives", []):
        ptype = p_data["type"]
        
        # Trace
        tr_data = p_data["trace"]
        trace = ProdTrace(
            bbox_px=tuple(tr_data["bbox_px"]),
            extraction_tool=tr_data.get("extraction_tool"),
            extracted_at=tr_data.get("extracted_at"),
            verification_request_sha256=tr_data.get("verification_request_sha256"),
            verification_result_sha256=tr_data.get("verification_result_sha256"),
        )

        # Validation
        val_data = p_data.get("validation", {})
        validation = ProdValidation(
            status=val_data.get("status", "unreviewed"),
            notes=val_data.get("notes"),
        )

        # Geometry
        geom = None
        text_data = None
        if ptype == "line":
            g = p_data["geometry"]
            geom = ProdLineGeometry(
                start=ProdPoint2D(x=g["start"]["x"], y=g["start"]["y"]),
                end=ProdPoint2D(x=g["end"]["x"], y=g["end"]["y"]),
            )
        elif ptype == "circle":
            g = p_data["geometry"]
            geom = ProdCircleGeometry(
                center=ProdPoint2D(x=g["center"]["x"], y=g["center"]["y"]),
                radius=g["radius"],
            )
        elif ptype == "arc":
            g = p_data["geometry"]
            geom = ProdArcGeometry(
                center=ProdPoint2D(x=g["center"]["x"], y=g["center"]["y"]),
                radius=g["radius"],
                start_angle_deg=g["start_angle_deg"],
                end_angle_deg=g["end_angle_deg"],
            )
        elif ptype == "text":
            td = p_data["text_data"]
            text_data = ProdTextData(
                content=td["content"],
                position=ProdPoint2D(x=td["position"]["x"], y=td["position"]["y"]),
                rotation_deg=td["rotation_deg"],
                height=td["height"],
                parsed_value=td.get("parsed_value"),
                semantic_role=td.get("semantic_role", "unknown"),
            )

        prim = ProdPrimitive(
            id=p_data["id"],
            type=ptype,
            source=p_data["source"],
            confidence=p_data["confidence"],
            trace=trace,
            layer=p_data.get("layer", "UNCLASSIFIED"),
            handle=p_data.get("handle"),
            geometry=geom,
            text_data=text_data,
            validation=validation,
        )
        primitives.append(prim)

    cross_validations: List[ProdCrossValidation] = []
    for cv_data in data.get("cross_validations", []):
        cv = ProdCrossValidation(
            id=cv_data["id"],
            text_primitive_id=cv_data["text_primitive_id"],
            geometry_primitive_id=cv_data["geometry_primitive_id"],
            status=cv_data["status"],
            text_value=cv_data.get("text_value"),
            geometry_measured_length=cv_data.get("geometry_measured_length"),
            delta_percent=cv_data.get("delta_percent"),
            match_threshold_percent=cv_data.get("match_threshold_percent", 3.0),
        )
        cross_validations.append(cv)

    return ProdPrimitiveIRDocument(
        source_document=source_document,
        calibration=calibration,
        primitives=primitives,
        cross_validations=cross_validations,
        schema_version=data.get("schema_version", "1.0.0"),
    )


# ==============================================================================
# Extended Assembly Builder (Supports Arcs)
# ==============================================================================

@dataclasses.dataclass
class RawArc:
    """Raw extracted arc in pixel coordinates."""
    id: str
    center_px: Tuple[float, float]
    radius_px: float
    start_angle_deg: float
    end_angle_deg: float
    confidence: float
    bbox_px: Tuple[float, float, float, float]
    source: str = "geometry_opencv"


def arc_to_primitive(raw: RawArc, calibration: ProdCalibration, tool: str = "taubin-arc-fit-v1") -> ProdPrimitive:
    """Convert raw pixel Arc into CAD Primitive with ArcGeometry."""
    center = calibration.pixel_to_cad(*raw.center_px)
    radius = raw.radius_px * calibration.pixel_to_unit_scale
    from primitive_ir_lib.models import now_iso
    return ProdPrimitive(
        id=raw.id,
        type="arc",
        source="geometry_opencv",
        confidence=raw.confidence,
        geometry=ProdArcGeometry(
            center=center,
            radius=radius,
            start_angle_deg=raw.start_angle_deg,
            end_angle_deg=raw.end_angle_deg,
        ),
        trace=ProdTrace(bbox_px=raw.bbox_px, extraction_tool=tool, extracted_at=now_iso()),
    )


# ==============================================================================
# Strategy Comparators
# ==============================================================================

class StrategyA_ProductionBaseline:
    """Current Production baseline using semantic_ir_lib.io_utils and validator.py."""
    
    @staticmethod
    def deserialize(doc_dict: Dict[str, Any]) -> ProdPrimitiveIRDocument:
        return prod_deserializer(doc_dict)

    @staticmethod
    def validate(doc_dict: Dict[str, Any]) -> List[str]:
        return prod_validate_document(doc_dict)

    @staticmethod
    def roundtrip(doc: ProdPrimitiveIRDocument) -> ProdPrimitiveIRDocument:
        d = doc.to_dict()
        return prod_deserializer(d)


class StrategyB_NaiveShallow:
    """Naive shallow unpacker without deep validation or arc geometry dispatch."""
    
    @staticmethod
    def deserialize(doc_dict: Dict[str, Any]) -> ProdPrimitiveIRDocument:
        # Shallow unpacks primitives but does not map arc geometry or trace sha256
        prims = []
        for p in doc_dict.get("primitives", []):
            ptype = p["type"]
            geom = None
            if ptype == "line":
                geom = ProdLineGeometry(
                    start=ProdPoint2D(p["geometry"]["start"]["x"], p["geometry"]["start"]["y"]),
                    end=ProdPoint2D(p["geometry"]["end"]["x"], p["geometry"]["end"]["y"]),
                )
            elif ptype == "circle":
                geom = ProdCircleGeometry(
                    center=ProdPoint2D(p["geometry"]["center"]["x"], p["geometry"]["center"]["y"]),
                    radius=p["geometry"]["radius"],
                )
            tr = ProdTrace(bbox_px=tuple(p["trace"]["bbox_px"]))
            prims.append(ProdPrimitive(
                id=p["id"], type=ptype, source=p["source"], confidence=p["confidence"],
                trace=tr, geometry=geom
            ))
        cal = ProdCalibration(
            unit=doc_dict["calibration"]["unit"],
            pixel_to_unit_scale=doc_dict["calibration"]["pixel_to_unit_scale"],
            origin_px=tuple(doc_dict["calibration"]["origin_px"]),
            method=doc_dict["calibration"]["method"],
        )
        sd = ProdSourceDocument(
            file_name=doc_dict["source_document"]["file_name"],
            page_index=doc_dict["source_document"]["page_index"],
            image_width_px=doc_dict["source_document"]["image_width_px"],
            image_height_px=doc_dict["source_document"]["image_height_px"],
        )
        return ProdPrimitiveIRDocument(source_document=sd, calibration=cal, primitives=prims)

    @staticmethod
    def validate(doc_dict: Dict[str, Any]) -> List[str]:
        # Minimal top-level check only
        errors = []
        if "primitives" not in doc_dict:
            errors.append("Missing primitives")
        return errors


class StrategyC_StrictSchemaDeserializer:
    """Strict schema deserializer preserving trace hashes and calibration status."""
    
    @staticmethod
    def deserialize(doc_dict: Dict[str, Any]) -> ProdPrimitiveIRDocument:
        # Preserves trace sha256 and calibration status, handles arc
        return deserialize_primitive_ir_document_lossless(doc_dict)

    @staticmethod
    def validate(doc_dict: Dict[str, Any]) -> List[str]:
        # Uses production validator (still has validator holes for geometry numbers)
        return prod_validate_document(doc_dict)


class StrategyD_LosslessCanonicalRoundtripEngine:
    """Complete lossless roundtrip engine with deep validation and canonical RFC-8259 hashing."""
    
    @staticmethod
    def deserialize(doc_dict: Dict[str, Any]) -> ProdPrimitiveIRDocument:
        return deserialize_primitive_ir_document_lossless(doc_dict)

    @staticmethod
    def validate(doc_dict: Dict[str, Any]) -> List[str]:
        return deep_validate_document(doc_dict)

    @staticmethod
    def serialize_canonical(doc: ProdPrimitiveIRDocument) -> str:
        d = doc.to_dict()
        errors = deep_validate_document(d)
        if errors:
            raise ValueError(f"Document violates schema: {errors}")
        return canonical_json_dumps(d)

    @staticmethod
    def compute_sha256(doc: ProdPrimitiveIRDocument) -> str:
        return canonical_sha256(doc.to_dict())

    @staticmethod
    def roundtrip(doc: ProdPrimitiveIRDocument) -> Tuple[ProdPrimitiveIRDocument, bool]:
        """Roundtrip document to dict and back, verifying byte and semantic equality."""
        d1 = doc.to_dict()
        err1 = deep_validate_document(d1)
        if err1:
            return doc, False
        reloaded = deserialize_primitive_ir_document_lossless(d1)
        d2 = reloaded.to_dict()
        err2 = deep_validate_document(d2)
        if err2:
            return reloaded, False
        equal = (canonical_json_dumps(d1) == canonical_json_dumps(d2))
        return reloaded, equal
