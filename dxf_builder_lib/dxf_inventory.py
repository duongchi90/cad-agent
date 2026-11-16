"""Read-only DXF ModelSpace entity census and $INSUNITS calibration gate."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Tuple

FIVE_TYPE_MECHANICAL_SET = frozenset({"LINE", "CIRCLE", "ARC", "TEXT", "DIMENSION"})
DEFAULT_MAX_EXTENDED_ENTITIES = 50_000

_INSUNITS_NAMES: Dict[int, str] = {
    0: "unitless",
    1: "inches",
    2: "feet",
    3: "miles",
    4: "millimetres",
    5: "centimetres",
    6: "metres",
    7: "kilometres",
    8: "microinches",
    9: "mils",
    10: "yards",
    11: "angstroms",
    12: "nanometres",
    13: "microns",
    14: "decimetres",
}
_INSUNITS_TO_MM: Dict[int, float] = {
    1: 25.4,
    2: 304.8,
    4: 1.0,
    5: 10.0,
    6: 1000.0,
}


@dataclass(frozen=True)
class TextStyleSummary:
    name: str
    font: str
    bigfont: str

    def to_dict(self) -> Dict[str, str]:
        return {"name": self.name, "font": self.font, "bigfont": self.bigfont}


@dataclass(frozen=True)
class ExtendedEntityRecord:
    handle: str
    dxftype: str
    layer: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "handle": self.handle,
            "dxftype": self.dxftype,
            "layer": self.layer,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class DxfInventoryReport:
    dxf_path: str
    source_sha256: str
    dxf_version: str
    insunits: int
    insunits_name: str
    unit_scale_to_mm: float | None
    calibration_required: bool
    unit_status: str
    measurement: int | None
    total_entities: int
    five_type_entity_count: int
    dropped_entity_count: int
    five_type_coverage_ratio: float
    entity_counts_by_type: Dict[str, int]
    dropped_counts_by_type: Dict[str, int]
    layers: Tuple[str, ...]
    text_styles: Tuple[TextStyleSummary, ...]
    extended_entities: Tuple[ExtendedEntityRecord, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dxf_path": self.dxf_path,
            "source_sha256": self.source_sha256,
            "dxf_version": self.dxf_version,
            "insunits": self.insunits,
            "insunits_name": self.insunits_name,
            "unit_scale_to_mm": self.unit_scale_to_mm,
            "calibration_required": self.calibration_required,
            "unit_status": self.unit_status,
            "measurement": self.measurement,
            "total_entities": self.total_entities,
            "five_type_entity_count": self.five_type_entity_count,
            "dropped_entity_count": self.dropped_entity_count,
            "five_type_coverage_ratio": self.five_type_coverage_ratio,
            "entity_counts_by_type": dict(self.entity_counts_by_type),
            "dropped_counts_by_type": dict(self.dropped_counts_by_type),
            "layers": list(self.layers),
            "text_styles": [s.to_dict() for s in self.text_styles],
            "extended_entities": [e.to_dict() for e in self.extended_entities],
        }


def _classify_units(insunits: int) -> Tuple[str, float | None, bool, str]:
    name = _INSUNITS_NAMES.get(insunits, f"unknown({insunits})")
    scale = _INSUNITS_TO_MM.get(insunits)
    if insunits == 0:
        return name, None, True, "UNITLESS_REQUIRES_CALIBRATION"
    if insunits in (4, 5, 6):
        return name, scale, False, "KNOWN_METRIC"
    if insunits in (1, 2):
        return name, scale, False, "KNOWN_IMPERIAL"
    return name, scale, True, "UNSUPPORTED_UNITS"


def _extract_extended_details(entity: Any, dxftype: str) -> Dict[str, Any]:
    if dxftype == "SPLINE":
        ctrl = getattr(entity, "control_points", None)
        fits = getattr(entity, "fit_points", None)
        return {
            "degree": int(getattr(entity.dxf, "degree", 0)),
            "closed": bool(getattr(entity, "closed", False)),
            "rational": bool(getattr(entity, "is_rational", False)),
            "control_point_count": len(ctrl) if ctrl is not None else 0,
            "fit_point_count": len(fits) if fits is not None else 0,
        }
    if dxftype == "LWPOLYLINE":
        pts = list(entity.get_points("xyseb")) if hasattr(entity, "get_points") else []
        return {
            "closed": bool(getattr(entity, "closed", False)),
            "vertex_count": len(pts),
            "has_bulge": any(abs(float(p[4])) > 1e-9 for p in pts),
        }
    if dxftype == "POLYLINE":
        verts = getattr(entity, "vertices", ())
        return {
            "closed": bool(getattr(entity, "is_closed", False)),
            "vertex_count": len(verts),
        }
    if dxftype == "ELLIPSE":
        major = getattr(entity.dxf, "major_axis", None)
        major_len = math.hypot(float(major.x), float(major.y)) if major is not None else 0.0
        return {
            "major_axis_length": round(major_len, 6),
            "ratio": float(getattr(entity.dxf, "ratio", 1.0)),
            "start_param": float(getattr(entity.dxf, "start_param", 0.0)),
            "end_param": float(getattr(entity.dxf, "end_param", 2.0 * math.pi)),
        }
    if dxftype == "MTEXT":
        plain = entity.plain_text() if hasattr(entity, "plain_text") else str(getattr(entity, "text", ""))
        insert = getattr(entity.dxf, "insert", None)
        return {
            "text_length": len(plain),
            "text_preview": plain[:120],
            "attachment_point": int(getattr(entity.dxf, "attachment_point", 1)),
            "insert": [float(insert.x), float(insert.y)] if insert is not None else None,
        }
    if dxftype == "INSERT":
        attribs = list(getattr(entity, "attribs", ()))
        return {
            "block_name": str(getattr(entity.dxf, "name", "")),
            "has_attribs": bool(attribs),
            "attrib_tags": tuple(str(getattr(a.dxf, "tag", "")) for a in attribs),
        }
    return {}


def inspect_dxf_inventory(
    dxf_path: str | Path,
    *,
    max_entities: int = DEFAULT_MAX_EXTENDED_ENTITIES,
    include_extended_entities: bool = False,
) -> DxfInventoryReport:
    """Return a full read-only ModelSpace entity census and $INSUNITS gate status."""
    if isinstance(max_entities, bool) or not isinstance(max_entities, int) or max_entities <= 0:
        raise ValueError("max_entities must be a positive integer")

    try:
        import ezdxf
    except ImportError as exc:
        raise ImportError(
            "Cần cài package 'ezdxf' để dùng DXF Inventory: "
            "pip install ezdxf --break-system-packages"
        ) from exc

    path = Path(dxf_path)
    source_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    doc = ezdxf.readfile(str(path))

    raw_insunits = doc.header.get("$INSUNITS", 0)
    insunits = int(raw_insunits)
    raw_meas = doc.header.get("$MEASUREMENT", None)
    measurement = int(raw_meas) if raw_meas is not None else None
    insunits_name, scale_to_mm, calibration_required, unit_status = _classify_units(insunits)

    counts: Dict[str, int] = {}
    layers_seen: set[str] = set()
    extended_records: list[ExtendedEntityRecord] = []
    total_entities = 0
    five_type_count = 0

    for entity in doc.modelspace():
        total_entities += 1
        dxftype = str(entity.dxftype()).upper()
        counts[dxftype] = counts.get(dxftype, 0) + 1
        layer = str(getattr(entity.dxf, "layer", "0"))
        layers_seen.add(layer)
        if dxftype in FIVE_TYPE_MECHANICAL_SET:
            five_type_count += 1
        elif include_extended_entities:
            if total_entities > max_entities:
                raise ValueError(
                    f"ModelSpace entity count {total_entities} exceeds max_entities={max_entities}"
                )
            extended_records.append(
                ExtendedEntityRecord(
                    handle=str(getattr(entity.dxf, "handle", "")).upper(),
                    dxftype=dxftype,
                    layer=layer,
                    details=_extract_extended_details(entity, dxftype),
                )
            )

    if include_extended_entities and total_entities > max_entities:
        raise ValueError(
            f"ModelSpace entity count {total_entities} exceeds max_entities={max_entities}"
        )

    dropped_counts = {
        k: counts[k] for k in sorted(counts) if k not in FIVE_TYPE_MECHANICAL_SET
    }
    dropped_total = total_entities - five_type_count
    coverage_ratio = (five_type_count / total_entities) if total_entities > 0 else 1.0

    text_styles = tuple(
        TextStyleSummary(
            name=str(style.dxf.name),
            font=str(getattr(style.dxf, "font", "")),
            bigfont=str(getattr(style.dxf, "bigfont", "")),
        )
        for style in sorted(doc.styles, key=lambda s: str(s.dxf.name))
    )

    return DxfInventoryReport(
        dxf_path=str(path),
        source_sha256=source_sha256,
        dxf_version=str(doc.dxfversion),
        insunits=insunits,
        insunits_name=insunits_name,
        unit_scale_to_mm=scale_to_mm,
        calibration_required=calibration_required,
        unit_status=unit_status,
        measurement=measurement,
        total_entities=total_entities,
        five_type_entity_count=five_type_count,
        dropped_entity_count=dropped_total,
        five_type_coverage_ratio=round(coverage_ratio, 6),
        entity_counts_by_type={k: counts[k] for k in sorted(counts)},
        dropped_counts_by_type=dropped_counts,
        layers=tuple(sorted(layers_seen)),
        text_styles=text_styles,
        extended_entities=tuple(extended_records),
    )
