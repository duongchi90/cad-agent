"""
table_extraction.py — Tier 2 (bảng nhiều cột) theo chiến lược đã benchmark ở
mục 9.2 của tài liệu tổng hợp.

VẤN ĐỀ MÀ MODULE NÀY GIẢI QUYẾT: benchmark thật cho thấy khi OCR nguyên khối 1
bảng thông số nhiều cột, cột nhãn hàng bị "xáo trộn" với cột số liệu (mục 9.2,
dòng "Bảng thông số nhiều cột"). Nguyên nhân: các ô sát cạnh nhau, Tesseract
không biết ranh giới ô, gộp chữ các ô kề nhau thành 1 dòng sai.

GIẢI PHÁP: KHÔNG đọc nguyên khối. Dùng kết quả line-detection đã có (danh sách
RawLine từ geometry_extraction, KHÔNG chạy lại Hough riêng) để nhận diện lưới
ngang-dọc của bảng, tách thành từng ô (cell) theo toạ độ giao cắt của lưới,
rồi OCR / đọc TỪNG ô độc lập. Nhờ ranh giới ô cứng (do line tạo ra), không
còn hiện tượng chữ ô này nhảy sang ô kia.

QUAN TRỌNG về nguồn dữ liệu: module này nhận vào `lines` (RawLine ở toạ độ
pixel) do bước geometry_extraction ở trên đã chạy xong — không tự gọi
OpenCV/Hough lần nữa, tránh trùng lặp + giữ tính deterministic (cùng 1 bộ
line vào -> cùng 1 lưới ra). Lý do dùng line đã phát hiện thay vì phát hiện
lưới riêng: line bảng và line khung/panel đều được Canny+Hough bắt trong 1
lượt, việc tách ô bảng chỉ là lọc + gom các line đó theo vùng bảng (TABLE_ROI).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

import numpy as np

from .geometry_extraction import RawLine
from .models import new_id
from .text_extraction import (
    RawText, classify_semantic_role, extract_text_tesseract,
)

Bbox = Tuple[float, float, float, float]  # (x_min, y_min, x_max, y_max) pixel


# ----------------------------------------------------------- TableCell --
@dataclass
class TableCell:
    """1 ô của bảng, xác định bằng giao 2 line lưới (hàng × cột)."""
    id: str
    row: int
    col: int
    bbox_px: Bbox  # toạ độ pixel của ô, đã thu nhỏ 1 chút để crop không dính line kẻ
    content: str = ""  # nội dung đọc được, gán sau khi OCR/đọc ô

    def __post_init__(self):
        self.id = self.id or new_id("cell")


# ------------------------------------------------- phân loại ngang/dọc --
def _line_orientation(p1, p2, tol: float = 5.0) -> str:
    """Trả về 'h' (ngang), 'v' (dọc) hoặc 'o' (chéo/không phân loại).

    tol = dung sai pixel: nếu chênh lệch toạ độ theo 1 trục < tol thì coi như
    song song trục kia. Dùng tuyệt đối (pixel) chứ không phải tỷ lệ để đơn
    giản — lưới bảng thường có line dài, sai số pixel nhỏ không đổi kết quả.
    """
    dx = abs(p2[0] - p1[0])
    dy = abs(p2[1] - p1[1])
    if dy <= tol and dx > tol:
        return "h"
    if dx <= tol and dy > tol:
        return "v"
    return "o"


def _collect_axis_values(
    lines: List[RawLine],
    table_roi: Bbox,
    orientation: str,
    merge_tol: float = 12.0,
) -> List[float]:
    """Lấy các toạ độ trục cố định của line theo orientation ('h' -> giá trị y,
    'v' -> giá trị x), chỉ giữ line nằm trong table_roi, rồi gom (cluster) các
    giá trị gần nhau thành 1 (vì Canny+Hough đôi khi tách 1 line bảng thành 2-3
    đoạn cùng toạ độ). Trả về danh sách toạ độ trục đã sắp xếp tăng dần."""
    x0, y0, x1, y1 = table_roi
    raw_vals: List[float] = []
    for ln in lines:
        orient = _line_orientation(ln.p1_px, ln.p2_px)
        if orient != orientation:
            continue
        # chỉ giữ line có tâm bbox nằm (gần) trong vùng bảng
        mx = (ln.p1_px[0] + ln.p2_px[0]) / 2.0
        my = (ln.p1_px[1] + ln.p2_px[1]) / 2.0
        if not (x0 - merge_tol <= mx <= x1 + merge_tol and y0 - merge_tol <= my <= y1 + merge_tol):
            continue
        # với line ngang lấy y trung bình của 2 đầu; line dọc lấy x trung bình
        if orientation == "h":
            raw_vals.append((ln.p1_px[1] + ln.p2_px[1]) / 2.0)
        else:
            raw_vals.append((ln.p1_px[0] + ln.p2_px[0]) / 2.0)

    if not raw_vals:
        return []

    # cluster 1 chiều: gom các giá trị cách nhau < merge_tol
    raw_vals.sort()
    clusters: List[List[float]] = [[raw_vals[0]]]
    for v in raw_vals[1:]:
        if v - clusters[-1][-1] <= merge_tol:
            clusters[-1].append(v)
        else:
            clusters.append([v])
    return [float(np.mean(c)) for c in clusters]


# ----------------------------------------------------------- detect_grid --
def detect_grid(
    lines: List[RawLine],
    table_roi: Bbox,
    merge_tol: float = 12.0,
) -> Tuple[List[float], List[float]]:
    """Phát hiện lưới bảng từ danh sách RawLine có sẵn.

    Trả về (xs, ys): toạ độ pixel các đường lưới dọc (cột) và ngang (hàng),
    đã gom cụm và sắp xếp tăng dần. Lưới tối thiểu cần >=2 đường mỗi trục để
    tạo ra ít nhất 1 ô; nếu thiếu, trả về list rỗng (bên gọi tự xử lý)."""
    xs = _collect_axis_values(lines, table_roi, "v", merge_tol=merge_tol)
    ys = _collect_axis_values(lines, table_roi, "h", merge_tol=merge_tol)
    return xs, ys


# ----------------------------------------------------------- build_cells --
def build_cells(
    xs: List[float],
    ys: List[float],
    table_roi: Bbox,
    inset: float = 3.0,
) -> List[TableCell]:
    """Ghép các giao điểm lưới thành ô. xs/ys là toạ độ pixel của các đường
    lưới dọc/ngang (từ detect_grid). inset = thu hẹp bbox ô bao nhiêu pixel để
    crop không dính line kẻ (cốt để tránh nhiễu OCR)."""
    cells: List[TableCell] = []
    if len(xs) < 2 or len(ys) < 2:
        return cells  # không đủ đường để tạo ô

    for row in range(len(ys) - 1):
        for col in range(len(xs) - 1):
            cx0, cx1 = xs[col], xs[col + 1]
            cy0, cy1 = ys[row], ys[row + 1]
            cells.append(TableCell(
                id=new_id("cell"),
                row=row,
                col=col,
                bbox_px=(cx0 + inset, cy0 + inset, cx1 - inset, cy1 - inset),
            ))
    return cells


# ----------------------------------------------------------- read_cells --
def _default_cell_reader(image_bgr: np.ndarray, bbox: Bbox) -> str:
    """Reader mặc định: crop vùng ô rồi OCR bằng Tesseract (tier 2 dùng lại
    công cụ tier 1 cho từng ô — Tesseract đọc tốt từng ô một khi ô đã tách
    sạch, theo benchmark mục 9.2 cột số liệu)."""
    x0, y0, x1, y1 = (int(round(v)) for v in bbox)
    crop = image_bgr[y0:y1, x0:x1]
    if crop.size == 0:
        return ""
    # dùng extract_text_tesseract để giữ cùng đường đi tiền xử lý + gộp từ
    results = extract_text_tesseract(crop)
    # 1 ô thường chỉ chứa 1 nhãn/số duy nhất; gộp kết quả các dòng thành 1
    return " ".join(r.content.strip() for r in results if r.content.strip())


# ------------------------------------------------------- extract_table_cells --
def extract_table_cells(
    image_bgr: np.ndarray,
    lines: List[RawLine],
    table_roi: Bbox,
    cell_reader: Optional[Callable[[np.ndarray, Bbox], str]] = None,
    merge_tol: float = 12.0,
    inset: float = 3.0,
) -> Tuple[List[TableCell], List[RawText]]:
    """Entry point tier 2 (mục 9.2): nhận diện lưới bảng từ `lines` đã có,
    tách thành từng ô, đọc nội dung từng ô độc lập.

    Trả về:
      - table_cells: danh sách TableCell (có bbox + row/col + content đã đọc).
      - raw_texts: danh sách RawText (source='text_tesseract', semantic_role
        được gán tự động qua classify_semantic_role) sẵn sàng ghép vào
        Primitive IR cùng các tier khác.

    cell_reader: callable tuỳ chọn (image_bgr, bbox) -> str, dùng thay
    Tesseract mặc định — vd. nối với Vision API cho ô có chữ nhỏ/xoay (xem
    cách text_extraction.extract_text_vision thiết kế interface tương tự).
    """
    xs, ys = detect_grid(lines, table_roi, merge_tol=merge_tol)
    cells = build_cells(xs, ys, table_roi, inset=inset)
    reader = cell_reader if cell_reader is not None else _default_cell_reader

    raw_texts: List[RawText] = []
    for cell in cells:
        content = reader(image_bgr, cell.bbox_px).strip()
        cell.content = content
        if not content:
            continue  # ô rỗng (vd ô góc không có chữ) -> không sinh RawText
        role, value = classify_semantic_role(content)
        raw_texts.append(RawText(
            id=new_id("rawtext"),
            content=content,
            bbox_px=cell.bbox_px,
            rotation_deg=0.0,
            confidence=0.85,  # Tesseract từng ô: khá tốt sau khi đã tách (mục 9.2)
            source="text_tesseract",
            parsed_value=value,
            semantic_role=role if role != "unknown" else "table_cell",
        ))
    return cells, raw_texts
