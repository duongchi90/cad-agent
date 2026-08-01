# AutoCAD .NET Plugin — Phương án A

**Ngày phê duyệt:** 2026-08-01  
**Phạm vi hỗ trợ:** Windows, Python 3.11, AutoCAD Mechanical 2027, .NET 10, x64  
**Trạng thái:** implemented and integrated into `main`; managed disposable smoke verified

**Cập nhật:** bổ sung ranh giới môi trường SDK và Mechanical theo yêu cầu ngày 2026-08-01.

## Phân tách môi trường và mã nguồn

Hai việc sau được quản lý riêng:

1. Chuẩn hóa máy phát triển: Visual Studio 2026, .NET 10 SDK, workload `.NET desktop development`, ObjectARX SDK 2027 và tài liệu/SDK AutoCAD Mechanical 2027 được cài bên ngoài repository.
2. Mã nguồn repository: chỉ chứa project Managed .NET, hợp đồng IPC, logic kiểm thử và cấu hình mẫu; không chứa source/headers/libs/COM type libraries của Autodesk.

Máy hiện tại đã có .NET SDK 10.0.301, Visual Studio Community/Build Tools 2026 và AutoCAD Mechanical 2027. Nếu ObjectARX SDK chưa có ở máy, build có thể dùng ba DLL tương ứng từ thư mục AutoCAD đã cài; khi SDK được cài, cấu hình local sẽ ưu tiên bản trong `$(ArxSdkDir)\inc`.

Repository sẽ track `Directory.Build.props.example` nhưng ignore `Directory.Build.props` thật. File local được phép đặt đường dẫn riêng cho `AcadDir` và `ArxSdkDir`; không ghi cứng đường dẫn cá nhân vào project hoặc commit.

## Mục tiêu

Thêm một plugin .NET `CadAgent.AutoCAD2027` vào cùng repository `cad-agent`, nằm song song với pipeline Python và File IPC dispatcher AutoLISP hiện tại. Plugin tạo một backend AutoCAD có thể kiểm thử độc lập qua JSON/File IPC mà không làm thay đổi hoặc thay thế dispatcher đã được kiểm chứng.

Lát cắt đầu tiên phải thực hiện được:

```text
Python dotnet_ipc backend
  -> request JSON
  -> CADAGENT_DISPATCH
  -> CadAgent.AutoCAD2027
  -> result JSON
```

## Không thuộc phạm vi

- Không chép source hoặc VSIX của `AutoCAD-Net-Wizards` vào repository.
- Không thay đổi các package nhận dạng ảnh, Primitive IR, Semantic IR hoặc DXF Builder.
- Không thay thế `mcp_dispatch.lsp` và không đổi protocol `autocad_mcp_cmd_*` hiện tại.
- Không chuyển ngay sang named pipe, HTTP hoặc tự động NETLOAD plugin.
- Không thêm chức năng vẽ cabin, chassis, cẩu, thùng xe.
- Không triển khai repair hoặc ghi sửa bản vẽ sản xuất trong lát cắt này.

## Kiến trúc

```text
cad_agent / mcp_integration_lib
        |
        | contracts/autocad-ipc/*.json
        v
CADAGENT_DISPATCH trong AutoCAD
        |
        v
CadAgent.AutoCAD2027.dll
        |
        v
AutoCAD Mechanical 2027 active document
```

`mcp_integration_lib` giữ nguyên `FileIPCLiveMCPClient` và dispatcher cũ. Backend mới `dotnet_ipc` dùng namespace/file prefix riêng để không xóa hoặc cạnh tranh với request của dispatcher cũ. Plugin chỉ xử lý request có schema version và operation được hỗ trợ.

Project C# nằm tại:

```text
autocad_plugin/
├── CadAgent.AutoCAD2027.sln
├── CadAgent.AutoCAD2027/
│   ├── CadAgent.AutoCAD2027.csproj
│   ├── Commands/
│   ├── Drawing/
│   ├── Ipc/
│   ├── Review/
│   └── Repair/
└── CadAgent.AutoCAD2027.Tests/
```

Project chính có `TargetFramework=net10.0-windows`, `PlatformTarget=x64`, `OutputType=Library`, `Nullable=enable`, `ImplicitUsings=enable`, và không thêm suffix framework/runtime vào output path. Ba reference AutoCAD là `AcCoreMgd.dll`, `AcDbMgd.dll`, `AcMgd.dll`, lấy ưu tiên từ `$(ArxSdkDir)\inc` và fallback về `$(AcadDir)`; cả ba đặt `Private=false`/`Copy Local=false`. Không tham chiếu AEC/Civil 3D SDK.

`CadAgent.AutoCAD2027.csproj` chỉ khai báo property mặc định an toàn khi các path local chưa được cấu hình; `Directory.Build.props.example` là nơi ghi ví dụ `AcadDir=C:\Program Files\Autodesk\AutoCAD 2027` và `ArxSdkDir=C:\Autodesk\ObjectARX 2027`. Không thêm `Directory.Build.props` thật vào Git.

## Hợp đồng JSON

Request tối thiểu:

```json
{
  "request_id": "12-character-or-longer-id",
  "schema_version": "1.0",
  "operation": "health",
  "drawing_full_path": "C:\\temp\\sample.dxf",
  "drawing_sha256": null,
  "parameters": {},
  "approval": null
}
```

Result tối thiểu:

```json
{
  "request_id": "same-id",
  "success": true,
  "operation": "health",
  "drawing_full_path": "C:\\temp\\sample.dxf",
  "changed": false,
  "entity_handles": [],
  "warnings": [],
  "errors": [],
  "started_at": "2026-08-01T00:00:00Z",
  "completed_at": "2026-08-01T00:00:00Z",
  "payload": {}
}
```

`drawing_full_path` là đường dẫn tuyệt đối. Với `health`, request có thể truyền `null` để hỏi document hiện tại; với `review` và `close_disposable`, plugin bắt buộc xác minh đường dẫn chuẩn hóa khớp document đang active. `drawing_sha256` chỉ là điều kiện kiểm tra khi operation yêu cầu hash; nó không được dùng để cấp quyền repair ở lát cắt này.

Các operation được phép trong lát cắt đầu:

- `health`: đọc trạng thái plugin, AutoCAD host, document active, IPC directory và quyền đọc/ghi IPC.
- `review`: đọc entity theo danh sách handle trong `parameters.handles`, trả type, layer và hình học cơ bản; không sửa document.
- `close_disposable`: chỉ đóng document khi `parameters.disposable=true` và `parameters.save_changes=false`; luôn đóng không lưu.

Operation khác trả result thất bại, không gọi transaction sửa đổi. `CADAGENT_REVIEW` và `CADAGENT_HEALTH` là command trực tiếp để kiểm tra thủ công; `CADAGENT_DISPATCH` là command đọc request và ghi result; `CADAGENT_CLOSE_DISPOSABLE` là command trực tiếp có guard disposable.

File IPC backend mới dùng:

```text
<ipc_dir>/cadagent_dotnet_request_<request_id>.json
<ipc_dir>/cadagent_dotnet_result_<request_id>.json
```

Mỗi request có `request_id`; result phải giữ nguyên id. File được ghi atomically bằng file tạm và rename/replace, sau đó client polling có timeout hữu hạn và dọn file của chính request đó.

## Thành phần

### `Ipc`

Chứa DTO, schema/version validation, full-path normalization, atomic JSON writer/reader và operation dispatch. Phần validation và serialization không phụ thuộc AutoCAD để test offline.

### `Drawing`

Chứa adapter mỏng quanh `Application.DocumentManager.MdiActiveDocument`, đọc tên/full path và đọc entity trong transaction chỉ-đọc. Adapter không tự mở hoặc lưu bản vẽ.

### `Review`

Chuyển entity AutoCAD thành payload ổn định gồm handle, type, layer và các trường hình học cơ bản cho LINE/CIRCLE/ARC/TEXT/DIMENSION. Entity không hỗ trợ được trả warning rõ ràng, không làm hỏng toàn bộ response nếu các handle khác đọc được.

### `Repair`

Chỉ tạo boundary/interface và trạng thái `not_supported` cho lát cắt đầu. Không có code mutation, không có `Save`, không có bypass approval/backup/second-review.

### `Mechanical`

Plugin chính chuẩn bị boundary Managed .NET nhưng không tham chiếu Mechanical ActiveX hoặc C++ SDK:

```csharp
public interface IMechanicalAdapter
{
    bool IsAvailable { get; }
    MechanicalCapabilityResult GetCapabilities();
    MechanicalOperationResult Execute(MechanicalOperationRequest request);
}
```

Implementation mặc định `NoOpMechanicalAdapter` trả `IsAvailable=false`, không có operation được hỗ trợ và kết quả `not_supported`. Interface này giúp bổ sung AM command/ActiveX/Native adapter sau này mà không làm plugin cơ bản phụ thuộc Mechanical SDK. Chỉ tạo project Mechanical/Native riêng khi có yêu cầu thật như BOM, balloon, Part Reference, Mechanical Structure, Content Library hoặc liên kết hình chiếu.

### `Commands`

Đăng ký bốn `CommandMethod` nêu trên, bắt lỗi thành result JSON hoặc thông báo Editor ngắn gọn. Command không chạy worker thread để chạm AutoCAD DB; mọi đọc entity thực hiện trong document context và transaction phù hợp.

### Python `dotnet_ipc`

Tạo request chuẩn, kích hoạt command `CADAGENT_DISPATCH` qua trigger Windows hiện có hoặc callback được inject trong test, polling result theo `request_id`, kiểm tra `success`, và expose các hàm `health`, `review`, `close_disposable`. Backend này không gọi hoặc chỉnh sửa `FileIPCLiveMCPClient` cũ.

## An toàn và lỗi

- Reject schema version không hỗ trợ, request id rỗng, operation ngoài allow-list và drawing path tương đối.
- Không chấp nhận path chỉ dựa trên filename; so sánh full path sau khi normalize Windows path.
- Mọi lỗi đọc JSON, timeout, mismatch document, thiếu handle hoặc lỗi transaction phải xuất hiện trong `errors`/`warnings`, không nuốt im lặng.
- `close_disposable` từ chối nếu thiếu cờ disposable hoặc có yêu cầu save.
- Plugin không tự lưu, không tự repair và không tự tải DLL.
- IPC directory mặc định là `C:\temp`, có thể override bằng `CAD_AGENT_DOTNET_IPC_DIR`; giá trị trong health result phải là full path.
- Không đưa bản vẽ riêng tư, result runtime, DLL AutoCAD hoặc build output vào Git.

## Kiểm thử và xác minh

1. C# unit tests không cần AutoCAD: DTO round-trip, schema/version validation, absolute-path validation, operation allow-list, close-disposable guard và payload mapping thuần.
2. Python contract tests: request/result round-trip, request id isolation, timeout/cleanup, fake dispatcher cho health/review và không ảnh hưởng dispatcher cũ.
3. Build C# Release x64 với .NET 10 và reference AutoCAD 2027; kiểm tra `Private=false` và output không chứa ba DLL Autodesk.
4. `scripts\verify.ps1` restore/build/test C# rồi chạy các gate Python hiện tại; live AutoCAD marker vẫn là gate riêng.
5. AutoCAD thật, khi có session: NETLOAD DLL thủ công, chạy `CADAGENT_HEALTH`, mở DXF disposable, chạy review theo handle, đóng không lưu và xác nhận file không bị sửa. Nếu không có session/plugin load được thì ghi `NOT RUN`, không coi là pass.

## Tiêu chí nghiệm thu

- `autocad_plugin/CadAgent.AutoCAD2027.sln` build được Release x64 trên máy hiện tại.
- Plugin chỉ tham chiếu ba DLL AutoCAD 2027 và không copy chúng vào output.
- `Directory.Build.props.example` được commit, `Directory.Build.props` thật bị ignore, và không có ObjectARX/Mechanical SDK binary/source trong Git.
- Có `IMechanicalAdapter` cùng `NoOpMechanicalAdapter`; plugin chính không tham chiếu ActiveX/COM hoặc C++ Mechanical SDK.
- C# unit tests và Python contract tests pass offline.
- `CADAGENT_HEALTH` đi qua backend JSON/File IPC và trả result có cùng `request_id`.
- `CADAGENT_REVIEW` chỉ đọc được entity theo handle, không save.
- `CADAGENT_CLOSE_DISPOSABLE` từ chối yêu cầu không disposable và đóng disposable không lưu.
- `mcp_integration_lib` dispatcher cũ và toàn bộ test hiện có vẫn pass.
- Không có production repair, không có tự động load plugin, không có private drawing trong Git.
