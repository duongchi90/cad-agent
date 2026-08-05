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
}
