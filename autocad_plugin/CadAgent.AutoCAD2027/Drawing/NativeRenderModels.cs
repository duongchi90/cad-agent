using System.Text.Json;
using CadAgent.AutoCAD2027.Ipc;

namespace CadAgent.AutoCAD2027.Drawing;

public sealed record NativeRenderLayout(string Identity, string Name);

public sealed record NativeRenderOptions(
    string Background,
    long Dpi,
    bool FitToPaper,
    string PaperSize,
    string PlotStyle);

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

        ContractValidator.EnsureRequestId(requestId);
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
                GetString(renderOptions, "plot_style")));
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
    IReadOnlyList<string> Warnings);

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

        return new Dictionary<string, JsonElement>(StringComparer.Ordinal)
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
            ["render_options"] = JsonSerializer.SerializeToElement(new
            {
                background = snapshot.RenderOptions.Background,
                dpi = snapshot.RenderOptions.Dpi,
                fit_to_paper = snapshot.RenderOptions.FitToPaper,
                paper_size = snapshot.RenderOptions.PaperSize,
                plot_style = snapshot.RenderOptions.PlotStyle
            }),
            ["renderer"] = JsonSerializer.SerializeToElement("AUTOCAD_NATIVE"),
            ["artifact"] = JsonSerializer.SerializeToElement(artifact),
            ["capture_timestamp"] = JsonSerializer.SerializeToElement(
                snapshot.CaptureTimestamp.ToUniversalTime().ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'")),
            ["changed"] = JsonSerializer.SerializeToElement(false),
            ["dbmod_before"] = JsonSerializer.SerializeToElement(snapshot.DbmodBefore),
            ["dbmod_after"] = JsonSerializer.SerializeToElement(snapshot.DbmodAfter),
            ["warnings"] = JsonSerializer.SerializeToElement(snapshot.Warnings.ToArray())
        };
    }
}

public static class NativeRenderPolicy
{
    public const long ApprovedPngWidth = 2480;
    public const long ApprovedPngHeight = 3508;
    public const long ApprovedPngLandscapeWidth = 3508;
    public const long ApprovedPngLandscapeHeight = 2480;

    public static bool IsApprovedPngDimensions(long width, long height) =>
        (width == ApprovedPngWidth && height == ApprovedPngHeight)
        || (width == ApprovedPngLandscapeWidth && height == ApprovedPngLandscapeHeight);

    public static void EnsureSupported(NativeRenderRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        if (string.Equals(request.Layout.Name, "Model", StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidDataException("Model space is not supported for native render evidence.");
        }

        if (request.ArtifactKind is not ("PNG" or "PDF")
            || !string.Equals(request.RenderOptions.Background, "white", StringComparison.Ordinal)
            || request.RenderOptions.Dpi != 300
            || !request.RenderOptions.FitToPaper
            || !string.Equals(request.RenderOptions.PaperSize, "A4", StringComparison.Ordinal)
            || !string.Equals(request.RenderOptions.PlotStyle, "monochrome.ctb", StringComparison.Ordinal))
        {
            throw new InvalidDataException("The native render profile is not supported.");
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
        }

        if (mismatches.Count != 0)
        {
            throw new InvalidDataException(
                "The native render evidence did not match the request or read-only boundary: "
                + string.Join(", ", mismatches));
        }
    }

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
