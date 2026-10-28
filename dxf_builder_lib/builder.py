"""
builder.py — DXF Builder (Phase 3, mục 2 tài liệu kiến trúc): "build 1 lần"
bằng `ezdxf`, không vẽ từng entity qua MCP/AutoCAD. Đây là module code THẬT
đầu tiên của Phase 3, đứng ngay sau Constraint Solving trong sơ đồ pipeline.

INPUT:
  - `PrimitiveIRDocument` (Phase 1) — nguồn hình học/text chính, đã build
    xong bằng geometry_extraction.py/text_extraction.py.
  - (optional) `solved_primitives` (Phase 2, `constraint_solving.solve_constraints()`)
    — nếu có, GHI ĐÈ toạ độ line "đã làm sạch" thay vì toạ độ đo thô, đúng
    thứ tự pipeline mục 2 (Constraint Solving -> DXF Builder).
  - (optional) `SemanticIRDocument` (Phase 2) — chỉ dùng để suy layer theo
    `part_type` (thanh_ngang/thanh_doc/...), KHÔNG dùng geometry của nó
    (Semantic IR vốn không sao chép geometry, xem models.py mục 11.1).

OUTPUT: file .dxf thật trên đĩa + `BuildResult` ghi lại CHÍNH XÁC những gì
đã ghi vào file cho mỗi primitive (`written_geometry_by_primitive_id`) và
`handle` CAD thật do ezdxf cấp — 2 giá trị này là "nguồn sự thật" để
`reviewer.py` (Headless Reviewer #1) đối chiếu ngược lại sau khi đọc lại
file, và để Repair #2 sau này target đúng entity qua handle (đã xác nhận
handle giữ nguyên 100% qua `drawing_open` AutoCAD LT thật — mục 9.4 tài
liệu kiến trúc).

`Primitive.handle` (field có sẵn từ Phase 1, `None` cho tới khi build)
được GHI ĐÈ trực tiếp lên chính object `primitive_doc.primitives[i]` sau
khi build xong — đúng ghi chú trong `primitive_ir.schema.json`: field này
chuyển từ null sang giá trị thật sau bước ezdxf build, dùng chung 1 schema
xuyên suốt thay vì có bản thứ 2 cho "sau khi build".

Optional dependency: `ezdxf` (`pip install ezdxf --break-system-packages`)
— cùng chiến lược lazy-import/graceful-skip đã dùng cho vision_client.py và
constraint_solving.py.
"""

from __future__ import annotations

import logging
import math
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from primitive_ir_lib.models import Primitive, PrimitiveIRDocument

# part_type (semantic_ir_lib) -> (tên layer DXF, mã màu ACI)
# Màu khác nhau theo part_type để Reviewer #2 (visual, screenshot AutoCAD)
# dễ phân biệt bằng mắt các nhóm linh kiện khi zoom — không ảnh hưởng gì
# tới Reviewer #1 (headless, chỉ so số).
_LAYER_BY_PART_TYPE: Dict[str, Tuple[str, int]] = {
    # single-primitive parts (pattern_recognition.py)
    "thanh_ngang": ("THANH_NGANG", 1),       # đỏ
    "thanh_doc": ("THANH_DOC", 5),           # xanh dương
    "thanh_xien": ("THANH_XIEN", 3),         # xanh lá
    "lo_bat_vit": ("LO_BAT_VIT", 2),         # vàng
    "duong_vien_tron": ("DUONG_VIEN_TRON", 6),  # tím/magenta
    # compound parts (pattern_compound.py) — Phase 2 nâng cao
    "khung_chu_nhat": ("KHUNG_CHU_NHAT", 4),     # cyan (xanh nước)
    "gia_do": ("GIA_DO", 30),                    # orange (cam)
    "ban_le": ("BAN_LE", 186),                   # light magenta (hồng nhạt)
    "diem_noi": ("DIEM_NOI", 9),                 # light gray (xám nhạt)
    "mechanical_shaft_step": ("MECHANICAL_SHAFT_STEP", 1),
    "mechanical_hole_feature": ("MECHANICAL_HOLE_FEATURE", 2),
    "unclassified": ("UNCLASSIFIED", 8),     # xám
}
_DEFAULT_LAYER: Tuple[str, int] = ("UNCLASSIFIED", 8)
_TEXT_LAYER: Tuple[str, int] = ("TEXT", 7)  # trắng/đen
_LAYER_BY_PDF_SOURCE_CLASSIFICATION: Dict[str, Tuple[str, int]] = {
    "HIDDEN": ("HIDDEN", 8),
    "CENTERLINE": ("CENTERLINE", 8),
}
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class NativeLinearDimensionSpec:
    id: str
    geometry_primitive_id: str
    approved_value_mm: float | None
    source_ref: str


@dataclass(frozen=True)
class DimensionLineExpectation:
    validation_id: str
    dimension_handle: str
    block_name: str
    line_endpoints: tuple[tuple[tuple[float, float, float], tuple[float, float, float]], ...]


@dataclass
class BuildResult:
    output_path: str
    handle_by_primitive_id: Dict[str, str] = field(default_factory=dict)
    layer_by_primitive_id: Dict[str, str] = field(default_factory=dict)
    # đúng những gì ĐÃ GHI vào file (đã áp solved override nếu có) — nguồn
    # sự thật cho reviewer.py, KHÔNG phải toạ độ thô trong primitive_doc
    written_geometry_by_primitive_id: Dict[str, dict] = field(default_factory=dict)
    skipped_primitive_ids: List[str] = field(default_factory=list)
    entity_count: int = 0
    dimension_count: int = 0
    dimension_handle_by_cross_validation_id: Dict[str, str] = field(default_factory=dict)
    written_dimension_by_cross_validation_id: Dict[str, dict] = field(default_factory=dict)
    # --- Semantic API (mục 12.4, semantic_components.py) — chỉ điền khi gọi
    # build_dxf(..., build_components=True) VÀ có semantic_doc. Đứng SONG
    # SONG với hình học thô ở trên (layer COMP_*, KHÔNG thay thế) — xem
    # docstring đầu semantic_components.py. Hỗ trợ cả single-primitive parts
    # và compound parts (mục 11.4 nâng cao).
    component_handle_by_part_id: Dict[str, str] = field(default_factory=dict)
    component_type_by_part_id: Dict[str, str] = field(default_factory=dict)
    skipped_part_ids: List[str] = field(default_factory=list)
    skipped_part_reasons: Dict[str, str] = field(default_factory=dict)
    component_count: int = 0
    # đúng những gì ĐÃ GHI vào entity INSERT (block name, layer, insert
    # point, x/y/z scale, rotation, ATTRIB) — đọc lại TRỰC TIẾP từ chính
    # entity vừa tạo (đối tượng blockref trong doc, TRƯỚC saveas) thay vì
    # từ ComponentInsertResult, để "nguồn sự thật" luôn khớp bất kể hàm
    # insert nào trong semantic_components.py sinh ra nó — cùng nguyên tắc
    # written_geometry_by_primitive_id ở trên, dùng cho reviewer.py đối
    # chiếu ngược sau khi đọc lại file (round-trip INSERT).
    written_component_by_part_id: Dict[str, dict] = field(default_factory=dict)
    # Source-declared endpoint connections, independent of per-entity write truth.
    # Empty preserves legacy roundtrip-only review; no connections are inferred.
    contour_join_by_id: Dict[str, dict] = field(default_factory=dict)
    # Optional, ephemeral evidence; intentionally omitted from persisted build evidence.
    dimension_line_expectations: Optional[tuple[DimensionLineExpectation, ...]] = None


_MAX_DIMENSION_LINE_EXPECTATIONS = 256
_MAX_LINES_PER_DIMENSION_EXPECTATION = 64


def validate_contour_joins(joins: object) -> None:
    """Validate the closed, additive source obligation shape before use."""
    if type(joins) is not dict:
        raise ValueError("Contour joins must be a dictionary.")
    for join_id, join in joins.items():
        if type(join_id) is not str or not join_id.strip():
            raise ValueError("Contour join ID must be a nonempty string.")
        if type(join) is not dict or set(join) != {"first", "second"}:
            raise ValueError(f"{join_id}: invalid contour join sides.")
        for side in join.values():
            if type(side) is not dict or set(side) != {"primitive_id", "endpoint"}:
                raise ValueError(f"{join_id}: invalid contour endpoint reference.")
            if type(side["primitive_id"]) is not str or not side["primitive_id"].strip():
                raise ValueError(f"{join_id}: missing contour primitive ID.")
            if type(side["endpoint"]) is not str or side["endpoint"] not in {"start", "end"}:
                raise ValueError(f"{join_id}: invalid contour endpoint selector.")
        if join["first"]["primitive_id"] == join["second"]["primitive_id"]:
            raise ValueError(f"{join_id}: contour joins require two distinct primitives.")


def _part_type_by_primitive_id(semantic_doc) -> Dict[str, str]:
    if semantic_doc is None:
        return {}
    mapping: Dict[str, str] = {}
    for part in semantic_doc.parts:
        for pid in part.primitive_ids:
            mapping[pid] = part.part_type
    return mapping


def _layer_for_primitive(prim: Primitive, part_type_by_id: Dict[str, str]) -> Tuple[str, int]:
    if prim.type == "text":
        return _TEXT_LAYER
    part_type = part_type_by_id.get(prim.id)
    if part_type is not None:
        effective = _LAYER_BY_PART_TYPE.get(part_type, _DEFAULT_LAYER)
        if prim.type == "line" and prim.layer in _LAYER_BY_PDF_SOURCE_CLASSIFICATION:
            _LOGGER.warning(
                "PDF_SOURCE_LAYER_OVERRIDE primitive_id=%s requested=%s effective=%s "
                "reason=semantic_doc_precedence",
                prim.id,
                prim.layer,
                effective[0],
            )
        return effective
    if prim.type == "line":
        return _LAYER_BY_PDF_SOURCE_CLASSIFICATION.get(prim.layer, _DEFAULT_LAYER)
    return _DEFAULT_LAYER


def _ensure_layer(doc, name: str, color: int) -> None:
    if name not in doc.layers:
        doc.layers.new(name=name, dxfattribs={"color": color})


# Style TEXT dùng font TTF Unicode — bắt buộc cho mọi nhãn tiếng Việt có
# dấu (vd "VẬT LIỆU", "SỐ LƯỢNG"). Style "Standard" mặc định của
# ezdxf.new() (không setup=True) dùng font "txt" (txt.shx) — 1 font stroke
# cơ bản của AutoCAD KHÔNG có glyph cho ký tự có dấu, khiến text hiển thị
# sai/mất dấu khi mở trong AutoCAD. Đã xác nhận bằng reproduce trực tiếp:
# doc.styles.get("Standard").dxf.font == "txt", bigfont == "".
_UNICODE_TEXT_STYLE = "VN_UNICODE"
_UNICODE_TEXT_FONT = "Arial.ttf"


def _ensure_unicode_text_style(doc) -> str:
    """Tạo (nếu chưa có) 1 text style trỏ tới font TTF Unicode và trả về
    tên style đó. Idempotent — an toàn gọi nhiều lần (vd builder.py build
    lần đầu, repair.py đọc lại file cũ rồi vẽ lại text sau repair)."""
    if _UNICODE_TEXT_STYLE not in doc.styles:
        doc.styles.add(_UNICODE_TEXT_STYLE, font=_UNICODE_TEXT_FONT)
    return _UNICODE_TEXT_STYLE


def _add_confirmed_dimensions(
    doc,
    msp,
    dimension_specs: Sequence[NativeLinearDimensionSpec],
    written_geometry_by_primitive_id: Dict[str, dict],
    *,
    capture_line_integrity: bool = False,
) -> tuple[Dict[str, str], Dict[str, dict], tuple[DimensionLineExpectation, ...] | None]:
    """Emit dimensions from the exact line geometry already written to DXF."""
    handles: Dict[str, str] = {}
    written: Dict[str, dict] = {}
    expectations: list[DimensionLineExpectation] = []
    if capture_line_integrity and len(dimension_specs) > _MAX_DIMENSION_LINE_EXPECTATIONS:
        raise ValueError("dimension line integrity capture resource limit exceeded")
    for spec in dimension_specs:
        line = written_geometry_by_primitive_id.get(
            spec.geometry_primitive_id
        )
        if line is None or line.get("type") != "line":
            raise ValueError(
                "Dimension spec references line "
                f"{spec.geometry_primitive_id!r}, but that line was not "
                "written to the DXF."
            )
        start = line["start"]
        end = line["end"]
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length <= 0:
            if spec.approved_value_mm is not None:
                raise ValueError(
                    f"Dimension spec {spec.id!r} references zero-length LINE geometry."
                )
            continue
        # Place the dimension line on the outward normal, far enough from the
        # measured line to remain legible without changing the measurement.
        offset = max(length * 0.08, 5.0)
        normal_x, normal_y = -dy / length, dx / length
        midpoint = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        base = (midpoint[0] + normal_x * offset, midpoint[1] + normal_y * offset)
        angle = math.degrees(math.atan2(dy, dx))
        override = msp.add_linear_dim(
            base=base,
            p1=start,
            p2=end,
            location=base,
            angle=angle,
            dxfattribs={"layer": "DIMENSIONS"},
        )
        override.render()
        dimension = override.dimension
        handles[spec.id] = dimension.dxf.handle
        if capture_line_integrity:
            block_name = dimension.dxf.geometry
            block = doc.blocks.get(block_name)
            if block is None or tuple(block.base_point) != (0.0, 0.0, 0.0):
                raise ValueError("dimension line integrity capture has unsupported block frame")
            if int(dimension.dxf.dimtype) & 7 != 0:
                raise ValueError("dimension line integrity capture supports linear type 0 only")
            extrusion = tuple(dimension.dxf.get("extrusion", (0.0, 0.0, 1.0)))
            if extrusion != (0.0, 0.0, 1.0):
                raise ValueError("dimension line integrity capture has unsupported extrusion")
            lines = [entity for entity in block if entity.dxftype() == "LINE"]
            if not lines or len(lines) > _MAX_LINES_PER_DIMENSION_EXPECTATION:
                raise ValueError("dimension line integrity capture incomplete or resource limit exceeded")
            endpoints = []
            for line_entity in lines:
                start = tuple(float(value) for value in line_entity.dxf.start)
                end = tuple(float(value) for value in line_entity.dxf.end)
                if not all(math.isfinite(value) for value in (*start, *end)):
                    raise ValueError("dimension line integrity capture contains non-finite LINE")
                endpoints.append((start, end))
            expectations.append(DimensionLineExpectation(
                spec.id, dimension.dxf.handle, block_name, tuple(endpoints),
            ))
        written[spec.id] = {
            "layer": "DIMENSIONS",
            "measurement": length,
            "approved_value_mm": spec.approved_value_mm,
            "geometry_primitive_id": spec.geometry_primitive_id,
            "source_ref": spec.source_ref,
        }
    return handles, written, tuple(expectations) if capture_line_integrity else None


def _dimension_specs_from_cross_validations(
    primitive_doc: PrimitiveIRDocument,
) -> list[NativeLinearDimensionSpec]:
    return [
        NativeLinearDimensionSpec(
            id=validation.id,
            geometry_primitive_id=validation.geometry_primitive_id,
            approved_value_mm=None,
            source_ref=validation.text_primitive_id,
        )
        for validation in primitive_doc.cross_validations
        if validation.status == "confirmed"
    ]


def _validate_explicit_dimension_specs(
    dimension_specs: Sequence[NativeLinearDimensionSpec],
) -> None:
    ids: set[str] = set()
    for spec in dimension_specs:
        if not spec.id or spec.id in ids:
            raise ValueError("explicit dimension spec ids must be non-empty and unique")
        ids.add(spec.id)
        value = spec.approved_value_mm
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError(
                f"dimension spec {spec.id!r} approved_value_mm must be finite positive"
            )


def build_dxf(
    primitive_doc: PrimitiveIRDocument,
    output_path: str,
    semantic_doc: Optional[object] = None,
    solved_primitives: Optional[Dict[str, object]] = None,
    dxf_version: str = "R2010",
    build_components: bool = False,
    build_dimensions: bool = False,
    dimension_specs: Optional[Sequence[NativeLinearDimensionSpec]] = None,
    contour_join_by_id: Optional[Dict[str, dict]] = None,
    *,
    capture_dimension_line_integrity: bool = False,
) -> BuildResult:
    """Build 1 file DXF thật từ `primitive_doc`. Trả về `BuildResult` —
    không raise nếu 1 primitive không vẽ được (thiếu geometry/text_data),
    chỉ ghi vào `skipped_primitive_ids` (lỗi dữ liệu cục bộ không nên chặn
    cả bản vẽ, đúng nguyên tắc "ưu tiên rule-based/deterministic" mục 7 —
    phần thiếu dữ liệu nên lộ ra để review, không nên crash toàn bộ).

    `build_components=True` (mặc định `False`, giữ nguyên hành vi cũ) +
    có `semantic_doc`: sau khi vẽ xong hình học thô, gọi thêm
    `semantic_components.assemble_semantic_components()` để chèn lớp
    "linh kiện" (frame_insert_beam/bracket_insert/panel_insert +
    4 hàm compound panel_rect_insert/bracket_L_insert/hinge_insert/
    node_insert, mục 12.4 + 11.4) trên layer riêng `COMP_*`, song song với
    hình học thô — xem docstring đầu `semantic_components.py`.

    Raise ImportError nếu chưa cài `ezdxf`.
    """
    if type(capture_dimension_line_integrity) is not bool:
        raise ValueError("capture_dimension_line_integrity must be a bool")
    if capture_dimension_line_integrity and not build_dimensions:
        raise ValueError("capture_dimension_line_integrity requires build_dimensions=True")
    if primitive_doc.calibration.status != "verified":
        raise ValueError(
            "Primitive IR calibration is needs_verification; DXF build is "
            "refused until a hash-bound approval marks it verified."
        )
    if dimension_specs is not None:
        if not build_dimensions:
            raise ValueError("dimension_specs requires build_dimensions=True")
        _validate_explicit_dimension_specs(dimension_specs)
    joins = {} if contour_join_by_id is None else contour_join_by_id
    validate_contour_joins(joins)
    try:
        import ezdxf
    except ImportError as exc:
        raise ImportError(
            "Cần cài package 'ezdxf' để dùng DXF Builder: "
            "pip install ezdxf --break-system-packages"
        ) from exc

    part_type_by_id = _part_type_by_primitive_id(semantic_doc)
    solved_primitives = solved_primitives or {}

    doc = ezdxf.new(dxfversion=dxf_version)
    # CAD-Agent produces geometry in millimetres. Declaring the unit prevents
    # AutoCAD from applying an implicit conversion when it opens the DXF.
    doc.header["$INSUNITS"] = 4  # millimetres
    msp = doc.modelspace()

    result = BuildResult(output_path=output_path, contour_join_by_id=deepcopy(joins))

    if build_dimensions:
        _ensure_layer(doc, "DIMENSIONS", 2)

    for prim in primitive_doc.primitives:
        layer_name, color = _layer_for_primitive(prim, part_type_by_id)
        _ensure_layer(doc, layer_name, color)

        entity = None
        written: Optional[dict] = None

        if prim.type == "line" and prim.geometry is not None:
            s, e = prim.geometry.start, prim.geometry.end
            solved = solved_primitives.get(prim.id)
            if solved is not None:
                s, e = solved.start, solved.end
            entity = msp.add_line((s.x, s.y), (e.x, e.y), dxfattribs={"layer": layer_name})
            written = {"type": "line", "start": (s.x, s.y), "end": (e.x, e.y)}

        elif prim.type == "circle" and prim.geometry is not None:
            c, r = prim.geometry.center, prim.geometry.radius
            entity = msp.add_circle((c.x, c.y), r, dxfattribs={"layer": layer_name})
            written = {"type": "circle", "center": (c.x, c.y), "radius": r}

        elif prim.type == "arc" and prim.geometry is not None:
            g = prim.geometry
            entity = msp.add_arc(
                (g.center.x, g.center.y), g.radius, g.start_angle_deg, g.end_angle_deg,
                dxfattribs={"layer": layer_name},
            )
            written = {
                "type": "arc", "center": (g.center.x, g.center.y), "radius": g.radius,
                "start_angle_deg": g.start_angle_deg, "end_angle_deg": g.end_angle_deg,
            }

        elif prim.type == "text" and prim.text_data is not None:
            td = prim.text_data
            entity = msp.add_text(
                td.content,
                dxfattribs={
                    "layer": layer_name,
                    "height": td.height,
                    "rotation": td.rotation_deg,
                    "insert": (td.position.x, td.position.y),
                    "style": _ensure_unicode_text_style(doc),
                },
            )
            written = {
                "type": "text", "content": td.content,
                "insert": (td.position.x, td.position.y),
                "height": td.height, "rotation_deg": td.rotation_deg,
            }

        if entity is None:
            result.skipped_primitive_ids.append(prim.id)
            continue

        handle = entity.dxf.handle
        # ghi đè trực tiếp lên Primitive gốc (null -> giá trị thật, xem
        # docstring module này + primitive_ir.schema.json field 'handle')
        prim.handle = handle
        prim.layer = layer_name

        result.handle_by_primitive_id[prim.id] = handle
        result.layer_by_primitive_id[prim.id] = layer_name
        result.written_geometry_by_primitive_id[prim.id] = written
        result.entity_count += 1

    if build_dimensions:
        active_dimension_specs = (
            _dimension_specs_from_cross_validations(primitive_doc)
            if dimension_specs is None
            else list(dimension_specs)
        )
        (
            result.dimension_handle_by_cross_validation_id,
            result.written_dimension_by_cross_validation_id,
            result.dimension_line_expectations,
        ) = _add_confirmed_dimensions(
            doc,
            msp,
            active_dimension_specs,
            result.written_geometry_by_primitive_id,
            capture_line_integrity=capture_dimension_line_integrity,
        )
        result.dimension_count = len(result.dimension_handle_by_cross_validation_id)
        if capture_dimension_line_integrity and result.dimension_count == 0:
            raise ValueError("dimension line integrity cannot qualify zero dimensions")

    if build_components and semantic_doc is not None:
        from .semantic_components import assemble_semantic_components

        assembly = assemble_semantic_components(
            doc, msp, semantic_doc, result.written_geometry_by_primitive_id,
        )
        for res in assembly.inserted:
            result.component_handle_by_part_id[res.part_id] = res.handle
            result.component_type_by_part_id[res.part_id] = res.component_type

            blockref_entity = doc.entitydb.get(res.handle)
            insert_pt = blockref_entity.dxf.insert
            attribs = {a.dxf.tag: a.dxf.text for a in blockref_entity.attribs}
            result.written_component_by_part_id[res.part_id] = {
                "block_name": blockref_entity.dxf.name,
                "layer": blockref_entity.dxf.layer,
                "insert": (insert_pt.x, insert_pt.y, insert_pt.z),
                "xscale": blockref_entity.dxf.xscale,
                "yscale": blockref_entity.dxf.yscale,
                "zscale": blockref_entity.dxf.zscale,
                "rotation_deg": blockref_entity.dxf.rotation,
                "attribs": attribs,
            }
        result.skipped_part_ids = assembly.skipped_part_ids
        result.skipped_part_reasons = assembly.skip_reasons
        result.component_count = len(assembly.inserted)

    doc.saveas(output_path)
    return result
