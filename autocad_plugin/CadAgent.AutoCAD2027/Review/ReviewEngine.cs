using System.Collections.ObjectModel;
using System.Text.Json;
using CadAgent.AutoCAD2027.Drawing;
using CadAgent.AutoCAD2027.Ipc;

namespace CadAgent.AutoCAD2027.Review;

public sealed class ReviewEngine
{
    private static readonly IReadOnlyDictionary<string, JsonElement> EmptyPayload =
        new ReadOnlyDictionary<string, JsonElement>(
            new Dictionary<string, JsonElement>(StringComparer.Ordinal));

    private readonly IDrawingGateway _drawingGateway;

    public ReviewEngine(IDrawingGateway drawingGateway)
    {
        _drawingGateway = drawingGateway ?? throw new ArgumentNullException(nameof(drawingGateway));
    }

    public ReviewResult Review(ReviewRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);

        var warnings = new List<string>();
        if (!TryNormalizeFullPath(request.DrawingFullPath, out var requestedPath, out var pathError))
        {
            return Failure(null, warnings, new[] { pathError });
        }

        if (!TryNormalizeFullPath(_drawingGateway.ActiveDocumentFullPath, out var activePath, out _))
        {
            return Failure(requestedPath, warnings, new[] { "No active document is available for review." });
        }

        if (!StringComparer.OrdinalIgnoreCase.Equals(requestedPath, activePath))
        {
            return Failure(
                activePath,
                warnings,
                new[] { "The requested drawing_full_path does not match the active document full path." });
        }

        if (request.Handles is null)
        {
            return Failure(activePath, warnings, new[] { "The review handles collection is required." });
        }

        var requestedHandles = NormalizeHandles(request.Handles, warnings);
        IReadOnlyList<EntitySnapshot> snapshots;
        try
        {
            snapshots = _drawingGateway.ReadEntities(requestedHandles) ?? Array.Empty<EntitySnapshot>();
        }
        catch (Exception exception)
        {
            return Failure(activePath, warnings, new[] { $"Unable to read drawing entities: {exception.Message}" });
        }

        var entitiesByHandle = IndexSnapshots(snapshots, warnings);
        var entities = new List<ReviewEntity>();
        foreach (var handle in requestedHandles)
        {
            if (!entitiesByHandle.TryGetValue(handle, out var snapshot))
            {
                warnings.Add($"Entity handle '{handle}' was not found.");
                continue;
            }

            if (!ReviewEntityTypes.TryNormalize(snapshot.Type, out var normalizedType))
            {
                var displayType = string.IsNullOrWhiteSpace(snapshot.Type) ? "<missing>" : snapshot.Type.Trim();
                warnings.Add($"Entity handle '{handle}' has unsupported type '{displayType}'.");
                continue;
            }

            entities.Add(new ReviewEntity(
                handle,
                normalizedType,
                snapshot.Layer?.Trim() ?? string.Empty,
                CopyGeometry(snapshot.Geometry)));
        }

        return new ReviewResult
        {
            Success = true,
            DrawingFullPath = activePath,
            Changed = false,
            EntityHandles = entities.Select(entity => entity.Handle).ToArray(),
            Entities = entities.ToArray(),
            Warnings = warnings.ToArray(),
            Errors = Array.Empty<string>(),
            Payload = new ReadOnlyDictionary<string, JsonElement>(
                new Dictionary<string, JsonElement>(StringComparer.Ordinal)
                {
                    ["entities"] = JsonSerializer.SerializeToElement(entities)
                })
        };
    }

    public static string NormalizeFullPath(string path)
    {
        if (!TryNormalizeFullPath(path, out var normalized, out var error))
        {
            throw new ArgumentException(error, nameof(path));
        }

        return normalized;
    }

    private static IReadOnlyList<string> NormalizeHandles(
        IReadOnlyList<string> handles,
        ICollection<string> warnings)
    {
        var normalized = new List<string>();
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var rawHandle in handles)
        {
            if (string.IsNullOrWhiteSpace(rawHandle))
            {
                warnings.Add("An empty entity handle was ignored.");
                continue;
            }

            var handle = rawHandle.Trim();
            if (seen.Add(handle))
            {
                normalized.Add(handle);
            }
        }

        return normalized;
    }

    private static Dictionary<string, EntitySnapshot> IndexSnapshots(
        IReadOnlyList<EntitySnapshot> snapshots,
        ICollection<string> warnings)
    {
        var indexed = new Dictionary<string, EntitySnapshot>(StringComparer.OrdinalIgnoreCase);
        foreach (var snapshot in snapshots
                     .Where(snapshot => snapshot is not null)
                     .OrderBy(snapshot => snapshot!.Handle, StringComparer.OrdinalIgnoreCase)
                     .ThenBy(snapshot => snapshot!.Type, StringComparer.OrdinalIgnoreCase)
                     .ThenBy(snapshot => snapshot!.Layer, StringComparer.OrdinalIgnoreCase))
        {
            if (string.IsNullOrWhiteSpace(snapshot.Handle))
            {
                warnings.Add("An entity was returned without a handle.");
                continue;
            }

            var handle = snapshot.Handle.Trim();
            if (!indexed.TryAdd(handle, snapshot))
            {
                warnings.Add($"Duplicate entity handle '{handle}' was returned; the first entity was used.");
            }
        }

        return indexed;
    }

    private static IReadOnlyDictionary<string, JsonElement> CopyGeometry(
        IReadOnlyDictionary<string, JsonElement>? geometry)
    {
        var copy = (geometry ?? new Dictionary<string, JsonElement>(StringComparer.Ordinal))
            .OrderBy(item => item.Key, StringComparer.Ordinal)
            .ToDictionary(item => item.Key, item => item.Value, StringComparer.Ordinal);
        return new ReadOnlyDictionary<string, JsonElement>(copy);
    }

    private static bool TryNormalizeFullPath(
        string? path,
        out string normalized,
        out string error)
    {
        normalized = string.Empty;
        error = "The drawing_full_path must be an absolute path.";
        if (string.IsNullOrWhiteSpace(path))
        {
            return false;
        }

        var candidate = path.Trim().Replace('/', '\\');
        if (!ContractValidator.TryNormalizeWindowsAbsolutePath(candidate, out normalized))
        {
            error = "The drawing_full_path is not a valid absolute path.";
            return false;
        }

        return true;
    }

    private static ReviewResult Failure(
        string? drawingFullPath,
        IEnumerable<string> warnings,
        IEnumerable<string> errors) =>
        new()
        {
            Success = false,
            DrawingFullPath = drawingFullPath,
            Changed = false,
            EntityHandles = Array.Empty<string>(),
            Entities = Array.Empty<ReviewEntity>(),
            Warnings = warnings.ToArray(),
            Errors = errors.ToArray(),
            Payload = EmptyPayload
        };
}
