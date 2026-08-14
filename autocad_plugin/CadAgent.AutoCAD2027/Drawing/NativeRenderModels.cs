using System.Text.Json;
using CadAgent.AutoCAD2027.Ipc;

namespace CadAgent.AutoCAD2027.Drawing;

public sealed record NativeRenderLayout(string Identity, string Name);

public sealed record NativeRenderCamera(
    string SchemaVersion,
    string CaptureId,
    string CaptureClass,
    string? ParentRegionId,
    string? RegionId,
    string ScopeId,
    string ViewId,
    string SheetId,
    string LayoutId,
    string CandidateRevisionSha256,
    string CandidateStateSha256,
    string VisualCapturePlanSha256,
    string ZoomMode,
    IReadOnlyList<double>? WcsBbox,
    double MarginRatio,
    string ViewDirection,
    string Ucs,
    string VisualStyle);

public sealed record NativeRenderOptions(
    string Background,
    long Dpi,
    bool FitToPaper,
    string PaperSize,
    string PlotStyle,
    NativeRenderCamera? Camera = null);

public sealed record NativeRenderRequest(
    string RequestId,
    string RunId,
    string DrawingFullPath,
    string DrawingSha256,
    string LatestMutationSha256,
    string VisualRunManifestSha256,
    NativeRenderLayout Layout,
    string ArtifactKind,
    NativeRenderOptions RenderOptions)
{
    public static NativeRenderRequest FromIpc(IpcRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        var parameters = request.Parameters
            ?? throw new InvalidDataException("native_render_evidence requires parameters.");

        var requestId = request.RequestId
            ?? throw new InvalidDataException("request_id is required.");
        var drawingFullPath = request.DrawingFullPath
            ?? throw new InvalidDataException("drawing_full_path is required.");
        var drawingSha256 = request.DrawingSha256
            ?? throw new InvalidDataException("drawing_sha256 is required.");
        var layout = GetObject(parameters, "layout");
        var renderOptions = GetObject(parameters, "render_options");
        var cameraObject = GetOptionalObject(renderOptions, "camera");

        ContractValidator.EnsureRequestId(requestId);
        var camera = cameraObject is null ? null : ParseCamera(cameraObject);
        if (camera is not null)
        {
            NativeRenderPolicy.EnsureCameraSupported(camera);
        }

        return new NativeRenderRequest(
            requestId,
            GetString(parameters, "run_id"),
            drawingFullPath,
            drawingSha256,
            GetString(parameters, "latest_mutation_sha256"),
            GetString(parameters, "visual_run_manifest_sha256"),
            new NativeRenderLayout(
                GetString(layout, "identity"),
                GetString(layout, "name")),
            GetString(parameters, "artifact_kind"),
            new NativeRenderOptions(
                GetString(renderOptions, "background"),
                GetInt64(renderOptions, "dpi"),
                GetBoolean(renderOptions, "fit_to_paper"),
                GetString(renderOptions, "paper_size"),
                GetString(renderOptions, "plot_style"),
                camera));
    }

    private static NativeRenderCamera ParseCamera(
        IReadOnlyDictionary<string, JsonElement> camera)
    {
        return new NativeRenderCamera(
            GetString(camera, "schema_version"),
            GetString(camera, "capture_id"),
            GetString(camera, "capture_class"),
            GetNullableString(camera, "parent_region_id"),
            GetNullableString(camera, "region_id"),
            GetString(camera, "scope_id"),
            GetString(camera, "view_id"),
            GetString(camera, "sheet_id"),
            GetString(camera, "layout_id"),
            GetString(camera, "candidate_revision_sha256"),
            GetString(camera, "candidate_state_sha256"),
            GetString(camera, "visual_capture_plan_sha256"),
            GetString(camera, "zoom_mode"),
            GetNullableDoubleArray(camera, "wcs_bbox"),
            GetDouble(camera, "margin_ratio"),
            GetString(camera, "view_direction"),
            GetString(camera, "ucs"),
            GetString(camera, "visual_style"));
    }

    private static Dictionary<string, JsonElement> GetObject(
        IReadOnlyDictionary<string, JsonElement> values,
        string name)
    {
        if (!values.TryGetValue(name, out var value) || value.ValueKind != JsonValueKind.Object)
        {
            throw new InvalidDataException($"native_render_evidence parameter '{name}' must be an object.");
        }

        return value.EnumerateObject()
            .ToDictionary(property => property.Name, property => property.Value.Clone(), StringComparer.Ordinal);
    }

    private static Dictionary<string, JsonElement>? GetOptionalObject(
        IReadOnlyDictionary<string, JsonElement> values,
        string name)
    {
        if (!values.TryGetValue(name, out var value))
        {
            return null;
        }
        if (value.ValueKind != JsonValueKind.Object)
        {
            throw new InvalidDataException($"native_render_evidence parameter '{name}' must be an object when present.");
        }

        return value.EnumerateObject()
            .ToDictionary(property => property.Name, property => property.Value.Clone(), StringComparer.Ordinal);
    }

    private static string GetString(IReadOnlyDictionary<string, JsonElement> values, string name)
    {
        if (!values.TryGetValue(name, out var value)
            || value.ValueKind != JsonValueKind.String
            || string.IsNullOrWhiteSpace(value.GetString()))
        {
            throw new InvalidDataException($"native_render_evidence parameter '{name}' must be a non-empty string.");
        }

        return value.GetString()!;
    }

    private static string? GetNullableString(
        IReadOnlyDictionary<string, JsonElement> values,
        string name)
    {
        if (!values.TryGetValue(name, out var value))
        {
            throw new InvalidDataException($"native_render_evidence parameter '{name}' is required.");
        }
        if (value.ValueKind == JsonValueKind.Null)
        {
            return null;
        }
        if (value.ValueKind != JsonValueKind.String || string.IsNullOrWhiteSpace(value.GetString()))
        {
            throw new InvalidDataException($"native_render_evidence parameter '{name}' must be null or a non-empty string.");
        }

        return value.GetString();
    }

    private static long GetInt64(IReadOnlyDictionary<string, JsonElement> values, string name)
    {
        if (!values.TryGetValue(name, out var value)
            || value.ValueKind != JsonValueKind.Number
            || !value.TryGetInt64(out var number))
        {
            throw new InvalidDataException($"native_render_evidence parameter '{name}' must be an integer.");
        }

        return number;
    }

    private static double GetDouble(IReadOnlyDictionary<string, JsonElement> values, string name)
    {
        if (!values.TryGetValue(name, out var value)
            || value.ValueKind != JsonValueKind.Number
            || !value.TryGetDouble(out var number)
            || !double.IsFinite(number))
        {
            throw new InvalidDataException($"native_render_evidence parameter '{name}' must be a finite number.");
        }

        return number;
    }

    private static IReadOnlyList<double>? GetNullableDoubleArray(
        IReadOnlyDictionary<string, JsonElement> values,
        string name)
    {
        if (!values.TryGetValue(name, out var value))
        {
            throw new InvalidDataException($"native_render_evidence parameter '{name}' is required.");
        }
        if (value.ValueKind == JsonValueKind.Null)
        {
            return null;
        }
        if (value.ValueKind != JsonValueKind.Array || value.GetArrayLength() != 4)
        {
            throw new InvalidDataException($"native_render_evidence parameter '{name}' must be null or four finite numbers.");
        }

        var result = new List<double>(4);
        foreach (var item in value.EnumerateArray())
        {
            if (item.ValueKind != JsonValueKind.Number
                || !item.TryGetDouble(out var number)
                || !double.IsFinite(number))
            {
                throw new InvalidDataException($"native_render_evidence parameter '{name}' must contain finite numbers.");
            }
            result.Add(number);
        }
        return result;
    }

    private static bool GetBoolean(IReadOnlyDictionary<string, JsonElement> values, string name)
    {
        if (!values.TryGetValue(name, out var value)
            || value.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
        {
            throw new InvalidDataException($"native_render_evidence parameter '{name}' must be a boolean.");
        }

        return value.GetBoolean();
    }
}

public sealed record NativeRenderArtifact(
    string RelativePath,
    string Sha256,
    long? Width,
    long? Height,
    long? PageCount);

public sealed record NativeRenderCameraReceipt(
    string SchemaVersion,
    string ReceiptId,
    string CaptureId,
    string RunId,
    string ScopeId,
    string? RegionId,
    string ViewId,
    string SheetId,
    string LayoutId,
    string CandidateRevisionSha256,
    string CandidateStateSha256,
    string LatestMutationSha256,
    string VisualCapturePlanSha256,
    string CaptureClass,
    string ZoomMode,
    IReadOnlyList<double>? RequestedWcsBbox,
    IReadOnlyList<double>? ObservedWcsBbox,
    IReadOnlyList<double> ViewCenter,
    double ViewWidth,
    double ViewHeight,
    string ViewDirection,
    string Ucs,
    string VisualStyle,
    string ArtifactSha256,
    long ArtifactWidth,
    long ArtifactHeight,
    DateTimeOffset CapturedAtUtc,
    bool TransientStateRestored);

public sealed record NativeRenderEvidenceSnapshot(
    string RequestId,
    string RunId,
    string DrawingSha256,
    string LatestMutationSha256,
    string VisualRunManifestSha256,
    NativeRenderLayout Layout,
    string ArtifactKind,
    NativeRenderOptions RenderOptions,
    NativeRenderArtifact Artifact,
    DateTimeOffset CaptureTimestamp,
    int DbmodBefore,
    int DbmodAfter,
    IReadOnlyList<string> Warnings,
    NativeRenderCameraReceipt? VisualCaptureReceipt = null);

public static class NativeRenderPayload
{
    public static Dictionary<string, JsonElement> Create(NativeRenderEvidenceSnapshot snapshot)
    {
        ArgumentNullException.ThrowIfNull(snapshot);
        ArgumentNullException.ThrowIfNull(snapshot.Artifact);

        var artifact = snapshot.ArtifactKind switch
        {
            "PNG" when snapshot.Artifact.Width.HasValue && snapshot.Artifact.Height.HasValue =>
                new Dictionary<string, JsonElement>(StringComparer.Ordinal)
                {
                    ["relative_path"] = JsonSerializer.SerializeToElement(snapshot.Artifact.RelativePath),
                    ["sha256"] = JsonSerializer.SerializeToElement(snapshot.Artifact.Sha256),
                    ["width"] = JsonSerializer.SerializeToElement(snapshot.Artifact.Width.Value),
                    ["height"] = JsonSerializer.SerializeToElement(snapshot.Artifact.Height.Value)
                },
            "PDF" when snapshot.Artifact.PageCount.HasValue =>
                new Dictionary<string, JsonElement>(StringComparer.Ordinal)
                {
                    ["relative_path"] = JsonSerializer.SerializeToElement(snapshot.Artifact.RelativePath),
                    ["sha256"] = JsonSerializer.SerializeToElement(snapshot.Artifact.Sha256),
                    ["page_count"] = JsonSerializer.SerializeToElement(snapshot.Artifact.PageCount.Value)
                },
            _ => throw new InvalidDataException("The native render artifact metadata is incomplete.")
        };

        var renderOptions = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["background"] = snapshot.RenderOptions.Background,
            ["dpi"] = snapshot.RenderOptions.Dpi,
            ["fit_to_paper"] = snapshot.RenderOptions.FitToPaper,
            ["paper_size"] = snapshot.RenderOptions.PaperSize,
            ["plot_style"] = snapshot.RenderOptions.PlotStyle
        };
        if (snapshot.RenderOptions.Camera is not null)
        {
            var camera = snapshot.RenderOptions.Camera;
            renderOptions["camera"] = new
            {
                schema_version = camera.SchemaVersion,
                capture_id = camera.CaptureId,
                capture_class = camera.CaptureClass,
                parent_region_id = camera.ParentRegionId,
                region_id = camera.RegionId,
                scope_id = camera.ScopeId,
                view_id = camera.ViewId,
                sheet_id = camera.SheetId,
                layout_id = camera.LayoutId,
                candidate_revision_sha256 = camera.CandidateRevisionSha256,
                candidate_state_sha256 = camera.CandidateStateSha256,
                visual_capture_plan_sha256 = camera.VisualCapturePlanSha256,
                zoom_mode = camera.ZoomMode,
                wcs_bbox = camera.WcsBbox,
                margin_ratio = camera.MarginRatio,
                view_direction = camera.ViewDirection,
                ucs = camera.Ucs,
                visual_style = camera.VisualStyle
            };
        }

        var payload = new Dictionary<string, JsonElement>(StringComparer.Ordinal)
        {
            ["schema_version"] = JsonSerializer.SerializeToElement(
                "autocad-native-render-evidence-1.0"),
            ["request_id"] = JsonSerializer.SerializeToElement(snapshot.RequestId),
            ["run_id"] = JsonSerializer.SerializeToElement(snapshot.RunId),
            ["drawing_sha256"] = JsonSerializer.SerializeToElement(snapshot.DrawingSha256),
            ["latest_mutation_sha256"] = JsonSerializer.SerializeToElement(snapshot.LatestMutationSha256),
            ["visual_run_manifest_sha256"] = JsonSerializer.SerializeToElement(
                snapshot.VisualRunManifestSha256),
            ["layout"] = JsonSerializer.SerializeToElement(new
            {
                identity = snapshot.Layout.Identity,
                name = snapshot.Layout.Name
            }),
            ["artifact_kind"] = JsonSerializer.SerializeToElement(snapshot.ArtifactKind),
            ["render_options"] = JsonSerializer.SerializeToElement(renderOptions),
            ["renderer"] = JsonSerializer.SerializeToElement("AUTOCAD_NATIVE"),
            ["artifact"] = JsonSerializer.SerializeToElement(artifact),
            ["capture_timestamp"] = JsonSerializer.SerializeToElement(
                snapshot.CaptureTimestamp.ToUniversalTime().ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'")),
            ["changed"] = JsonSerializer.SerializeToElement(false),
            ["dbmod_before"] = JsonSerializer.SerializeToElement(snapshot.DbmodBefore),
            ["dbmod_after"] = JsonSerializer.SerializeToElement(snapshot.DbmodAfter),
            ["warnings"] = JsonSerializer.SerializeToElement(snapshot.Warnings.ToArray())
        };

        if (snapshot.VisualCaptureReceipt is not null)
        {
            var receipt = snapshot.VisualCaptureReceipt;
            payload["visual_capture_receipt"] = JsonSerializer.SerializeToElement(new
            {
                schema_version = "visual-capture-receipt-1.0",
                receipt_id = receipt.ReceiptId,
                capture_id = receipt.CaptureId,
                run_id = receipt.RunId,
                scope_id = receipt.ScopeId,
                region_id = receipt.RegionId,
                view_id = receipt.ViewId,
                sheet_id = receipt.SheetId,
                layout_id = receipt.LayoutId,
                candidate_revision_sha256 = receipt.CandidateRevisionSha256,
                candidate_state_sha256 = receipt.CandidateStateSha256,
                latest_mutation_sha256 = receipt.LatestMutationSha256,
                visual_capture_plan_sha256 = receipt.VisualCapturePlanSha256,
                capture_class = receipt.CaptureClass,
                zoom_mode = receipt.ZoomMode,
                requested_wcs_bbox = receipt.RequestedWcsBbox,
                observed_wcs_bbox = receipt.ObservedWcsBbox,
                view_center = receipt.ViewCenter,
                view_width = receipt.ViewWidth,
                view_height = receipt.ViewHeight,
                view_direction = receipt.ViewDirection,
                ucs = receipt.Ucs,
                visual_style = receipt.VisualStyle,
                artifact_sha256 = receipt.ArtifactSha256,
                artifact_width = receipt.ArtifactWidth,
                artifact_height = receipt.ArtifactHeight,
                captured_at_utc = receipt.CapturedAtUtc.ToUniversalTime().ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'"),
                transient_state_restored = receipt.TransientStateRestored
            });
        }

        return payload;
    }
}

public static class NativeRenderPolicy
{
    public const string DuplicateRequestErrorCode = "NATIVE_RENDER_DUPLICATE_REQUEST";
    public const string DuplicateArtifactErrorCode = "NATIVE_RENDER_DUPLICATE_ARTIFACT";
    public const string DeviceUnavailableErrorCode = "NATIVE_RENDER_DEVICE_UNAVAILABLE";
    public const string MediaUnavailableErrorCode = "NATIVE_RENDER_MEDIA_UNAVAILABLE";
    public const string LayoutNotFoundErrorCode = "NATIVE_RENDER_LAYOUT_NOT_FOUND";
    public const string UnsupportedProfileErrorCode = "NATIVE_RENDER_UNSUPPORTED_PROFILE";

    public const long ApprovedPngWidth = 2480;
    public const long ApprovedPngHeight = 3508;
    public const long ApprovedPngLandscapeWidth = 3508;
    public const long ApprovedPngLandscapeHeight = 2480;

    public static bool IsApprovedPngDimensions(long width, long height) =>
        (width == ApprovedPngWidth && height == ApprovedPngHeight)
        || (width == ApprovedPngLandscapeWidth && height == ApprovedPngLandscapeHeight);

    public static void EnsureCameraSupported(NativeRenderCamera camera)
    {
        ArgumentNullException.ThrowIfNull(camera);
        if (!string.Equals(camera.SchemaVersion, "canonical-camera-render-1.0", StringComparison.Ordinal)
            || string.IsNullOrWhiteSpace(camera.CaptureId)
            || string.IsNullOrWhiteSpace(camera.ScopeId)
            || string.IsNullOrWhiteSpace(camera.ViewId)
            || string.IsNullOrWhiteSpace(camera.SheetId)
            || string.IsNullOrWhiteSpace(camera.LayoutId)
            || !IsLowerSha(camera.CandidateRevisionSha256)
            || !IsLowerSha(camera.CandidateStateSha256)
            || !IsLowerSha(camera.VisualCapturePlanSha256)
            || !string.Equals(camera.ViewDirection, "TOP", StringComparison.Ordinal)
            || !string.Equals(camera.Ucs, "WORLD", StringComparison.Ordinal)
            || !string.Equals(camera.VisualStyle, "2D_WIREFRAME", StringComparison.Ordinal)
            || !double.IsFinite(camera.MarginRatio))
        {
            throw new InvalidDataException(
                $"{UnsupportedProfileErrorCode}: The canonical camera contract is invalid.");
        }

        if (camera.CaptureClass == "GLOBAL")
        {
            if (camera.ZoomMode != "EXTENTS"
                || camera.WcsBbox is not null
                || camera.RegionId is not null
                || camera.ParentRegionId is not null
                || camera.MarginRatio != 0.05)
            {
                throw new InvalidDataException(
                    $"{UnsupportedProfileErrorCode}: GLOBAL canonical camera is invalid.");
            }
            return;
        }

        if (camera.CaptureClass is not ("REGION" or "DETAIL")
            || camera.ZoomMode != "WINDOW"
            || string.IsNullOrWhiteSpace(camera.RegionId)
            || camera.WcsBbox is null
            || camera.WcsBbox.Count != 4
            || camera.WcsBbox.Any(value => !double.IsFinite(value))
            || camera.WcsBbox[2] <= camera.WcsBbox[0]
            || camera.WcsBbox[3] <= camera.WcsBbox[1])
        {
            throw new InvalidDataException(
                $"{UnsupportedProfileErrorCode}: WINDOW canonical camera is invalid.");
        }

        if (camera.CaptureClass == "REGION")
        {
            if (camera.ParentRegionId is not null || camera.MarginRatio != 0.10)
            {
                throw new InvalidDataException(
                    $"{UnsupportedProfileErrorCode}: REGION canonical camera is invalid.");
            }
        }
        else if (camera.ParentRegionId != camera.RegionId || camera.MarginRatio != 0.05)
        {
            throw new InvalidDataException(
                $"{UnsupportedProfileErrorCode}: DETAIL canonical camera is invalid.");
        }
    }

    public static void EnsureSupported(NativeRenderRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        if (string.Equals(request.Layout.Name, "Model", StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidDataException(
                $"{UnsupportedProfileErrorCode}: Model space is not supported for native render evidence.");
        }

        if (request.ArtifactKind is not ("PNG" or "PDF")
            || !string.Equals(request.RenderOptions.Background, "white", StringComparison.Ordinal)
            || request.RenderOptions.Dpi != 300
            || !request.RenderOptions.FitToPaper
            || !string.Equals(request.RenderOptions.PaperSize, "A4", StringComparison.Ordinal)
            || !string.Equals(request.RenderOptions.PlotStyle, "monochrome.ctb", StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                $"{UnsupportedProfileErrorCode}: The native render profile is not supported.");
        }

        if (request.RenderOptions.Camera is not null)
        {
            if (request.ArtifactKind != "PNG")
            {
                throw new InvalidDataException(
                    $"{UnsupportedProfileErrorCode}: canonical camera native render must be PNG.");
            }
            EnsureCameraSupported(request.RenderOptions.Camera);
            if (!string.Equals(
                    request.RenderOptions.Camera.LayoutId,
                    request.Layout.Identity,
                    StringComparison.Ordinal))
            {
                throw new InvalidDataException(
                    $"{UnsupportedProfileErrorCode}: camera layout identity does not match request layout.");
            }
        }
    }

    public static void EnsureReadOnly(
        int dbmodBefore,
        int dbmodAfter,
        string drawingHashBefore,
        string drawingHashAfter,
        bool sessionStateRestored)
    {
        if (dbmodBefore < 0 || dbmodAfter < 0 || dbmodBefore != dbmodAfter)
        {
            throw new InvalidDataException("DBMOD changed during native render evidence capture.");
        }

        if (string.IsNullOrWhiteSpace(drawingHashBefore)
            || !string.Equals(drawingHashBefore, drawingHashAfter, StringComparison.Ordinal))
        {
            throw new InvalidDataException("The drawing hash changed during native render evidence capture.");
        }

        if (!sessionStateRestored)
        {
            throw new InvalidDataException("AutoCAD session state was not restored.");
        }
    }

    public static void EnsureMatchesRequest(
        NativeRenderRequest request,
        NativeRenderEvidenceSnapshot snapshot)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentNullException.ThrowIfNull(snapshot);

        var mismatches = new List<string>();
        if (!string.Equals(snapshot.RequestId, request.RequestId, StringComparison.Ordinal))
        {
            mismatches.Add("request_id");
        }

        if (!string.Equals(snapshot.RunId, request.RunId, StringComparison.Ordinal))
        {
            mismatches.Add("run_id");
        }

        if (!string.Equals(snapshot.DrawingSha256, request.DrawingSha256, StringComparison.Ordinal))
        {
            mismatches.Add("drawing_sha256");
        }

        if (!string.Equals(
                snapshot.LatestMutationSha256,
                request.LatestMutationSha256,
                StringComparison.Ordinal))
        {
            mismatches.Add("latest_mutation_sha256");
        }

        if (!string.Equals(
                snapshot.VisualRunManifestSha256,
                request.VisualRunManifestSha256,
                StringComparison.Ordinal))
        {
            mismatches.Add("visual_run_manifest_sha256");
        }

        if (!string.Equals(snapshot.ArtifactKind, request.ArtifactKind, StringComparison.Ordinal))
        {
            mismatches.Add("artifact_kind");
        }

        if (!string.Equals(snapshot.Layout.Identity, request.Layout.Identity, StringComparison.Ordinal))
        {
            mismatches.Add("layout.identity");
        }

        if (!string.Equals(snapshot.Layout.Name, request.Layout.Name, StringComparison.Ordinal))
        {
            mismatches.Add("layout.name");
        }

        if (!string.Equals(snapshot.RenderOptions.Background, request.RenderOptions.Background, StringComparison.Ordinal))
        {
            mismatches.Add("render_options.background");
        }

        if (snapshot.RenderOptions.Dpi != request.RenderOptions.Dpi)
        {
            mismatches.Add("render_options.dpi");
        }

        if (snapshot.RenderOptions.FitToPaper != request.RenderOptions.FitToPaper)
        {
            mismatches.Add("render_options.fit_to_paper");
        }

        if (!string.Equals(snapshot.RenderOptions.PaperSize, request.RenderOptions.PaperSize, StringComparison.Ordinal))
        {
            mismatches.Add("render_options.paper_size");
        }

        if (!string.Equals(snapshot.RenderOptions.PlotStyle, request.RenderOptions.PlotStyle, StringComparison.Ordinal))
        {
            mismatches.Add("render_options.plot_style");
        }

        if (!CameraMatches(snapshot.RenderOptions.Camera, request.RenderOptions.Camera))
        {
            mismatches.Add("render_options.camera");
        }

        if ((request.RenderOptions.Camera is null) != (snapshot.VisualCaptureReceipt is null))
        {
            mismatches.Add("visual_capture_receipt");
        }
        if (request.RenderOptions.Camera is not null && snapshot.VisualCaptureReceipt is not null)
        {
            var receipt = snapshot.VisualCaptureReceipt;
            if (receipt.CaptureId != request.RenderOptions.Camera.CaptureId
                || receipt.RunId != request.RunId
                || receipt.ScopeId != request.RenderOptions.Camera.ScopeId
                || receipt.RegionId != request.RenderOptions.Camera.RegionId
                || receipt.ViewId != request.RenderOptions.Camera.ViewId
                || receipt.SheetId != request.RenderOptions.Camera.SheetId
                || receipt.LayoutId != request.RenderOptions.Camera.LayoutId
                || receipt.CandidateRevisionSha256 != request.RenderOptions.Camera.CandidateRevisionSha256
                || receipt.CandidateStateSha256 != request.RenderOptions.Camera.CandidateStateSha256
                || receipt.LatestMutationSha256 != request.LatestMutationSha256
                || receipt.VisualCapturePlanSha256 != request.RenderOptions.Camera.VisualCapturePlanSha256
                || receipt.CaptureClass != request.RenderOptions.Camera.CaptureClass
                || receipt.ZoomMode != request.RenderOptions.Camera.ZoomMode
                || receipt.ViewDirection != request.RenderOptions.Camera.ViewDirection
                || receipt.Ucs != request.RenderOptions.Camera.Ucs
                || receipt.VisualStyle != request.RenderOptions.Camera.VisualStyle
                || !receipt.TransientStateRestored)
            {
                mismatches.Add("visual_capture_receipt.binding");
            }
        }

        if (snapshot.DbmodBefore < 0
            || snapshot.DbmodAfter < 0
            || snapshot.DbmodBefore != snapshot.DbmodAfter)
        {
            mismatches.Add("dbmod");
        }

        if (snapshot.Artifact is null)
        {
            mismatches.Add("artifact");
        }
        else
        {
            var expectedPath = ExpectedArtifactRelativePath(request);
            if (!string.Equals(snapshot.Artifact.RelativePath, expectedPath, StringComparison.Ordinal))
            {
                mismatches.Add("artifact.relative_path");
            }

            if (!System.Text.RegularExpressions.Regex.IsMatch(
                    snapshot.Artifact.Sha256,
                    "^[0-9a-f]{64}$",
                    System.Text.RegularExpressions.RegexOptions.CultureInvariant))
            {
                mismatches.Add("artifact.sha256");
            }

            if (request.ArtifactKind == "PNG"
                && (!snapshot.Artifact.Width.HasValue
                    || !snapshot.Artifact.Height.HasValue
                    || !IsApprovedPngDimensions(
                        snapshot.Artifact.Width.Value,
                        snapshot.Artifact.Height.Value)
                    || snapshot.Artifact.PageCount is not null))
            {
                mismatches.Add("artifact.png_metadata");
            }

            if (request.ArtifactKind == "PDF"
                && (snapshot.Artifact.PageCount != 1
                    || snapshot.Artifact.Width is not null
                    || snapshot.Artifact.Height is not null))
            {
                mismatches.Add("artifact.pdf_metadata");
            }

            if (snapshot.VisualCaptureReceipt is not null
                && (snapshot.Artifact.Width is null
                    || snapshot.Artifact.Height is null
                    || snapshot.VisualCaptureReceipt.ArtifactSha256 != snapshot.Artifact.Sha256
                    || snapshot.VisualCaptureReceipt.ArtifactWidth != snapshot.Artifact.Width.Value
                    || snapshot.VisualCaptureReceipt.ArtifactHeight != snapshot.Artifact.Height.Value))
            {
                mismatches.Add("visual_capture_receipt.artifact");
            }
        }

        if (mismatches.Count != 0)
        {
            throw new InvalidDataException(
                "The native render evidence did not match the request or read-only boundary: "
                + string.Join(", ", mismatches));
        }
    }

    private static bool CameraMatches(NativeRenderCamera? left, NativeRenderCamera? right)
    {
        if (left is null || right is null)
        {
            return left is null && right is null;
        }
        return left with { WcsBbox = null } == right with { WcsBbox = null }
            && SequenceMatches(left.WcsBbox, right.WcsBbox);
    }

    private static bool SequenceMatches(
        IReadOnlyList<double>? left,
        IReadOnlyList<double>? right)
    {
        if (left is null || right is null)
        {
            return left is null && right is null;
        }
        return left.Count == right.Count
            && left.Zip(right, (a, b) => a.Equals(b)).All(equal => equal);
    }

    private static bool IsLowerSha(string value) =>
        value.Length == 64
        && value.All(character => character is >= '0' and <= '9' or >= 'a' and <= 'f');

    public static string ExpectedArtifactRelativePath(NativeRenderRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        var extension = request.ArtifactKind switch
        {
            "PNG" => "png",
            "PDF" => "pdf",
            _ => throw new InvalidDataException("The native render artifact kind is unsupported.")
        };
        return $"native-render/{request.RequestId}/artifact.{extension}";
    }
}