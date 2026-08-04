using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using CadAgent.AutoCAD2027.Ipc;
using CadAgent.AutoCAD2027.Review;

namespace CadAgent.AutoCAD2027.Drawing;

public sealed record VisualEvidenceEntityRecord(
    string StableId,
    string Handle,
    string Type,
    string Layer,
    IReadOnlyDictionary<string, JsonElement> Geometry);

public sealed record VisualEvidenceMeasurementRecord(
    string Id,
    string Kind,
    JsonElement Reference,
    JsonElement? ToReference = null);

public static class VisualEvidenceProjection
{
    public static string CanonicalRegionConfigSha256(JsonElement region)
    {
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream))
        {
            WriteCanonical(region, writer);
        }

        return Convert.ToHexString(SHA256.HashData(stream.ToArray())).ToLowerInvariant();
    }

    public static IReadOnlyList<VisualEvidenceEntityRecord> ProjectEntities(
        IReadOnlyList<EntitySnapshot> snapshots)
    {
        ArgumentNullException.ThrowIfNull(snapshots);
        return snapshots
            .Where(snapshot => !string.IsNullOrWhiteSpace(snapshot.Handle))
            .Select(snapshot =>
            {
                var handle = snapshot.Handle!.Trim().ToUpperInvariant();
                var type = NormalizeEntityType(snapshot.Type);
                var layer = snapshot.Layer?.Trim() ?? string.Empty;
                var geometry = (snapshot.Geometry ?? new Dictionary<string, JsonElement>())
                    .OrderBy(item => item.Key, StringComparer.Ordinal)
                    .ToDictionary(item => item.Key, item => item.Value.Clone(), StringComparer.Ordinal);
                return new VisualEvidenceEntityRecord($"ENTITY:{handle}", handle, type, layer, geometry);
            })
            .OrderBy(entity => entity.Handle, StringComparer.Ordinal)
            .ThenBy(entity => entity.Type, StringComparer.Ordinal)
            .ThenBy(entity => entity.Layer, StringComparer.Ordinal)
            .ToArray();
    }

    public static IReadOnlyList<VisualEvidenceMeasurementRecord> ProjectMeasurements(
        IEnumerable<JsonElement> measurements)
    {
        ArgumentNullException.ThrowIfNull(measurements);
        return measurements
            .Select(measurement =>
            {
                if (measurement.ValueKind != JsonValueKind.Object
                    || !measurement.TryGetProperty("id", out var id)
                    || id.ValueKind != JsonValueKind.String
                    || string.IsNullOrWhiteSpace(id.GetString())
                    || !measurement.TryGetProperty("kind", out var kind)
                    || kind.ValueKind != JsonValueKind.String
                    || !measurement.TryGetProperty("reference", out var reference)
                    || reference.ValueKind != JsonValueKind.Object)
                {
                    throw new ArgumentException("Measurement evidence must contain id, kind and reference.", nameof(measurements));
                }

                JsonElement? toReference = null;
                if (measurement.TryGetProperty("to_reference", out var toReferenceValue))
                {
                    toReference = toReferenceValue.Clone();
                }

                return new VisualEvidenceMeasurementRecord(
                    id.GetString()!.Trim(),
                    kind.GetString()!.Trim().ToUpperInvariant(),
                    reference.Clone(),
                    toReference);
            })
            .OrderBy(measurement => measurement.Id, StringComparer.Ordinal)
            .ToArray();
    }

    private static string NormalizeEntityType(string? value)
    {
        if (ReviewEntityTypes.TryNormalize(value, out var normalized))
        {
            return normalized;
        }

        return (value ?? string.Empty).Trim().ToUpperInvariant();
    }

    private static void WriteCanonical(JsonElement value, Utf8JsonWriter writer)
    {
        switch (value.ValueKind)
        {
            case JsonValueKind.Object:
                writer.WriteStartObject();
                foreach (var property in value.EnumerateObject().OrderBy(item => item.Name, StringComparer.Ordinal))
                {
                    writer.WritePropertyName(property.Name);
                    WriteCanonical(property.Value, writer);
                }

                writer.WriteEndObject();
                break;
            case JsonValueKind.Array:
                writer.WriteStartArray();
                foreach (var item in value.EnumerateArray())
                {
                    WriteCanonical(item, writer);
                }

                writer.WriteEndArray();
                break;
            case JsonValueKind.String:
                writer.WriteStringValue(value.GetString());
                break;
            case JsonValueKind.Number:
                if (value.TryGetInt64(out var integer))
                {
                    writer.WriteNumberValue(integer);
                }
                else if (value.TryGetDecimal(out var decimalValue))
                {
                    writer.WriteNumberValue(decimalValue);
                }
                else
                {
                    writer.WriteRawValue(value.GetRawText(), skipInputValidation: true);
                }

                break;
            case JsonValueKind.True:
                writer.WriteBooleanValue(true);
                break;
            case JsonValueKind.False:
                writer.WriteBooleanValue(false);
                break;
            case JsonValueKind.Null:
                writer.WriteNullValue();
                break;
            default:
                throw new JsonException($"Unsupported JSON value kind {value.ValueKind}.");
        }
    }
}

public static class VisualEvidenceArtifactPolicy
{
    public const string Version = "vs-t3-artifacts-1";
    public const long MaxRenderBytes = 8 * 1024 * 1024;
    public const int MaxEntityRecords = 50_000;
    public const int MaxMeasurementRecords = 10_000;
    public const long MaxEntityMapBytes = 8 * 1024 * 1024;
    public const long MaxMeasurementBytes = 4 * 1024 * 1024;
    public const long MaxTotalArtifactBytes = 32 * 1024 * 1024;

    public static void Validate(string kind, string mimeType, long byteLength)
    {
        if (byteLength < 0)
        {
            throw new InvalidDataException("Artifact byte length cannot be negative.");
        }

        var limit = kind switch
        {
            "render" => MaxRenderBytes,
            "entity-map" => MaxEntityMapBytes,
            "measurements" => MaxMeasurementBytes,
            _ => throw new ArgumentException($"Unsupported VS-T3 artifact kind '{kind}'.", nameof(kind))
        };
        if (byteLength > limit)
        {
            throw new InvalidDataException($"Artifact kind '{kind}' exceeds its byte limit of {limit}.");
        }

        var expectedMimeType = kind == "render" ? "image/png" : "application/json";
        if (!string.Equals(mimeType, expectedMimeType, StringComparison.Ordinal))
        {
            throw new ArgumentException($"Artifact kind '{kind}' must use MIME type '{expectedMimeType}'.", nameof(mimeType));
        }
    }
}

public sealed class RequestOwnedArtifactStore : IDisposable
{
    private readonly string _ipcRoot;
    private readonly string _artifactDirectory;
    private long _totalBytes;
    private bool _disposed;

    private RequestOwnedArtifactStore(string ipcRoot, string artifactDirectory)
    {
        _ipcRoot = ipcRoot;
        _artifactDirectory = artifactDirectory;
    }

    public string ArtifactDirectory => _artifactDirectory;

    public IDisposable AcquireLease()
    {
        ThrowIfDisposed();
        var leasePath = Path.Combine(_artifactDirectory, "active.lease");
        var stream = new FileStream(
            leasePath,
            FileMode.CreateNew,
            FileAccess.Write,
            FileShare.None,
            128,
            FileOptions.WriteThrough);
        stream.Write(Encoding.UTF8.GetBytes(DateTimeOffset.UtcNow.ToString("O")));
        stream.Flush(flushToDisk: true);
        return new Lease(stream, leasePath);
    }

    public static RequestOwnedArtifactStore Create(
        string ipcRoot,
        string requestId,
        string artifactDirectory)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(ipcRoot);
        ContractValidator.EnsureRequestId(requestId);
        var normalizedRoot = Path.GetFullPath(ipcRoot);
        if (!Directory.Exists(normalizedRoot))
        {
            throw new DirectoryNotFoundException($"IPC root does not exist: {normalizedRoot}");
        }

        RejectReparsePoint(normalizedRoot);
        if (Path.IsPathRooted(artifactDirectory))
        {
            throw new ArgumentException("artifact_directory must be relative to the IPC root.", nameof(artifactDirectory));
        }

        var parts = artifactDirectory.Replace('\\', '/').Split('/', StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length == 0 || parts.Any(part => part is "." or ".."))
        {
            throw new ArgumentException("artifact_directory contains an unsafe path segment.", nameof(artifactDirectory));
        }

        if (!string.Equals(parts[^1], requestId, StringComparison.Ordinal))
        {
            throw new ArgumentException("artifact_directory must end with request_id.", nameof(artifactDirectory));
        }

        var fullDirectory = Path.GetFullPath(Path.Combine(normalizedRoot, Path.Combine(parts)));
        if (!IsWithin(normalizedRoot, fullDirectory))
        {
            throw new ArgumentException("artifact_directory escapes the IPC root.", nameof(artifactDirectory));
        }

        var parent = Directory.GetParent(fullDirectory)?.FullName;
        if (parent is null)
        {
            throw new DirectoryNotFoundException("The artifact parent directory does not exist.");
        }

        if (!Directory.Exists(parent))
        {
            Directory.CreateDirectory(parent);
        }

        RejectReparsePoint(parent);
        if (Directory.Exists(fullDirectory) || File.Exists(fullDirectory))
        {
            throw new IOException("The request-owned artifact directory already exists.");
        }

        Directory.CreateDirectory(fullDirectory);
        try
        {
            RejectReparsePoint(fullDirectory);
        }
        catch
        {
            Directory.Delete(fullDirectory, recursive: true);
            throw;
        }

        return new RequestOwnedArtifactStore(normalizedRoot, fullDirectory);
    }

    public EvidenceArtifactDescriptor Write(
        string kind,
        string fileName,
        string mimeType,
        ReadOnlySpan<byte> content,
        int? width = null,
        int? height = null)
    {
        ThrowIfDisposed();
        VisualEvidenceArtifactPolicy.Validate(kind, mimeType, content.Length);
        if (fileName.IndexOfAny(new[] { '/', '\\' }) >= 0
            || fileName is "." or ".."
            || string.IsNullOrWhiteSpace(fileName))
        {
            throw new ArgumentException("Artifact file name must be a single safe path component.", nameof(fileName));
        }

        var total = checked(_totalBytes + content.Length);
        if (total > VisualEvidenceArtifactPolicy.MaxTotalArtifactBytes)
        {
            throw new InvalidDataException("The request exceeds the total VS-T3 artifact byte limit.");
        }

        var path = Path.GetFullPath(Path.Combine(_artifactDirectory, fileName));
        if (!IsWithin(_artifactDirectory, path))
        {
            throw new ArgumentException("Artifact file escapes the request-owned directory.", nameof(fileName));
        }

        RejectReparsePoint(_artifactDirectory);
        using (var stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None, 64 * 1024, FileOptions.WriteThrough))
        {
            stream.Write(content);
            stream.Flush(flushToDisk: true);
        }

        var bytes = content.ToArray();
        _totalBytes = total;
        return new EvidenceArtifactDescriptor(
            $"{kind}:{fileName}",
            kind,
            Path.GetRelativePath(_ipcRoot, path).Replace(Path.DirectorySeparatorChar, '/'),
            Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),
            bytes.LongLength,
            mimeType,
            width,
            height);
    }

    public void CleanupOnFailure()
    {
        if (_disposed)
        {
            return;
        }

        RejectReparsePoint(_artifactDirectory);
        if (File.Exists(Path.Combine(_artifactDirectory, "active.lease")))
        {
            throw new IOException("The request-owned artifact directory still has an active lease.");
        }
        Directory.Delete(_artifactDirectory, recursive: true);
        _disposed = true;
    }

    public void Dispose()
    {
        _disposed = true;
    }

    private void ThrowIfDisposed()
    {
        if (_disposed)
        {
            throw new ObjectDisposedException(nameof(RequestOwnedArtifactStore));
        }
    }

    private static bool IsWithin(string root, string candidate)
    {
        var normalizedRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
            + Path.DirectorySeparatorChar;
        var normalizedCandidate = Path.GetFullPath(candidate).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
            + Path.DirectorySeparatorChar;
        return normalizedCandidate.StartsWith(normalizedRoot, StringComparison.OrdinalIgnoreCase);
    }

    private static void RejectReparsePoint(string path)
    {
        var attributes = File.GetAttributes(path);
        if ((attributes & FileAttributes.ReparsePoint) != 0)
        {
            throw new IOException($"Reparse points are not allowed in VS-T3 artifact paths: {path}");
        }
    }

    private sealed class Lease : IDisposable
    {
        private readonly FileStream _stream;
        private readonly string _path;
        private bool _disposed;

        public Lease(FileStream stream, string path)
        {
            _stream = stream;
            _path = path;
        }

        public void Dispose()
        {
            if (_disposed)
            {
                return;
            }

            _disposed = true;
            _stream.Dispose();
            if (File.Exists(_path))
            {
                File.Delete(_path);
            }
        }
    }
}
