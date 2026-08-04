using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using CadAgent.AutoCAD2027.Ipc;

namespace CadAgent.AutoCAD2027.Drawing;

public sealed record VisualEvidenceRequest(
    string DrawingFullPath,
    string DrawingSha256,
    string RunId,
    string EvidenceId,
    string RegionId,
    string LatestMutationSha256,
    string VisualRunManifestSha256,
    string ArtifactPolicyVersion,
    string ArtifactDirectory,
    JsonElement Region,
    IReadOnlyList<JsonElement> Measurements)
{
    public static VisualEvidenceRequest FromIpc(IpcRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        if (request.Parameters is null)
        {
            throw new InvalidDataException("visual_evidence_export requires parameters.");
        }

        var parameters = request.Parameters;
        return new VisualEvidenceRequest(
            request.DrawingFullPath ?? throw new InvalidDataException("drawing_full_path is required."),
            request.DrawingSha256 ?? throw new InvalidDataException("drawing_sha256 is required."),
            parameters["run_id"].GetString()!,
            parameters["evidence_id"].GetString()!,
            parameters["region_id"].GetString()!,
            parameters["latest_mutation_sha256"].GetString()!,
            parameters["visual_run_manifest_sha256"].GetString()!,
            parameters["artifact_policy_version"].GetString()!,
            parameters["artifact_directory"].GetString()!,
            parameters["region"].Clone(),
            parameters["measurements"].EnumerateArray().Select(value => value.Clone()).ToArray());
    }
}

public sealed record EvidenceArtifactDescriptor(
    string ArtifactId,
    string Kind,
    string RelativePath,
    string Sha256,
    long ByteLength,
    string MimeType,
    int? Width = null,
    int? Height = null);

public sealed record SessionViewSnapshot(
    double CenterX,
    double CenterY,
    double Width,
    double Height,
    double TargetX,
    double TargetY,
    double TargetZ,
    double DirectionX,
    double DirectionY,
    double DirectionZ,
    double Twist,
    double LensLength);

public sealed record SessionSpaceSnapshot(
    string LayoutName,
    int TileMode,
    int Cvport,
    string Kind);

public sealed record SessionLayerSnapshot(bool IsOff, bool IsFrozen);

public sealed record SessionStateSnapshot(
    string DrawingFullPath,
    string DocumentIdentity,
    string CurrentLayout,
    SessionSpaceSnapshot Space,
    string CurrentLayer,
    string ViewProperties,
    SessionViewSnapshot? CurrentView,
    IReadOnlyList<string> SelectionHandles,
    IReadOnlyDictionary<string, SessionLayerSnapshot> LayerStates,
    IReadOnlyDictionary<string, JsonElement> RendererSystemVariables,
    string FingerprintSha256)
{
    public static SessionStateSnapshot Create(
        string drawingFullPath,
        string documentIdentity,
        string currentLayout,
        SessionSpaceSnapshot space,
        string currentLayer,
        string viewProperties,
        IEnumerable<string> selectionHandles,
        IReadOnlyDictionary<string, SessionLayerSnapshot> layerStates,
        IReadOnlyDictionary<string, JsonElement> rendererSystemVariables,
        SessionViewSnapshot? currentView = null)
    {
        ArgumentNullException.ThrowIfNull(selectionHandles);
        ArgumentNullException.ThrowIfNull(layerStates);
        ArgumentNullException.ThrowIfNull(rendererSystemVariables);
        ArgumentNullException.ThrowIfNull(space);

        var normalizedPath = ContractValidator.NormalizeWindowsAbsolutePath(drawingFullPath);
        var canonical = new
        {
            drawing_full_path = normalizedPath,
            document_identity = documentIdentity,
            current_layout = currentLayout,
            space,
            current_layer = currentLayer,
            view_properties = viewProperties,
            current_view = currentView,
            selection_handles = selectionHandles.ToArray(),
            layer_states = layerStates.OrderBy(item => item.Key, StringComparer.Ordinal)
                .ToDictionary(item => item.Key, item => new
                {
                    is_off = item.Value.IsOff,
                    is_frozen = item.Value.IsFrozen
                }, StringComparer.Ordinal),
            renderer_system_variables = rendererSystemVariables.OrderBy(item => item.Key, StringComparer.Ordinal)
                .ToDictionary(item => item.Key, item => item.Value, StringComparer.Ordinal)
        };
        var bytes = JsonSerializer.SerializeToUtf8Bytes(canonical);
        return new SessionStateSnapshot(
            normalizedPath,
            documentIdentity,
            currentLayout,
            space,
            currentLayer,
            viewProperties,
            currentView,
            selectionHandles.ToArray(),
            layerStates.OrderBy(item => item.Key, StringComparer.Ordinal)
                .ToDictionary(item => item.Key, item => item.Value, StringComparer.Ordinal),
            rendererSystemVariables.OrderBy(item => item.Key, StringComparer.Ordinal)
                .ToDictionary(item => item.Key, item => item.Value, StringComparer.Ordinal),
            Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant());
    }
}

public sealed record VisualEvidenceSnapshot(
    string ActiveDocumentFullPath,
    string DrawingFullPath,
    string RunId,
    string EvidenceId,
    string RegionId,
    string DrawingSha256Before,
    string DrawingSha256After,
    long DbModBefore,
    long DbModAfter,
    string LatestMutationSha256,
    string VisualRunManifestSha256,
    string RegionConfigSha256,
    string SessionStateSha256Before,
    string SessionStateSha256After,
    bool TransientStateRestored,
    DateTimeOffset CapturedAtUtc,
    IReadOnlyList<EvidenceArtifactDescriptor> Artifacts,
    bool Changed,
    IReadOnlyList<string> EntityHandles);

public static class VisualEvidencePayload
{
    private static readonly JsonSerializerOptions SerializerOptions = new()
    {
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
    };

    public static Dictionary<string, JsonElement> Create(VisualEvidenceSnapshot snapshot)
    {
        ArgumentNullException.ThrowIfNull(snapshot);
        return new Dictionary<string, JsonElement>(StringComparer.Ordinal)
        {
            ["run_id"] = JsonSerializer.SerializeToElement(snapshot.RunId),
            ["evidence_id"] = JsonSerializer.SerializeToElement(snapshot.EvidenceId),
            ["region_id"] = JsonSerializer.SerializeToElement(snapshot.RegionId),
            ["drawing_sha256_before"] = JsonSerializer.SerializeToElement(snapshot.DrawingSha256Before),
            ["drawing_sha256_after"] = JsonSerializer.SerializeToElement(snapshot.DrawingSha256After),
            ["dbmod_before"] = JsonSerializer.SerializeToElement(snapshot.DbModBefore),
            ["dbmod_after"] = JsonSerializer.SerializeToElement(snapshot.DbModAfter),
            ["latest_mutation_sha256"] = JsonSerializer.SerializeToElement(snapshot.LatestMutationSha256),
            ["visual_run_manifest_sha256"] = JsonSerializer.SerializeToElement(snapshot.VisualRunManifestSha256),
            ["region_config_sha256"] = JsonSerializer.SerializeToElement(snapshot.RegionConfigSha256),
            ["session_state_sha256_before"] = JsonSerializer.SerializeToElement(snapshot.SessionStateSha256Before),
            ["session_state_sha256_after"] = JsonSerializer.SerializeToElement(snapshot.SessionStateSha256After),
            ["transient_state_restored"] = JsonSerializer.SerializeToElement(snapshot.TransientStateRestored),
            ["captured_at_utc"] = JsonSerializer.SerializeToElement(
                snapshot.CapturedAtUtc.ToUniversalTime().ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'")),
            ["artifacts"] = JsonSerializer.SerializeToElement(snapshot.Artifacts.Select(artifact => new
            {
                artifact_id = artifact.ArtifactId,
                kind = artifact.Kind == "entity-map" ? "entity_map" : artifact.Kind,
                relative_path = artifact.RelativePath,
                sha256 = artifact.Sha256,
                byte_length = artifact.ByteLength,
                mime_type = artifact.MimeType,
                width = artifact.Width,
                height = artifact.Height
            }).ToArray(), SerializerOptions)
        };
    }
}

public static class VisualEvidenceReadOnlyBoundary
{
    public static IReadOnlyList<string> Validate(
        VisualEvidenceRequest request,
        VisualEvidenceSnapshot snapshot)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentNullException.ThrowIfNull(snapshot);
        var errors = new List<string>();
        var requestedPath = NormalizePath(request.DrawingFullPath, errors, "requested");
        var activePath = NormalizePath(snapshot.ActiveDocumentFullPath, errors, "active");
        var snapshotPath = NormalizePath(snapshot.DrawingFullPath, errors, "snapshot");
        if (requestedPath is null || activePath is null || snapshotPath is null
            || !StringComparer.OrdinalIgnoreCase.Equals(requestedPath, activePath)
            || !StringComparer.OrdinalIgnoreCase.Equals(requestedPath, snapshotPath))
        {
            errors.Add("The requested drawing_full_path does not match the active document full path.");
        }
        if (!string.Equals(snapshot.DrawingSha256Before, request.DrawingSha256, StringComparison.Ordinal))
        {
            errors.Add("The before drawing hash does not match the requested drawing_sha256.");
        }
        if (!string.Equals(snapshot.DrawingSha256Before, snapshot.DrawingSha256After, StringComparison.Ordinal))
        {
            errors.Add("The drawing hash changed during the read-only operation.");
        }
        if (snapshot.DbModBefore != snapshot.DbModAfter)
        {
            errors.Add("DBMOD changed during the read-only operation.");
        }
        if (!string.Equals(snapshot.SessionStateSha256Before, snapshot.SessionStateSha256After, StringComparison.Ordinal)
            || !snapshot.TransientStateRestored)
        {
            errors.Add("Transient AutoCAD session state was not restored.");
        }
        if (!string.Equals(request.RunId, snapshot.RunId, StringComparison.Ordinal))
        {
            errors.Add("run_id was not echoed exactly.");
        }
        if (!string.Equals(request.RegionId, snapshot.RegionId, StringComparison.Ordinal))
        {
            errors.Add("region_id was not echoed exactly.");
        }
        if (snapshot.Changed)
        {
            errors.Add("visual_evidence_export changed the drawing.");
        }
        if (snapshot.EntityHandles.Count != 0)
        {
            errors.Add("visual_evidence_export returned mutation entity handles.");
        }
        if (!string.Equals(request.EvidenceId, snapshot.EvidenceId, StringComparison.Ordinal))
        {
            errors.Add("evidence_id was not echoed exactly.");
        }
        if (!string.Equals(request.LatestMutationSha256, snapshot.LatestMutationSha256, StringComparison.Ordinal))
        {
            errors.Add("latest_mutation_sha256 was not echoed exactly.");
        }
        if (!string.Equals(request.VisualRunManifestSha256, snapshot.VisualRunManifestSha256, StringComparison.Ordinal))
        {
            errors.Add("visual_run_manifest_sha256 was not echoed exactly.");
        }
        if (!string.Equals(
                request.ArtifactPolicyVersion,
                VisualEvidenceArtifactPolicy.Version,
                StringComparison.Ordinal))
        {
            errors.Add("artifact_policy_version is not supported.");
        }
        var expectedRegionHash = VisualEvidenceProjection.CanonicalRegionConfigSha256(request.Region);
        if (!string.Equals(expectedRegionHash, snapshot.RegionConfigSha256, StringComparison.Ordinal))
        {
            errors.Add("region_config_sha256 does not match the requested region configuration.");
        }
        if (snapshot.Artifacts.Count != 3
            || snapshot.Artifacts.Select(artifact => artifact.Kind).ToHashSet(StringComparer.Ordinal)
                .SetEquals(new[] { "render", "entity-map", "measurements" }) is false)
        {
            errors.Add("visual_evidence_export must return exactly render, entity-map and measurements artifacts.");
        }
        return errors;
    }

    private static string? NormalizePath(string? path, ICollection<string> errors, string label)
    {
        if (path is null || !ContractValidator.TryNormalizeWindowsAbsolutePath(path, out var normalized))
        {
            errors.Add($"The {label} drawing path is not a valid absolute path.");
            return null;
        }
        return normalized;
    }
}
