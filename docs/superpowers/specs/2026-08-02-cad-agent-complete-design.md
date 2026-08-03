# CAD Agent — Đặc tả tổng hợp hoàn chỉnh

Ngày: 2026-08-02  
Trạng thái: ĐÃ DUYỆT bởi chủ dự án ngày 2026-08-02  
Mục tiêu triển khai: AutoCAD Mechanical 2027  
Repo đích: duongchi90/cad-agent

## 1. Quyết định sản phẩm

CAD Agent không phải là một AI “nhìn ảnh rồi vẽ lại các nét”. Nó phải hoạt
động như một hệ thống hỗ trợ kỹ sư thiết kế:

1. Hiểu loại, mục đích và tiêu chuẩn của bản vẽ.
2. Khởi tạo môi trường CAD đúng chuẩn trước khi tạo entity.
3. Xây dựng hình học từ kích thước, datum và quan hệ kỹ thuật đã được duyệt.
4. Tìm và tái sử dụng bản vẽ, cụm chi tiết và block chuẩn có nguồn gốc rõ ràng.
5. Dùng PDF/ảnh để hiểu hình dáng, topology và kiểm tra trực quan, không dùng
   pixel làm thước đo kỹ thuật có thẩm quyền.
6. Tạo entity CAD native, chỉnh sửa được trong AutoCAD Mechanical 2027.
7. Render lại kết quả sau mỗi lần tạo hoặc sửa.
8. Kiểm tra từng vùng của từng hình chiếu, đo ngược kích thước và kiểm tra toàn
   cảnh trước khi báo hoàn thành.
9. Chỉ sửa hoặc lưu vào bản vẽ sản xuất sau khi có backup, phê duyệt và lần
   review thứ hai.

Tên định hướng kỹ thuật:

> Dimension-first, image-guided, profile-controlled CAD reconstruction.

Nghĩa là:

- dimension-first: kích thước và ràng buộc đã duyệt điều khiển tọa độ;
- image-guided: ảnh/PDF hỗ trợ nhận dạng hình dáng và đối chiếu;
- profile-controlled: layer, style, block, tỷ lệ và quy tắc trình bày lấy từ
  profile/template được duyệt, không để AI tự sáng tác mỗi lần.

## 2. Phạm vi

### 2.1 Phạm vi lõi

Lõi phải dùng được cho nhiều loại bản vẽ kỹ thuật 2D và nhiều dạng công việc
trong từng domain, không hard-code riêng cho một xe, một loại cải tạo, một tàu
hoặc một bản mẫu:

- bản vẽ bố trí chung;
- bản vẽ lắp;
- bản vẽ chi tiết;
- bản vẽ kết cấu;
- mặt cắt;
- sơ đồ và bản vẽ trình duyệt;
- bản vẽ cải tạo ô tô.

Các khái niệm domain như trục xe, cabin, thùng hàng, cẩu, chassis, station,
frame hoặc gridline được ánh xạ qua Domain Pack và Drawing Profile.

Kiến trúc lõi không được phụ thuộc vào một cặp trạng thái trước/sau cụ thể.
Thông tin của từng hồ sơ phải đi qua Drawing Definition, Job/Conversion
Profile, Domain Pack, Component Registry và dữ liệu kỹ thuật đã được duyệt.

### 2.2 Domain đầu tiên

Domain đầu tiên là toàn bộ nhóm thiết kế cải tạo ô tô mà hệ thống được cấu hình
và kỹ sư phê duyệt, không phải một phương án cải tạo duy nhất. Các ca có thể
bao gồm nhưng không giới hạn ở:

- thay đổi, tháo hoặc lắp kết cấu thùng hàng;
- lắp, tháo hoặc thay đổi thiết bị chuyên dùng;
- thay đổi bố trí các cụm và chi tiết liên quan;
- cập nhật hình chiếu, mặt cắt, kích thước, khối lượng và ghi chú tương ứng.

Trường hợp “xe tải có mui chuyển thành xe tải gắn cẩu sau cabin và thùng lửng”
chỉ được dùng như một ca pilot/fixture nếu chủ dự án chọn nó để kiểm chứng. Nó
không phải định nghĩa sản phẩm, không phải nhánh xử lý cố định và không được
hard-code vào schema, solver, Operation Plan hoặc AutoCAD executor. Một loại
cải tạo mới phải được bổ sung chủ yếu bằng cấu hình, profile, domain pack và
component đã audit, không phải sửa kiến trúc lõi.

AI không được tự phê duyệt các quyết định thiết kế, kết cấu, ổn định, tải trọng,
phân bố khối lượng hoặc tuân thủ pháp lý. Những dữ liệu này phải đến từ tính
toán, nguồn kỹ thuật hoặc phê duyệt của kỹ sư.

### 2.3 Ngoài phạm vi ban đầu

- Không tự thiết kế một phương án cải tạo hoàn toàn mới chỉ từ mô tả ngắn.
- Không dùng ảnh raster để suy ra kích thước sản xuất.
- Không sửa trực tiếp hàng loạt DWG sản xuất.
- Không hợp nhất toàn bộ mã nguồn của các repo bên ngoài vào một khối.
- Không mở hàng trăm lệnh primitive như draw_line hoặc draw_arc cho LLM dùng
  trực tiếp.
- Không coi một DWG cũ là template chuẩn chỉ vì bản vẽ đó có nhiều layer,
  block hoặc dimension.

### 2.4 Các phương án đã xem xét

| Phương án | Ưu điểm | Hạn chế | Quyết định |
|---|---|---|---|
| Chỉ bổ sung prompt nhắc AI setup và zoom kiểm tra | Nhanh, ít thay đổi code | Không cưỡng chế được; AI có thể quên hoặc báo xong thiếu bằng chứng | Không chọn làm giải pháp chính |
| Dùng nguyên một DWG cũ làm template | Tái sử dụng nhanh layer/style/block | Kéo theo lỗi legacy, override, font thiếu, entity explode và nội dung riêng của nguồn | Không chọn |
| DWT + Drawing Profile + Dimension/Constraint IR + hai cổng kiểm soát | Chuẩn hóa, kiểm thử được, truy vết được và mở rộng theo domain | Cần xây contract, audit và verification engine | Phương án được chọn |

Prompt vẫn cần để điều phối, nhưng các điều kiện an toàn và chất lượng phải được
cưỡng chế bằng schema, validator, state machine, test và release gate.

## 3. Các nguyên tắc bắt buộc

### 3.1 Thứ tự nguồn dữ liệu có thẩm quyền

| Thứ tự | Nguồn | Cách sử dụng |
|---:|---|---|
| 1 | Kích thước nguồn đã được duyệt | Điều khiển trực tiếp kích thước/tọa độ |
| 2 | Datum đã duyệt | Trục, tâm, baseline, mặt chuẩn, cao độ, gốc tọa độ |
| 3 | Quan hệ hình học đã duyệt | Song song, vuông góc, đồng tâm, tiếp tuyến, đối xứng, trùng |
| 4 | Block/chi tiết CAD chuẩn có provenance | Tái sử dụng khi đúng loại, revision và điều kiện áp dụng |
| 5 | PDF/ảnh nguồn | Topology, view, attachment, đường cong, nét khuất, hatch, bố cục |
| 6 | Đo pixel | Chỉ là ước lượng, bắt buộc gắn trạng thái ESTIMATED |

Khi hai nguồn authoritative mâu thuẫn, hệ thống phải dừng với
dimension_conflict. Không được chọn giá trị “trông giống ảnh hơn”.

Khi hình ảnh không khớp với kích thước authoritative, hệ thống giữ hình học
kỹ thuật và tạo cảnh báo source_visual_conflict.

### 3.2 Model Space và tỷ lệ

- Model Space dùng đơn vị mm và dựng hình 1:1.
- Tỷ lệ 1:5, 1:10, 1:20 hoặc tỷ lệ khác nằm ở viewport/Layout và style chú
  thích theo profile.
- scale_mm_per_px chỉ phục vụ overlay/đối chiếu, không được thay đổi model
  coordinates.
- LTSCALE, CELTSCALE, PSLTSCALE, MSLTSCALE và viewport scale phải được kiểm
  tra cùng nhau; không kết luận nét đúng chỉ từ LTSCALE.

### 3.3 Entity native và khả năng chỉnh sửa

Kết quả ưu tiên:

- LINE, ARC, CIRCLE, LWPOLYLINE hoặc entity Mechanical phù hợp;
- DIMENSION native;
- HATCH native và boundary hợp lệ;
- BLOCK/INSERT cho chi tiết lặp;
- TEXT/MTEXT theo TextStyle;
- linetype, color và lineweight theo BYLAYER;
- Layout, viewport, title block và plot setting có thể tiếp tục chỉnh sửa.

Không được tạo hình “đúng ảnh” bằng hàng nghìn đoạn rời hoặc explode toàn bộ
dimension/block nếu không có lý do kỹ thuật được ghi nhận.

### 3.4 Provenance

Mỗi dimension, constraint, component và entity quan trọng phải mang một trong
bốn trạng thái:

- EXACT: lấy trực tiếp từ dữ liệu đã duyệt;
- CONSTRAINED: được giải từ kích thước và quan hệ đã duyệt;
- ESTIMATED: suy ra từ ảnh hoặc heuristic chưa duyệt;
- UNRESOLVED: thiếu hoặc mơ hồ dữ liệu.

Không có entity model-critical ở trạng thái ESTIMATED hoặc UNRESOLVED được đi
vào bản phát hành authoritative.

### 3.5 An toàn khi thao tác AutoCAD

- Read-only hoặc disposable drawing là mặc định.
- Mỗi run có run_id, source hash, input hash và operation-plan hash.
- Lệnh phải idempotent hoặc có cơ chế phát hiện chạy lặp.
- Trước sửa production drawing: tạo backup, chỉ rõ file đích, xin phê duyệt.
- Sau sửa: render, đo ngược, review lần hai rồi mới cho phép save.
- Không tắt SECURELOAD bằng cách đặt SECURELOAD = 0.
- Script/plugin phải nằm trong TRUSTEDPATHS hoặc được ký/triển khai theo cơ chế
  tin cậy của AutoCAD.
- Không dùng quit/save/close mơ hồ trên tài liệu người dùng đang mở.

## 4. Kiến trúc tổng thể

~~~mermaid
flowchart TD
    A["DWG, DXF, PDF, ảnh và dữ liệu xe"] --> B["Source + Legacy Analyzer"]
    B --> C["Knowledge Base và Similarity"]
    B --> D["Dimension, Datum và Constraint IR"]
    C --> E["Python Decision Engine"]
    D --> E
    E --> F["Drawing Setup + Operation Plan"]
    F --> G["AutoCAD .NET Dispatcher"]
    G --> H["AutoCAD Mechanical 2027"]
    H --> I["Render, Measure và Region Evidence"]
    I --> E
    I --> J["Release Gate"]
~~~

### 4.1 Ranh giới trách nhiệm

| Thành phần | Trách nhiệm | Không được làm |
|---|---|---|
| Source Analyzer | Kiểm kê nguồn, view, text, dimension, layer, block, style | Tự phê duyệt kích thước |
| Legacy CAD Analyzer | Trích xuất tri thức từ DWG/DXF cũ | Coi toàn bộ DWG là tiêu chuẩn |
| Similarity Engine | Tìm bản vẽ/cụm gần nhất theo metadata và hình học | Copy mù toàn bộ bản cũ |
| Decision Engine | Chọn profile, giải constraint, lập kế hoạch cấp nghiệp vụ | Phát lệnh primitive tùy tiện |
| Deterministic Builder | Tạo hình học từ nghiệm đã chốt | Thay tọa độ bằng pixel |
| File IPC/.NET Dispatcher | Thực thi, inspect, zoom, render, measure | Tự quyết định thiết kế |
| Verification Engine | Quản lý region, bằng chứng, residual, coverage | Duyệt khi thiếu ảnh sau lần sửa cuối |
| Human Approval | Duyệt dữ liệu mơ hồ, thay đổi kỹ thuật, production save | Bị thay thế bởi confidence của AI |

### 4.2 Giữ các module hiện có

Các ranh giới hiện có được giữ và mở rộng:

- primitive_ir_lib: observation hình học, OCR, Dimension IR và datum candidate;
- semantic_ir_lib: view model, datum refs, Constraint IR, solver status,
  residual và conflict;
- dxf_builder_lib: nhận solved geometry, tạo entity exact/constrained,
  DIMENSION native và provenance;
- cad_agent: orchestration, checkpoint, hash, approval và run manifest;
- mcp_integration_lib: giao tiếp hiện có qua File IPC;
- CadAgent.AutoCAD2027: dispatcher phía AutoCAD bằng .NET;
- ezdxf/analyzer: kiểm kê và phân tích kho DXF/DWG đã chuyển đổi.

ezdxf không phải nơi AI tự quyết định tọa độ. Nếu dxf_builder_lib dùng nó để
serialize DXF thì quyết định hình học vẫn phải đến từ solved geometry và
Operation Plan đã duyệt.

Hệ thống có thể có hai đường xuất nhưng chỉ có một solved model:

1. Offline/draft path: dxf_builder_lib tạo DXF có thể mở lại để test và review.
2. AutoCAD-native path: CadAgent.AutoCAD2027 thực thi Operation Plan đã
   validation trong AutoCAD Mechanical 2027.

Hai đường phải đo ngược ra cùng dimension/constraint trong tolerance được cấu
hình. Không module nào được tự giải lại hình học theo một bộ quy tắc khác.

## 5. Quy trình chuẩn của một kỹ sư trước khi vẽ

### 5.1 Drawing Definition

Trước khi tạo entity đầu tiên, AI phải xác định:

- domain;
- loại bản vẽ;
- mục đích bản vẽ;
- nguồn và revision;
- tiêu chuẩn áp dụng;
- trạng thái bản vẽ: mới, sửa đổi, tái dựng hoặc tham khảo;
- mức phát hành: draft, review hoặc authoritative;
- các trường cần kỹ sư phê duyệt.

Ví dụ:

~~~yaml
drawing_definition:
  domain: AUTOMOTIVE_CONVERSION
  drawing_type: GENERAL_ARRANGEMENT
  purpose: DESIGN_APPROVAL
  source_mode: RECONSTRUCT_FROM_APPROVED_SOURCE
  standard_profile: VN_VEHICLE_CONVERSION_V1
  revision: "01"
  release_profile: REVIEW
~~~

### 5.2 Chọn profile và template

Khuyến nghị khởi đầu:

- template_id: VX_MECHANICAL_2027_TEMPLATE;
- domain_pack: AUTOMOTIVE_CONVERSION_V1;
- layer_profile: VEHICLE_CONVERSION_V1;
- block library: bộ block đã audit và duyệt;
- title block/layout: A4 đến A0 theo mẫu doanh nghiệp;
- font policy: profile mới và profile tương thích legacy tách riêng.

Template DWT chứa sẵn:

- units và measurement;
- layers, color, linetype, lineweight, plot/no-plot;
- TextStyle;
- DimStyle;
- MLeaderStyle;
- TableStyle;
- hatch patterns;
- Layout, viewport mẫu và page setup;
- plot style;
- title block;
- ký hiệu và block chuẩn.

### 5.3 Sheet Plan

AI lập kế hoạch:

- khổ giấy và hướng giấy;
- số tờ;
- danh sách hình chiếu;
- mặt cắt và detail view;
- vị trí tương đối;
- viewport scale;
- vùng dành cho dimension, notes, BOM hoặc bảng;
- title block và revision table.

### 5.4 Datum và View Plan

Mỗi view phải có:

- view_id và source_region;
- hệ trục;
- datum gốc;
- trục tâm/baseline;
- các trục lặp;
- cao độ;
- quan hệ shared/view-local;
- phép biến đổi chỉ dùng cho overlay.

### 5.5 Annotation Plan

Trước khi ghi kích thước:

- dimension nào là driving, reference hoặc derived;
- dimension nằm ở view nào;
- điểm/đường gióng bám vào entity nào;
- DimStyle theo viewport scale;
- cách ghi tolerance;
- text height;
- leader, section symbol và hatch;
- tránh dimension trùng, cắt nhau hoặc thiếu attachment.

### 5.6 Drawing Initialization Gate

Không được tạo geometry nếu chưa đạt tất cả điều kiện:

- Drawing Definition hợp lệ;
- template/profile tồn tại và đúng revision;
- Model Space unit = mm, model scale = 1:1;
- sheet/view/viewport plan hợp lệ;
- layer, linetype, lineweight, DimStyle, TextStyle, hatch và plotstyle đã kiểm;
- datum/view plan đã khai báo;
- source hashes và approval record đã gắn;
- trạng thái setup = SETUP_VERIFIED.

Nếu thiếu lựa chọn ảnh hưởng kỹ thuật hoặc trình bày, trạng thái là
NEEDS_REVIEW; AI không tự đoán.

## 6. Hợp đồng dữ liệu

### 6.1 Source Manifest

~~~yaml
source_manifest:
  run_id: RUN-20260802-001
  files:
    - source_id: SRC-001
      type: PDF
      sha256: "EXAMPLE_SOURCE_PDF_SHA256"
      page_count: 1
      authority: VISUAL_AND_ANNOTATION_SOURCE
    - source_id: SRC-002
      type: DWG
      sha256: "EXAMPLE_SOURCE_DWG_SHA256"
      authority: LEGACY_REFERENCE
  vehicle_data:
    source_id: VEHICLE-REGISTER-001
    approval_status: APPROVED
~~~

### 6.2 Drawing Setup Plan

~~~yaml
drawing_setup_plan:
  definition_ref: DRAWDEF-001
  template:
    id: VX_MECHANICAL_2027_TEMPLATE
    revision: "1.0"
    sha256: "EXAMPLE_TEMPLATE_SHA256"
  domain_pack:
    id: AUTOMOTIVE_CONVERSION_V1
    revision: "1.0"
  model:
    unit: mm
    scale: "1:1"
    ucs: WORLD
  sheet:
    paper_size: A1
    orientation: LANDSCAPE
    layouts: [A1-01]
  viewports:
    - view_id: SIDE
      scale: "1:20"
      locked: true
  styles:
    layer_profile: VEHICLE_CONVERSION_V1
    textstyle: VX_TEXT
    dimstyle: VX_DIM_20
    mleaderstyle: VX_MLEADER
    plotstyle: VX_MONO
  status: SETUP_VERIFIED
~~~

### 6.3 Dimension IR

Mỗi dimension observation phải có tối thiểu:

~~~json
{
  "id": "DIM-001",
  "value": 500.0,
  "unit": "mm",
  "kind": "horizontal_distance",
  "scope": "view:SIDE",
  "from": {"datum_or_entity": "axle:front"},
  "to": {"datum_or_entity": "axle:rear"},
  "extension_geometry": {
    "p1_source": [0, 0],
    "p2_source": [0, 0],
    "dimension_line_source": [[0, 0], [0, 0]]
  },
  "dimension_role": "driving",
  "source": {
    "source_id": "SRC-001",
    "page": 1,
    "bbox": [0, 0, 0, 0]
  },
  "extraction": "vector_or_ocr_plus_geometry",
  "confidence": 0.98,
  "status": "APPROVED",
  "approval": {
    "approved_by": "ENGINEER",
    "approved_at": "2026-08-02T00:00:00+07:00"
  }
}
~~~

Một con số OCR không có attachment hợp lệ phải là UNRESOLVED.

### 6.4 Datum IR

~~~yaml
datum:
  id: DATUM-AXLE-FRONT
  kind: NAMED_AXIS
  view_id: SIDE
  coordinate_role: X_ORIGIN
  source_refs: [DIM-001]
  status: APPROVED
~~~

### 6.5 Constraint IR

Mỗi constraint có:

- stable id;
- kind;
- các entity/datum liên quan;
- giá trị hoặc quan hệ;
- unit và tolerance policy;
- source references;
- approval/provenance;
- solver status;
- residual;
- conflict set nếu có.

Ví dụ:

~~~yaml
constraint:
  id: CON-001
  kind: HORIZONTAL_DISTANCE
  from: DATUM-AXLE-FRONT
  to: DATUM-AXLE-REAR
  value: 4500
  unit: mm
  source_refs: [DIM-001]
  provenance: EXACT
  status: SATISFIED
  residual_mm: 0.0
~~~

### 6.6 Component và Entity Provenance

Ví dụ component cẩu dưới đây chỉ minh họa hợp đồng provenance và placement;
nó không giới hạn hệ thống vào thiết kế gắn cẩu.

~~~yaml
component:
  id: CMP-CRANE-001
  class: CRANE_ASSEMBLY
  source:
    library_item_id: VX_CRANE_MODEL_SIDE_R03
    revision: R03
    sha256: "EXAMPLE_COMPONENT_SHA256"
  placement:
    datum_ref: DATUM-CHASSIS-TOP
    constraints: [CON-021, CON-022]
  provenance: CONSTRAINED
  criticality: CRITICAL
~~~

### 6.7 Operation Plan cấp nghiệp vụ

LLM chỉ được tạo Operation Plan cấp nghiệp vụ. Ví dụ:

~~~yaml
operations:
  - op_id: OP-001
    operation: APPLY_DRAWING_PROFILE
    profile_id: VEHICLE_CONVERSION_V1
  - op_id: OP-002
    operation: CREATE_VIEW_FROM_SOLVED_MODEL
    view_id: SIDE
    solved_model_ref: SOLVED-SIDE-001
  - op_id: OP-003
    operation: PLACE_STANDARD_COMPONENT
    component_ref: CMP-CRANE-001
  - op_id: OP-004
    operation: GENERATE_NATIVE_ANNOTATION
    annotation_plan_ref: ANN-SIDE-001
  - op_id: OP-005
    operation: RENDER_AND_REGISTER_EVIDENCE
    affected_regions: [SIDE-R01, SIDE-R02]
~~~

Không mở draw_line/draw_arc làm giao diện chính cho AI. Primitive chỉ được dùng
nội bộ trong executor đã kiểm soát.

### 6.8 Region Verification Register

~~~yaml
region:
  region_id: SIDE-R02
  view_id: SIDE
  criticality: CRITICAL
  source_crop:
    source_id: SRC-001
    page: 1
    bbox: [100, 200, 600, 800]
    crop_hash: "EXAMPLE_SOURCE_CROP_SHA256"
  cad_crop:
    model_bbox_mm: [0, 0, 5000, 2500]
    layout: A1-01
    viewport_id: VP-SIDE
  expected_features:
    - chassis_outline
    - rear_axle_centerline
    - crane_attachment
    - hidden_lines
  dimension_refs: [DIM-001, DIM-014]
  entity_refs: [ENT-001, ENT-002]
  last_mutation_hash: "EXAMPLE_MUTATION_SHA256"
  last_render_hash: "EXAMPLE_RENDER_SHA256"
  checks:
    engineering_fidelity: PASSED
    visual_fidelity: PASSED
  status: VERIFIED
~~~

## 7. Quy trình end-to-end bắt buộc

### Giai đoạn A — Tiếp nhận và phân loại

1. Nhận yêu cầu, dữ liệu xe, DWG/DXF/PDF/ảnh và revision.
2. Hash toàn bộ source.
3. Phân loại bản vẽ và release profile.
4. Xác định dữ liệu authoritative và dữ liệu tham khảo.
5. Tạo danh sách thiếu/mâu thuẫn.

### Giai đoạn B — Tìm kiếm và tái sử dụng

1. Tìm trong kho CAD theo:
   - loại xe;
   - loại cải tạo;
   - chassis/cabin;
   - kích thước chính;
   - bố trí view;
   - block/component;
   - layer/style profile;
   - provenance và revision.
2. Xếp hạng kết quả.
3. Phân loại:
   - REUSABLE_STANDARD;
   - SOURCE_SPECIFIC;
   - LEGACY_COMPATIBILITY;
   - NEEDS_REVIEW;
   - DO_NOT_REUSE.
4. Chỉ copy component hoặc cấu trúc đã duyệt.
5. Gắn source_id, revision và transform cho mọi đối tượng tái sử dụng.

### Giai đoạn C — Drawing Initialization

1. Tạo Drawing Definition.
2. Chọn Drawing Profile, Domain Pack và DWT.
3. Lập Sheet/View/Viewport Plan.
4. Lập Datum và Annotation Plan.
5. Kiểm tra setup.
6. Vượt Drawing Initialization Gate.

### Giai đoạn D — Dimension-first

1. Tách view và source region sơ bộ.
2. Trích xuất dimension text cùng arrowhead, extension line và attachment.
3. Tạo Dimension IR và datum candidates.
4. Kỹ sư duyệt các observation quan trọng hoặc mơ hồ.
5. Tạo Constraint IR.
6. Giải hệ constraint.
7. Báo underconstraint, overconstraint và conflict set.
8. Không tạo authoritative geometry nếu model-critical DOF chưa xác định.

### Giai đoạn E — Lập kế hoạch và dựng hình

1. Tạo solved view model.
2. Chọn component/block chuẩn.
3. Tạo Operation Plan cấp nghiệp vụ.
4. Chạy static validation.
5. Thực thi trong bản vẽ disposable/draft.
6. Tạo geometry, annotation, hatch, block và Layout.
7. Mọi entity có provenance.

### Giai đoạn F — Render sau thao tác

Sau mỗi operation làm thay đổi hình học hoặc annotation:

1. Xác định affected views và affected regions.
2. Invalidate bằng chứng cũ của các region đó.
3. REGEN.
4. Render/chụp vùng CAD mới.
5. Gắn render hash với mutation hash.
6. Không được dùng ảnh CAD trước lần sửa cuối làm bằng chứng.

### Giai đoạn G — Kiểm tra từng vùng

Đối với từng region:

1. Mở source crop.
2. Mở CAD crop mới nhất.
3. So sánh đặt cạnh nhau.
4. Overlay nếu cần phát hiện khác biệt hình dáng.
5. Kiểm tra engineering_fidelity.
6. Kiểm tra visual_fidelity.
7. Nếu sai, lập Repair Plan cấp nghiệp vụ.
8. Sửa, render lại, đo lại và kiểm tra lại chính region đó.
9. Chỉ chuyển VERIFIED khi bằng chứng sau lần sửa cuối đạt.

### Giai đoạn H — Kiểm tra toàn cục

1. Kiểm tra quan hệ giữa các view.
2. Kiểm tra shared datums.
3. Đo ngược driving dimensions.
4. Kiểm tra dimension chain, baseline, ordinate và tổng derived.
5. Kiểm tra layer, BYLAYER, lineweight, linetype và plot.
6. Kiểm tra text/font, dimension/hatch/block native.
7. Plot preview toàn tờ.
8. Kiểm tra coverage không bỏ sót vùng.

### Giai đoạn I — Review và phát hành

1. Xuất Verification Report.
2. Xuất Release Manifest.
3. Review read-only trong AutoCAD Mechanical 2027.
4. Nếu sửa production drawing: backup + approval.
5. Thực thi sửa.
6. Review lần hai.
7. Chỉ save khi Release Gate đạt.

## 8. Hai loại fidelity không được trộn

### 8.1 Engineering fidelity

Dùng dimension, datum và constraint để kiểm tra:

- khoảng cách;
- tọa độ;
- góc;
- bán kính/đường kính;
- quan hệ hình học;
- attachment;
- chain closure;
- cross-view consistency.

Engineering fidelity không dùng pixel để điều chỉnh model coordinates.

### 8.2 Visual fidelity

Dùng PDF/ảnh để kiểm tra:

- topology;
- hình dáng;
- đường cong không có dimension;
- attachment trực quan;
- nét khuất;
- đường tâm;
- hatch;
- chi tiết trình bày;
- vị trí tương đối;
- chi tiết bị thiếu hoặc thừa.

Overlay chỉ là công cụ phát hiện khác biệt. Nó không có quyền bẻ hình học kỹ
thuật để khớp pixel.

## 9. Kiểm tra vùng và coverage

### 9.1 Cách tạo region

Mỗi view được chia theo hai lớp:

1. Semantic regions:
   - cụm cẩu;
   - cabin;
   - chassis;
   - trục/bánh;
   - thùng hàng;
   - mặt cắt;
   - dimension cluster;
   - title block hoặc bảng.
2. Coverage grid:
   - lưới phủ toàn bộ view để chứng minh không có khoảng trống chưa kiểm tra.

Region CRITICAL gồm:

- vùng có kích thước điều khiển;
- vị trí lắp/attachment;
- mặt cắt kết cấu;
- component tái sử dụng;
- vùng có thay đổi thiết kế;
- vùng có cảnh báo hoặc confidence thấp;
- vùng đã từng FAILED.

### 9.2 Vòng đời region

~~~mermaid
stateDiagram-v2
    [*] --> PENDING
    PENDING --> CHECKING
    CHECKING --> VERIFIED
    CHECKING --> FAILED
    CHECKING --> NEEDS_REVIEW
    FAILED --> REPAIRED
    REPAIRED --> CHECKING
    VERIFIED --> STALE: affected mutation
    STALE --> CHECKING
~~~

### 9.3 Điều kiện một region được VERIFIED

- source crop tồn tại;
- CAD render tồn tại;
- render được tạo sau mutation cuối;
- expected features đã kiểm;
- dimension refs đã đo nếu có;
- engineering_fidelity đạt;
- visual_fidelity đạt;
- không có unresolved critical item;
- người/agent kiểm tra và thời điểm được ghi lại.

### 9.4 Điều kiện một view được VERIFIED

- 100% region CRITICAL đã kiểm tra;
- không có CRITICAL region FAILED hoặc NEEDS_REVIEW;
- mỗi region VERIFIED có ảnh CAD sau lần sửa cuối;
- mọi driving dimension đạt residual/tolerance;
- kiểm tra toàn cảnh đạt;
- coverage report chứng minh không bỏ sót vùng.

### 9.5 Local Visual Verification Gate

Gate này nằm sau dựng/sửa CAD và trước kiểm tra phát hành toàn cục. Gate đạt khi:

- tất cả view bắt buộc đã có Region Verification Register;
- toàn bộ CRITICAL region trong các view đó đã VERIFIED;
- visual evidence không stale so với mutation cuối;
- engineering_fidelity và visual_fidelity đều đạt;
- mọi Repair Plan đã được đóng bằng một vòng sửa → render mới → đo lại →
  kiểm tra lại;
- coverage report không có vùng trống;
- không còn source_visual_conflict chưa được kỹ sư xử lý.

Gate này không thay Release Gate. Nó chứng minh mọi vùng đã được nhìn lại; Release
Gate còn kiểm tra tính nhất quán toàn bản vẽ, native/editable entities, plot,
approval và an toàn production.

## 10. Audit kho DWG cũ

### 10.1 Bài học từ BVTL.dwg

Các script bbox/inspect có thể chứng minh:

- số lượng entity;
- loại entity;
- layer;
- color và linetype;
- LTSCALE/DIMSCALE cơ bản;
- DIMSTYLE;
- TEXTSTYLE/font khai báo;
- block table và số INSERT;
- bounding box theo layer.

Nhưng đó mới là structural inventory, chưa phải engineering audit. Không được
từ các con số này suy ra rằng:

- entity dùng BYLAYER đúng;
- lineweight đúng;
- Model Space vẽ 1:1;
- viewport và plot scale đúng;
- block nào là bản lề, móc hoặc tay nắm;
- DIMSTYLE dùng đúng từng tỷ lệ;
- HATCH associative và boundary hợp lệ;
- font substitution không làm lệch bố cục;
- bản vẽ có thể dùng nguyên trạng làm template.

### 10.2 Drawing Standard Extraction Audit

Đối với mỗi DWG ứng viên, audit phải xuất:

#### Drawing variables

- INSUNITS;
- MEASUREMENT;
- LTSCALE;
- CELTSCALE;
- PSLTSCALE;
- MSLTSCALE;
- DIMASSOC;
- ANNOALLVISIBLE;
- current layer/style;
- extents sau REGEN.

#### Model/Layout/Viewport

- entity theo Model/Paper Space;
- layout name;
- page setup;
- paper size;
- plot area và plot scale;
- viewport scale;
- viewport lock;
- Model Space 1:1 hay không.

#### Layer audit

- name;
- color;
- linetype;
- lineweight;
- transparency;
- plot/no-plot;
- frozen/locked;
- entity count;
- tỷ lệ BYLAYER;
- color/linetype/lineweight override;
- duplicate hoặc gần trùng.

#### Style audit

- DIMSTYLE cùng các biến quan trọng;
- TEXTSTYLE, font gốc, bigfont và substitution;
- MLEADERSTYLE;
- TABLESTYLE;
- hatch pattern/scale;
- plot style.

#### Block audit

- block definition và INSERT count tách riêng;
- base point;
- units;
- layer;
- attributes;
- nested blocks;
- dynamic properties;
- anonymous blocks;
- exploded duplicates;
- hình preview hoặc render để xác định công dụng.

#### Dimension audit

- native DIMENSION;
- exploded dimension;
- DIMASSOC;
- text/value override;
- attachment;
- DimStyle usage theo scale;
- orphan hoặc non-associative dimensions.

#### Hatch audit

- pattern;
- scale;
- angle;
- associative;
- closed/valid boundary;
- duplicate/overlap.

#### Phân loại kết quả

- REUSABLE_STANDARD;
- SOURCE_SPECIFIC;
- LEGACY_COMPATIBILITY;
- NEEDS_REVIEW;
- DO_NOT_REUSE.

Chỉ thành phần REUSABLE_STANDARD đã được kỹ sư duyệt mới đi vào DWT,
Drawing Profile hoặc Block Library.

### 10.3 Chính sách font

Tách hai profile:

1. LEGACY_COMPATIBILITY:
   - giữ TextStyle và mapping font cần thiết để mở/tái tạo đúng bản cũ;
   - ghi rõ font thiếu và font thay thế;
   - không đổi hàng loạt sang Arial.
2. NEW_DRAWING:
   - dùng font TTF/SHX đã được duyệt;
   - kiểm thử tiếng Việt, chiều rộng chữ, ký hiệu kỹ thuật và plot;
   - chỉ áp dụng khi profile/template đã được chủ dự án duyệt.

## 11. Kho block và component chuẩn

### 11.1 Quy tắc

- mm, 1:1;
- base point cố định và có ý nghĩa;
- hướng +X thống nhất;
- layer/profile rõ;
- không override tùy tiện;
- metadata, revision và provenance;
- preview;
- input parameter và điều kiện áp dụng;
- test insertion/explode policy;
- không tạo một block “all-in-one” chứa mọi biến thể.

Tên gợi ý:

    VX_[GROUP]_[MODEL]_[VIEW]_[REV]

Ví dụ:

    VX_CRANE_KS1256_SIDE_R03

Dynamic block chỉ dùng cho biến thiên có giới hạn và đã được kiểm thử. Các cụm
phức tạp nên dùng Mechanical Structure, Custom Content Library hoặc component
definition phù hợp.

### 11.2 Tái sử dụng an toàn

Một component chỉ được tái sử dụng nếu:

- loại và revision đúng;
- unit đúng;
- datum/base point tương thích;
- parameter nằm trong miền cho phép;
- source hash/provenance còn hợp lệ;
- không có unresolved override;
- render và measurement sau placement đạt.

## 12. AutoCAD Mechanical 2027 integration

### 12.1 Công nghệ

- AutoCAD Mechanical 2027;
- Visual Studio 2026;
- .NET 10, target net10.0-windows, x64;
- ObjectARX SDK 2027;
- AcCoreMgd.dll, AcDbMgd.dll, AcMgd.dll với Copy Local = False;
- Mechanical SDK là adapter riêng, chỉ thêm khi use case thực sự cần.

Khoảng 80–90% chức năng nên dùng AutoCAD .NET API chuẩn; phần Mechanical chỉ
làm adapter 10–20% cho chức năng đặc thù.

### 12.2 Vai trò plugin

CadAgent.AutoCAD2027 là AutoCAD-side dispatcher, không thay Python pipeline.

Giai đoạn đầu chỉ cần các lệnh:

- CADAGENT_HEALTH;
- CADAGENT_DISPATCH;
- CADAGENT_REVIEW;
- CADAGENT_CLOSE_DISPOSABLE.

CADAGENT_REPAIR chỉ bật sau khi Operation Plan, validation, render feedback và
approval boundary đã ổn định.

### 12.3 Hợp đồng dispatcher

Mỗi request có:

- protocol version;
- request_id;
- run_id;
- drawing target;
- source/current drawing hash;
- operation plan hash;
- read-only/draft/production mode;
- timeout;
- approval token khi cần;
- expected output/evidence.

Mỗi response có:

- command status;
- precondition checks;
- entity/change summary;
- affected views/regions;
- measurement results;
- render artifacts;
- warnings/errors;
- resulting drawing hash;
- save status.

## 13. Trạng thái và lỗi chuẩn

### 13.1 Trạng thái run

~~~mermaid
stateDiagram-v2
    [*] --> INGESTED
    INGESTED --> SETUP_PENDING
    SETUP_PENDING --> SETUP_VERIFIED
    SETUP_VERIFIED --> DIMENSIONS_PENDING
    DIMENSIONS_PENDING --> CONSTRAINTS_SOLVED
    CONSTRAINTS_SOLVED --> PLAN_VALIDATED
    PLAN_VALIDATED --> EXECUTED
    EXECUTED --> REGION_REVIEW
    REGION_REVIEW --> RELEASE_READY
    RELEASE_READY --> RELEASED
~~~

Mọi trạng thái có thể chuyển sang NEEDS_REVIEW, BLOCKED hoặc FAILED khi vi phạm
cổng tương ứng.

### 13.2 Mã lỗi tối thiểu

- source_changed;
- source_visual_conflict;
- dimension_conflict;
- dimension_unattached;
- datum_unresolved;
- underconstrained_geometry;
- overconstrained_geometry;
- setup_incomplete;
- profile_missing;
- profile_hash_mismatch;
- template_hash_mismatch;
- unsupported_operation;
- drawing_target_mismatch;
- stale_render_evidence;
- critical_region_failed;
- critical_region_needs_review;
- coverage_incomplete;
- production_backup_missing;
- approval_missing;
- second_review_missing;
- font_substitution_risk;
- non_native_annotation;
- viewport_scale_mismatch.

## 14. Roadmap M0–M8

Đây là roadmap tổng hợp chính thức của thiết kế này. Các nhánh P0–P3 trong tài
liệu Dimension-First cũ được đặt bên trong các mốc tương ứng, không chạy như
một roadmap cạnh tranh.

### M0 — Baseline, contracts và safety

Phạm vi:

- kiểm kê repo và test hiện có;
- đóng băng các ranh giới đang hoạt động;
- Source/Run/Approval/Provenance Manifest;
- hash và checkpoint;
- disposable/read-only mode;
- backup/approval/second-review policy;
- lỗi và state machine chuẩn.

Đạt khi:

- một run có thể resume/reject đúng theo source hash;
- không có đường chạy nào sửa production drawing mà thiếu backup và approval;
- test baseline được ghi nhận.

### M1 — AutoCAD .NET transport và dispatcher an toàn

Phạm vi:

- CadAgent.AutoCAD2027;
- dotnet_ipc backend song song với File IPC;
- CADAGENT_HEALTH, DISPATCH, REVIEW, CLOSE_DISPOSABLE;
- inspect, zoom, measure, render và change summary;
- chưa thêm CADAGENT_REPAIR sản xuất.

Đạt khi:

- round-trip thật với AutoCAD Mechanical 2027 ổn định;
- request/response có hash và idempotency;
- disposable drawing đóng an toàn;
- không ảnh hưởng bản vẽ đang làm của người dùng.

### M2 — Drawing standards và Drawing Initialization Gate

Phạm vi:

- Drawing Definition;
- Drawing/Profile/View/Annotation schema;
- VX_MECHANICAL_2027_TEMPLATE.dwt;
- layer, style, layout, viewport, plot profile;
- Domain Pack AUTOMOTIVE_CONVERSION_V1 bản đầu;
- audit BVTL và bộ 10 DWG chuẩn ứng viên;
- font policy legacy/new.

Đạt khi:

- AI không thể tạo entity trước SETUP_VERIFIED;
- DWT/profile có revision/hash;
- một bản vẽ mẫu mở đúng layer/style/layout/plot;
- chỉ thành phần DWG đã audit được tái sử dụng.

### M3 — Dimension IR, Datum IR, Constraint IR và solver

Phạm vi:

- P0 contracts and evidence của thiết kế Dimension-First;
- Dimension IR và attachment;
- datum candidates;
- Constraint IR;
- solver, residual, conflict set;
- approval register;
- fixture MẠN private/manual register làm regression đầu tiên.

Đạt khi:

- driving dimension đều có value, unit, kind, attachment, view và approval;
- chain/baseline/ordinate đóng;
- under/overconstraint được phát hiện;
- không dùng mm/px để tạo authoritative coordinates.

### M4 — Deterministic generation và render feedback

Phạm vi:

- P1 representative vertical slice;
- solved geometry đến native CAD entities;
- native DIMENSION/HATCH/BLOCK;
- Operation Plan cấp nghiệp vụ;
- render/chụp lại sau mọi thao tác tạo hoặc sửa;
- affected-region invalidation;
- measurement round-trip.

Đạt khi:

- một view đại diện được tạo từ dimension/constraint;
- output editable trong AutoCAD Mechanical 2027;
- mọi mutation có render mới và change summary;
- ảnh cũ không thể được dùng làm bằng chứng sau sửa.

### M5 — Legacy knowledge, similarity và reusable operations

Phạm vi:

- analyzer DWG/DXF;
- JSON/SQLite knowledge base;
- metadata và geometry features;
- similarity ranking;
- block/component registry;
- business-level operations cho cải tạo ô tô;
- provenance và parameter-range validation.

Đạt khi:

- tìm được bản/cụm tương tự với lý do xếp hạng;
- không copy mù cả DWG;
- component tái sử dụng có revision/hash/datum;
- operation cấp nghiệp vụ thay thế primitive API cho LLM.

### M6 — View segmentation và Source/CAD Region Mapping

Phạm vi:

- P2 additional views and cross-view contracts;
- tách source thành view;
- semantic region + coverage grid;
- source crop;
- CAD model/layout crop;
- mapping view/region/entity/dimension;
- cross-view shared datum checks.

Đạt khi:

- mọi view có source region và technical coordinate frame;
- mọi CRITICAL region có source crop và expected features;
- coverage grid phủ toàn bộ view;
- shared datum chỉ tồn tại khi có bằng chứng/approval.

### M7 — Domain-complete reconstruction và repair loop

Phạm vi:

- nhiều view của một bộ bản vẽ cải tạo ô tô được chọn từ cấu hình công việc;
- chứng minh kiến trúc không phụ thuộc vào riêng loại thùng, thiết bị hoặc cặp
  trạng thái trước/sau của ca pilot;
- annotation plan hoàn chỉnh;
- line/hatch/block/text/font fidelity;
- P3 advanced fidelity;
- CADAGENT_REPAIR ở draft/disposable mode;
- repair plan cấp nghiệp vụ;
- kiểm tra layer/style/layout/plot.

Đạt khi:

- một bộ bản vẽ đại diện chạy end-to-end;
- có thể khai báo thêm ít nhất một cấu hình cải tạo khác qua profile/domain
  pack/component registry mà không tạo nhánh xử lý đặc thù trong lõi;
- lỗi cục bộ tạo Repair Plan, sửa, render và đo lại;
- dimension và entity vẫn native/editable;
- không có critical unresolved item.

### M8 — Region Verification Register và Authoritative Release Gate

Phạm vi:

- Region Verification Register;
- engineering_fidelity;
- visual_fidelity;
- side-by-side và overlay;
- stale evidence detection;
- coverage report;
- global sheet review;
- production backup, approval, second review và release manifest.

Đạt khi:

- 100% CRITICAL region VERIFIED;
- không còn FAILED/NEEDS_REVIEW critical region;
- mọi driving dimension đo ngược đạt;
- mọi region có ảnh CAD sau lần sửa cuối;
- coverage hoàn chỉnh;
- AutoCAD/plot preview đạt;
- chỉ khi đó mới được báo RELEASED hoặc cho phép production save.

## 15. Ánh xạ P0–P3 cũ vào M0–M8

| Nhánh cũ | Vị trí mới |
|---|---|
| P0 contracts and evidence | M0 + phần hợp đồng của M3 |
| P1 representative dimension-first slice | M3 + M4 |
| P2 additional views/cross-view | M6 |
| P3 advanced fidelity | M7 |

Không xóa pixel-first path ngay. Nó được giữ ở chế độ DRAFT/REFERENCE cho đến
khi dimension-first path có đủ staging, review và safety evidence tương đương.

## 16. Chiến lược kiểm thử

### 16.1 Unit tests

- schema và validation;
- Dimension IR parsing;
- attachment resolution;
- unit conversion;
- datum/view mapping;
- provenance transition;
- operation validation;
- region invalidation.

### 16.2 Solver tests

- exact distance/angle/radius;
- chain closure;
- baseline/ordinate;
- underconstraint;
- overconstraint;
- conflicting dimensions;
- residual/tolerance;
- cross-view shared datum.

### 16.3 Golden fixtures

- fixture MẠN private cho repeated axes/levels;
- fixture automotive conversion cho side/top/rear;
- expected coordinates và native entity types;
- không đưa dữ liệu nhạy cảm hoặc số riêng của khách hàng vào production logic.

### 16.4 DWG/DXF tests

- mở lại file;
- entity native;
- layer/BYLAYER;
- block insert/definition;
- dimension association;
- hatch association;
- style/layout/viewport;
- font substitution report;
- model extents và units.

### 16.5 AutoCAD integration tests

- health/dispatch/review;
- disposable lifecycle;
- document activation;
- read-only guarantee;
- render after mutation;
- measurement round-trip;
- timeout/retry/idempotency;
- production guard.

### 16.6 Visual/region tests

- source crop và CAD crop đúng view;
- render hash mới hơn mutation hash;
- overlay không thay model coordinates;
- region state transitions;
- critical coverage = 100%;
- global sheet preview.

## 17. Chỉ số chất lượng

Không dùng một điểm pixel similarity duy nhất làm chỉ số thành công.

Các KPI phù hợp:

- driving_dimension_pass_rate;
- max_dimension_residual_mm;
- constraint_satisfied_rate;
- critical_region_verified_rate;
- total_region_coverage_rate;
- stale_evidence_count;
- unresolved_model_critical_count;
- native_dimension_rate;
- native_block_reuse_rate;
- bylayer_compliance_rate;
- viewport_scale_pass_rate;
- reusable_component_hit_rate;
- human_correction_count;
- production_guard_violation_count;
- release_without_evidence_count, bắt buộc bằng 0.

## 18. Release Gate

Một run chỉ được RELEASE_READY khi:

- Drawing Initialization Gate đạt;
- source/profile/template hashes hợp lệ;
- mọi driving dimension được duyệt và đo ngược đạt;
- mọi model-critical DOF exact hoặc constrained;
- không có dimension_conflict;
- không có critical ESTIMATED/UNRESOLVED entity;
- dimension chain và cross-view checks đạt;
- mọi CRITICAL region VERIFIED;
- mọi region VERIFIED có render sau mutation cuối;
- coverage đạt;
- native/editable checks đạt;
- layer/style/layout/viewport/plot checks đạt;
- review read-only trong AutoCAD Mechanical đạt.

Production save chỉ được phép thêm khi:

- đích sửa đã xác định chính xác;
- backup đã tạo và kiểm tra;
- kỹ sư phê duyệt Operation Plan;
- sửa xong đã render/measure lại;
- review lần hai đạt;
- Release Manifest được ghi.

## 19. Bộ đầu ra của mỗi run

Mỗi run phải để lại:

1. Source Manifest.
2. Drawing Definition.
3. Drawing Setup Plan và checklist.
4. Similarity/Reuse Report.
5. Dimension Register.
6. Datum/View Register.
7. Constraint Report và residuals.
8. Solved Model hash.
9. Operation Plan.
10. Change Summary.
11. CAD output draft.
12. Render artifacts.
13. Region Verification Register.
14. Coverage Report.
15. Global Review Report.
16. Release Manifest hoặc Blocker Report.

## 20. Prompt chỉ đạo hoàn chỉnh cho PO/CAD Agent

Phần dưới đây có thể dùng làm chỉ dẫn cấp cao. Nó không thay schema, validator,
test và code gate; các quy tắc quan trọng phải được cưỡng chế bằng phần mềm.

~~~text
Bạn là PO và kỹ sư điều phối của dự án cad-agent cho AutoCAD Mechanical 2027.

MỤC TIÊU
Xây CAD Agent theo hướng dimension-first, image-guided và profile-controlled.
Hệ thống phải tạo bản vẽ kỹ thuật native, chỉnh sửa được, có provenance, có
bằng chứng kiểm tra từng vùng và không được báo hoàn thành khi chỉ mới dựng
hình học sơ bộ.

PHẠM VI SẢN PHẨM
Hệ thống phục vụ nhiều dạng thiết kế cải tạo ô tô. Không định nghĩa sản phẩm
bằng một ví dụ như xe tải có mui chuyển thành xe gắn cẩu và thùng lửng. Nếu ca
đó được chọn làm pilot thì chỉ dùng để kiểm chứng hợp đồng tổng quát. Không
hard-code loại xe, loại thùng, thiết bị chuyên dùng hoặc cặp trạng thái
trước/sau vào kiến trúc lõi. Ca cải tạo mới phải đi qua cấu hình, Drawing
Definition, Domain Pack, Component Registry và dữ liệu kỹ thuật đã duyệt.

NGUYÊN TẮC NGUỒN DỮ LIỆU
1. Kích thước đã duyệt là nguồn có thẩm quyền cao nhất.
2. Sau đó là datum và quan hệ hình học đã duyệt.
3. Sau đó là block/chi tiết chuẩn có revision và provenance phù hợp.
4. PDF/ảnh dùng cho topology, view, attachment, đường cong, nét khuất, hatch và
   kiểm tra trực quan.
5. Pixel chỉ là ước lượng. Không dùng mm/px để thay đổi tọa độ kỹ thuật.
6. Nếu nguồn authoritative mâu thuẫn, dừng với dimension_conflict.
7. Nếu ảnh mâu thuẫn với kích thước authoritative, giữ kích thước và ghi
   source_visual_conflict.

KHỞI TẠO BẢN VẼ
Không được tạo entity trước khi:
- xác định domain, loại và mục đích bản vẽ;
- chọn Drawing Profile, Domain Pack và DWT đúng revision;
- xác định Model Space mm, 1:1;
- lập sheet/view/viewport plan;
- kiểm tra layer, linetype, lineweight, TextStyle, DimStyle, MLeaderStyle,
  hatch, plotstyle và title block;
- khai báo datum, view coordinate frame và annotation plan;
- tạo Drawing Setup Checklist;
- trạng thái đạt SETUP_VERIFIED.

DIMENSION-FIRST
Mỗi dimension phải có value, unit, kind, view, from/to attachment, extension
geometry, role, source, confidence, status và approval. Một con số không có
attachment là UNRESOLVED.

Chỉ tạo Constraint IR từ dimension/datum/relation đã duyệt. Solver phải báo
underconstraint, overconstraint, residual và conflict set. Không được lấy pixel
để lấp một model-critical DOF mà vẫn gắn nhãn exact.

KHO CAD VÀ TÁI SỬ DỤNG
Tìm bản vẽ/cụm tương tự trước khi dựng mới. Không copy mù toàn bộ DWG. Mọi
layer, style, block, component hoặc detail lấy từ bản cũ phải qua audit và được
phân loại REUSABLE_STANDARD, SOURCE_SPECIFIC, LEGACY_COMPATIBILITY,
NEEDS_REVIEW hoặc DO_NOT_REUSE.

LLM chỉ lập Operation Plan cấp nghiệp vụ. Không mở một tập lệnh draw_line,
draw_arc cấp thấp làm giao diện chính. Mọi component tái sử dụng phải có
revision, hash, base point/datum, miền tham số và provenance.

THỰC THI AUTOCAD
Giữ Python pipeline và mcp_integration_lib. CadAgent.AutoCAD2027 là dispatcher
phía AutoCAD, không phải decision engine. Dùng File IPC/dotnet IPC cho inspect,
dispatch, zoom, measure, render và review.

Mặc định chạy read-only hoặc disposable. Không tắt SECURELOAD. Không sửa hoặc
lưu production drawing nếu chưa có backup, target rõ ràng, approval và review
lần hai.

ENTITY VÀ TRÌNH BÀY
Ưu tiên entity native: LINE/ARC/CIRCLE/LWPOLYLINE, BLOCK/INSERT, HATCH,
DIMENSION, TEXT/MTEXT. Dùng layer, linetype và lineweight theo profile/BYLAYER.
Model Space vẽ 1:1; tỷ lệ đặt ở viewport/Layout. Không explode dimension/block
hoặc truy vết thành hàng nghìn đoạn rời nếu không có lý do được ghi nhận.

RENDER VÀ KIỂM TRA VÙNG
Sau mọi thao tác tạo hoặc sửa:
1. Xác định affected views/regions.
2. Invalidate bằng chứng cũ.
3. REGEN và render/chụp vùng CAD mới.
4. Gắn render hash với mutation hash.
5. So sánh source crop và CAD crop.
6. Kiểm tra engineering_fidelity bằng dimension/datum/constraint.
7. Kiểm tra visual_fidelity bằng PDF/ảnh.
8. Nếu sai, tạo Repair Plan cấp nghiệp vụ, sửa, render lại và đo lại.

Không được dùng ảnh CAD có trước lần sửa cuối làm bằng chứng.

Mỗi view phải có semantic regions và coverage grid. Region CRITICAL gồm vùng
có driving dimension, attachment, thay đổi thiết kế, component tái sử dụng,
mặt cắt, confidence thấp hoặc lỗi trước đó.

Một view chỉ VERIFIED khi:
- 100% CRITICAL region đã kiểm;
- không còn CRITICAL FAILED/NEEDS_REVIEW;
- mọi region đạt có CAD render sau lần sửa cuối;
- mọi driving dimension đo ngược đạt;
- kiểm tra toàn cảnh đạt;
- coverage chứng minh không bỏ sót vùng.

PHÁT HÀNH
Không dùng từ “xong”, “hoàn thành”, “verified” hoặc “released” nếu thiếu bằng
chứng. Trước khi phát hành phải kiểm tra:
- setup;
- source/profile/template hashes;
- dimension residuals;
- constraint closure;
- provenance;
- layer/style/layout/viewport/plot;
- native/editable entities;
- region register;
- coverage;
- AutoCAD read-only review.

Nếu còn thiếu dữ liệu hoặc phê duyệt, xuất Blocker Report với mã lỗi, affected
view/region, bằng chứng hiện có, dữ liệu cần bổ sung và hành động tiếp theo.

ROADMAP
Thực hiện theo M0–M8:
M0 contracts/safety;
M1 .NET dispatcher;
M2 drawing standards/setup gate;
M3 Dimension/Datum/Constraint IR và solver;
M4 deterministic generation + render feedback;
M5 legacy knowledge/similarity/reusable operations;
M6 view/region mapping;
M7 domain-complete reconstruction + repair loop;
M8 verification register + release gate.

Không nhảy thẳng đến vẽ xe hoàn chỉnh khi gate và bằng chứng của mốc trước chưa
đạt. Mỗi mốc phải có test, fixture, acceptance evidence và báo cáo chênh lệch
so với thiết kế này.

Trong mọi mốc, kiểm kê và tái sử dụng phần đã có trước khi viết mới. Không tạo
pipeline, contract hoặc executor thứ hai nếu ranh giới hiện tại có thể mở rộng
bằng một thay đổi nhỏ có test bảo vệ.
~~~

## 21. Mẫu giao việc cho từng milestone

Mỗi task của PO phải có:

~~~yaml
task:
  id: M4-T03
  milestone: M4
  objective: "Render affected CAD regions after every mutation"
  in_scope:
    - mutation-to-region mapping
    - regen and render
    - render hash
    - stale evidence invalidation
  out_of_scope:
    - production save
    - full M8 release gate
  inputs:
    - operation_plan_schema
    - region_schema
  outputs:
    - render_artifact
    - change_summary
    - updated_region_register
  preconditions:
    - SETUP_VERIFIED
    - PLAN_VALIDATED
  acceptance_tests:
    - "Mutation invalidates old region evidence"
    - "New render is linked to the mutation hash"
    - "Unchanged regions retain valid evidence"
  safety:
    mode: DISPOSABLE
    production_write: false
  evidence_required:
    - test_output
    - sample_manifest
    - before_after_render
~~~

PO không được giao task mơ hồ kiểu “làm AI vẽ chính xác hơn”. Mỗi task phải chỉ
rõ contract, input, output, gate, test và bằng chứng.

## 22. Definition of Done của thiết kế

Thiết kế này được coi là đã duyệt khi chủ dự án xác nhận:

- hướng dimension-first/image-guided/profile-controlled;
- kiến trúc và ranh giới module;
- Drawing Initialization Gate;
- Local Visual Verification Gate;
- roadmap M0–M8;
- DWT/profile/domain-pack policy;
- kho CAD audit/reuse policy;
- production safety boundary;
- bộ hợp đồng và đầu ra bắt buộc.

Sau khi thiết kế được duyệt, bước tiếp theo là viết Implementation Plan theo
từng milestone, bắt đầu từ trạng thái thật của repo và không viết lại các phần
đã có/đã kiểm thử.
