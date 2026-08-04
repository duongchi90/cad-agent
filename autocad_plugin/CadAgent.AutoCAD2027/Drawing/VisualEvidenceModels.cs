using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
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
    IReadOnlyList<JsonElement> Measurements);

public sealed record EvidenceArtifactDescriptor(
    string ArtifactId,
    string Kind,
    string RelativePath,
    string Sha256,
    long ByteLength,
    string MimeType,
    int? Width = null,
    int? Height = null);

public sealed record SessionStateSnapshot(
    string DrawingFullPath,
    string DocumentIdentity,
    string CurrentLayout,
    bool ModelSpace,
    int Cvport,
    string CurrentLayer,
    string ViewProperties,
    IReadOnlyList<string> SelectionHandles,
    IReadOnlyDictionary<string, bool> LayerStates,
    IReadOnlyDictionary<string, string> RendererSystemVariables,
    string FingerprintSha256)
{
    public static SessionStateSnapshot Create(
        string drawingFullPath,
        string documentIdentity,
        string currentLayout,
        bool modelSpace,
        int cvport,
        string currentLayer,
        string viewProperties,
        IEnumerable<string> selectionHandles,
        IReadOnlyDictionary<string, bool> layerStates,
        IReadOnlyDictionary<string, string> rendererSystemVariables)
    {
        ArgumentNullException.ThrowIfNull(selectionHandles);
        ArgumentNullException.ThrowIfNull(layerStates);
        ArgumentNullException.ThrowIfNull(rendererSystemVariables);

        var normalizedPath = ContractValidator.NormalizeWindowsAbsolutePath(drawingFullPath);
        var canonical = new
        {
            drawing_full_path = normalizedPath,
            document_identity = documentIdentity,
            current_layout = currentLayout,
            model_space = modelSpace,
            cvport,
            current_layer = currentLayer,
            view_properties = viewProperties,
            selection_handles = selectionHandles.ToArray(),
            layer_states = layerStates.OrderBy(item => item.Key, StringComparer.Ordinal)
                .ToDictionary(item => item.Key, item => item.Value, StringComparer.Ordinal),
            renderer_system_variables = rendererSystemVariables.OrderBy(item => item.Key, StringComparer.Ordinal)
                .ToDictionary(item => item.Key, item => item.Value, StringComparer.Ordinal)
        };
        var bytes = JsonSerializer.SerializeToUtf8Bytes(canonical);
        return new SessionStateSnapshot(
            normalizedPath,
            documentIdentity,
            currentLayout,
            modelSpace,
            cvport,
            currentLayer,
            viewProperties,
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
