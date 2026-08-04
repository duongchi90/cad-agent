using System.Text.Json;
using System.Text.RegularExpressions;

namespace CadAgent.AutoCAD2027.Ipc;

public sealed class ContractValidationResult
{
    public ContractValidationResult(IEnumerable<string> errors)
    {
        Errors = errors.ToArray();
    }

    public IReadOnlyList<string> Errors { get; }

    public bool IsValid => Errors.Count == 0;
}

public sealed class ContractValidationException : ArgumentException
{
    public ContractValidationException(IEnumerable<string> errors)
        : base(string.Join("; ", errors))
    {
        Errors = errors.ToArray();
    }

    public IReadOnlyList<string> Errors { get; }
}

public static class ContractValidator
{
    private static readonly Regex RequestIdPattern =
        new("^[A-Za-z0-9][A-Za-z0-9_-]*$", RegexOptions.CultureInvariant | RegexOptions.Compiled);

    private static readonly Regex Sha256Pattern =
        new("^[0-9a-fA-F]{64}$", RegexOptions.CultureInvariant | RegexOptions.Compiled);

    private static readonly Regex VisualEvidenceIdentifierPattern =
        new("^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$", RegexOptions.CultureInvariant | RegexOptions.Compiled);

    private static readonly Regex LowercaseSha256Pattern =
        new("^[0-9a-f]{64}$", RegexOptions.CultureInvariant | RegexOptions.Compiled);

    private static readonly Regex VisualEvidenceCapturedAtPattern =
        new("^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?Z$", RegexOptions.CultureInvariant | RegexOptions.Compiled);

    public static ContractValidationResult ValidateRequest(IpcRequest? request)
    {
        var errors = new List<string>();
        if (request is null)
        {
            errors.Add("request must not be null");
            return new ContractValidationResult(errors);
        }

        ValidateRequestId(request.RequestId, errors);
        if (!string.Equals(request.SchemaVersion, ContractConstants.SchemaVersion, StringComparison.Ordinal))
        {
            errors.Add($"schema_version must be {ContractConstants.SchemaVersion}");
        }

        if (request.Operation is null || !ContractConstants.SupportedOperations.Contains(request.Operation))
        {
            errors.Add("operation is not supported");
        }

        if (request.DrawingFullPath is null)
        {
            if (!string.Equals(request.Operation, "health", StringComparison.Ordinal))
            {
                errors.Add("drawing_full_path may be null only for health");
            }
        }
        else if (!TryNormalizeWindowsAbsolutePath(request.DrawingFullPath, out _))
        {
            errors.Add("drawing_full_path must be a full absolute Windows path");
        }

        if (request.DrawingSha256 is not null && !Sha256Pattern.IsMatch(request.DrawingSha256))
        {
            errors.Add("drawing_sha256 must be null or a 64-character hexadecimal SHA-256");
        }

        if (request.Approval.HasValue
            && request.Approval.Value.ValueKind is not (JsonValueKind.Object or JsonValueKind.Null))
        {
            errors.Add("approval must be an object or null");
        }

        if (request.Parameters is null)
        {
            errors.Add("parameters must be an object");
        }
        else if (string.Equals(request.Operation, "review", StringComparison.Ordinal))
        {
            ValidateReviewParameters(request.Parameters, errors);
        }
        else if (string.Equals(request.Operation, "health", StringComparison.Ordinal) && request.Parameters.Count != 0)
        {
            errors.Add("health parameters must be an empty object");
        }
        else if (string.Equals(request.Operation, "mechanical_bom", StringComparison.Ordinal)
            && request.Parameters.Count != 0)
        {
            errors.Add("mechanical_bom parameters must be an empty object");
        }
        else if (string.Equals(request.Operation, "drawing_setup_audit", StringComparison.Ordinal)
            && request.Parameters.Count != 0)
        {
            errors.Add("drawing_setup_audit parameters must be an empty object");
        }
        else if (string.Equals(request.Operation, "close_disposable", StringComparison.Ordinal))
        {
            ValidateDisposableParameters(request.Parameters, errors);
        }
        else if (string.Equals(request.Operation, "visual_evidence_export", StringComparison.Ordinal))
        {
            ValidateVisualEvidenceParameters(request, errors);
        }

        return new ContractValidationResult(errors);
    }

    public static ContractValidationResult ValidateResult(IpcResult? result)
    {
        var errors = new List<string>();
        if (result is null)
        {
            errors.Add("result must not be null");
            return new ContractValidationResult(errors);
        }

        ValidateRequestId(result.RequestId, errors);
        if (result.Operation is null || !ContractConstants.SupportedOperations.Contains(result.Operation))
        {
            errors.Add("operation is not supported");
        }

        if (result.DrawingFullPath is null)
        {
            if (!string.Equals(result.Operation, "health", StringComparison.Ordinal))
            {
                errors.Add("drawing_full_path may be null only for health");
            }
        }
        else if (!TryNormalizeWindowsAbsolutePath(result.DrawingFullPath, out _))
        {
            errors.Add("drawing_full_path must be a full absolute Windows path");
        }

        ValidateStringList(result.EntityHandles, "entity_handles", errors);
        ValidateStringList(result.Warnings, "warnings", errors);
        ValidateStringList(result.Errors, "errors", errors);
        if (string.Equals(result.Operation, "drawing_setup_audit", StringComparison.Ordinal)
            && (result.Changed || (result.EntityHandles?.Count ?? 0) != 0))
        {
            errors.Add("drawing_setup_audit results must be read-only and contain no entity handles");
        }
        if (string.Equals(result.Operation, "visual_evidence_export", StringComparison.Ordinal))
        {
            if (result.Changed || (result.EntityHandles?.Count ?? 0) != 0)
            {
                errors.Add("visual_evidence_export results must be read-only and contain no entity handles");
            }
            if (result.Success)
            {
                ValidateVisualEvidencePayload(result.Payload, errors);
            }
        }
        if (result.Payload is null)
        {
            errors.Add("payload must be an object when present");
        }
        if (result.StartedAt == default)
        {
            errors.Add("started_at is required");
        }

        if (result.CompletedAt == default)
        {
            errors.Add("completed_at is required");
        }
        else if (result.StartedAt != default && result.CompletedAt < result.StartedAt)
        {
            errors.Add("completed_at must not be before started_at");
        }

        return new ContractValidationResult(errors);
    }

    public static IpcRequest NormalizeRequest(IpcRequest request)
    {
        var validation = ValidateRequest(request);
        if (!validation.IsValid)
        {
            throw new ContractValidationException(validation.Errors);
        }

        return request with
        {
            DrawingFullPath = request.DrawingFullPath is null
                ? null
                : NormalizeWindowsAbsolutePath(request.DrawingFullPath)
        };
    }

    public static IpcResult NormalizeResult(IpcResult result)
    {
        var validation = ValidateResult(result);
        if (!validation.IsValid)
        {
            throw new ContractValidationException(validation.Errors);
        }

        return result with
        {
            DrawingFullPath = result.DrawingFullPath is null
                ? null
                : NormalizeWindowsAbsolutePath(result.DrawingFullPath)
        };
    }

    public static string NormalizeWindowsAbsolutePath(string path)
    {
        if (!TryNormalizeWindowsAbsolutePath(path, out var normalized))
        {
            throw new ArgumentException("The path must be a full absolute Windows path.", nameof(path));
        }

        return normalized;
    }

    public static bool TryNormalizeWindowsAbsolutePath(string? path, out string normalized)
    {
        normalized = string.Empty;
        if (string.IsNullOrWhiteSpace(path) || !IsAbsoluteWindowsPath(path))
        {
            return false;
        }

        try
        {
            normalized = Path.GetFullPath(path);
            if (normalized.Length > 3)
            {
                normalized = normalized.TrimEnd('\\');
            }

            return !string.IsNullOrWhiteSpace(normalized) && IsAbsoluteWindowsPath(normalized);
        }
        catch (ArgumentException)
        {
            return false;
        }
        catch (NotSupportedException)
        {
            return false;
        }
    }

    public static void EnsureRequestId(string? requestId)
    {
        var errors = new List<string>();
        ValidateRequestId(requestId, errors);
        if (errors.Count > 0)
        {
            throw new ArgumentException(string.Join("; ", errors), nameof(requestId));
        }
    }

    private static bool IsAbsoluteWindowsPath(string path)
    {
        if (!Path.IsPathFullyQualified(path))
        {
            return false;
        }

        if (path.Length >= 3 && char.IsLetter(path[0]) && path[1] == ':' && (path[2] == '\\' || path[2] == '/'))
        {
            return true;
        }

        return path.StartsWith("\\\\", StringComparison.Ordinal) && path.Length > 2;
    }

    private static void ValidateRequestId(string? requestId, ICollection<string> errors)
    {
        if (string.IsNullOrWhiteSpace(requestId))
        {
            errors.Add("request_id must not be empty");
            return;
        }

        if (requestId.Length > ContractConstants.MaxRequestIdLength || !RequestIdPattern.IsMatch(requestId))
        {
            errors.Add("request_id contains unsupported filename characters or is too long");
        }
    }

    private static void ValidateReviewParameters(
        IReadOnlyDictionary<string, JsonElement> parameters,
        ICollection<string> errors)
    {
        if (!parameters.TryGetValue("handles", out var handles) || handles.ValueKind != JsonValueKind.Array)
        {
            errors.Add("parameters.handles must be an array");
            return;
        }

        foreach (var handle in handles.EnumerateArray())
        {
            if (handle.ValueKind != JsonValueKind.String || string.IsNullOrWhiteSpace(handle.GetString()))
            {
                errors.Add("parameters.handles must contain non-empty strings");
                break;
            }
        }

        var values = handles.EnumerateArray()
            .Where(handle => handle.ValueKind == JsonValueKind.String)
            .Select(handle => handle.GetString()!)
            .ToArray();
        if (values.Length == 0)
        {
            errors.Add("parameters.handles must contain at least one handle");
        }
        else if (values.Length != values.Distinct(StringComparer.Ordinal).Count())
        {
            errors.Add("parameters.handles must not contain duplicates");
        }

        if (parameters.Keys.Any(key => !string.Equals(key, "handles", StringComparison.Ordinal)))
        {
            errors.Add("review parameters contain unsupported fields");
        }
    }

    private static void ValidateDisposableParameters(
        IReadOnlyDictionary<string, JsonElement> parameters,
        ICollection<string> errors)
    {
        if (!TryGetBoolean(parameters, "disposable", out var disposable) || !disposable)
        {
            errors.Add("parameters.disposable must be true");
        }

        if (!TryGetBoolean(parameters, "save_changes", out var saveChanges) || saveChanges)
        {
            errors.Add("parameters.save_changes must be false");
        }

        if (parameters.Keys.Any(key => key is not "disposable" and not "save_changes"))
        {
            errors.Add("close_disposable parameters contain unsupported fields");
        }
    }

    private static void ValidateVisualEvidenceParameters(
        IpcRequest request,
        ICollection<string> errors)
    {
        var parameters = request.Parameters!;
        var required = new HashSet<string>(StringComparer.Ordinal)
        {
            "run_id",
            "evidence_id",
            "region_id",
            "latest_mutation_sha256",
            "visual_run_manifest_sha256",
            "artifact_policy_version",
            "artifact_directory",
            "region",
            "measurements"
        };
        foreach (var missing in required.Except(parameters.Keys, StringComparer.Ordinal))
        {
            errors.Add($"visual_evidence_export parameters are missing '{missing}'");
        }
        foreach (var unsupported in parameters.Keys.Except(required, StringComparer.Ordinal))
        {
            errors.Add($"visual_evidence_export parameters contain unsupported field '{unsupported}'");
        }

        foreach (var name in new[] { "run_id", "evidence_id", "region_id" })
        {
            if (!TryGetString(parameters, name, out var value)
                || !VisualEvidenceIdentifierPattern.IsMatch(value))
            {
                errors.Add($"parameters.{name} must be a stable identifier");
            }
        }
        foreach (var name in new[] { "latest_mutation_sha256", "visual_run_manifest_sha256" })
        {
            if (!TryGetString(parameters, name, out var value)
                || !LowercaseSha256Pattern.IsMatch(value))
            {
                errors.Add($"parameters.{name} must be a lowercase SHA-256");
            }
        }

        if (!TryGetString(parameters, "artifact_policy_version", out var policy)
            || !string.Equals(policy, "vs-t3-artifacts-1", StringComparison.Ordinal))
        {
            errors.Add("parameters.artifact_policy_version must be vs-t3-artifacts-1");
        }
        if (TryGetString(parameters, "artifact_directory", out var artifactDirectory)
            && !IsSafeRelativePath(artifactDirectory))
        {
            errors.Add("parameters.artifact_directory must be a safe relative path");
        }

        if (!parameters.TryGetValue("region", out var region)
            || region.ValueKind != JsonValueKind.Object)
        {
            errors.Add("parameters.region must be an object");
        }
        else
        {
            ValidateVisualEvidenceRegion(region, errors);
        }

        if (!parameters.TryGetValue("measurements", out var measurements)
            || measurements.ValueKind != JsonValueKind.Array)
        {
            errors.Add("parameters.measurements must be an array");
        }
        else
        {
            ValidateVisualEvidenceMeasurements(measurements, errors);
        }

    }

    private static void ValidateVisualEvidenceRegion(
        JsonElement region,
        ICollection<string> errors)
    {
        var required = new HashSet<string>(StringComparer.Ordinal)
        {
            "model_bbox_mm",
            "pixel_size",
            "background",
            "include_layers",
            "exclude_layers"
        };
        ValidateClosedObject(region, required, "parameters.region", errors);
        if (!TryGetArray(region, "model_bbox_mm", out var bbox) || bbox.GetArrayLength() != 4
            || bbox.EnumerateArray().Any(value => value.ValueKind is not (JsonValueKind.Number)))
        {
            errors.Add("parameters.region.model_bbox_mm must contain four numbers");
        }
        if (!TryGetArray(region, "pixel_size", out var pixelSize) || pixelSize.GetArrayLength() != 2
            || pixelSize.EnumerateArray().Any(value => value.ValueKind != JsonValueKind.Number
                || !value.TryGetInt32(out var size) || size is < 1 or > 8192))
        {
            errors.Add("parameters.region.pixel_size must contain two positive integers");
        }
        if (!TryGetString(region, "background", out var background)
            || background is not ("WHITE" or "BLACK"))
        {
            errors.Add("parameters.region.background is unsupported");
        }
        foreach (var field in new[] { "include_layers", "exclude_layers" })
        {
            if (!TryGetArray(region, field, out var layers)
                || layers.EnumerateArray().Any(value => value.ValueKind != JsonValueKind.String
                    || string.IsNullOrWhiteSpace(value.GetString())))
            {
                errors.Add($"parameters.region.{field} must contain layer names");
            }
            else
            {
                var values = layers.EnumerateArray().Select(value => value.GetString()!).ToArray();
                if (values.Length != values.Distinct(StringComparer.Ordinal).Count())
                {
                    errors.Add($"parameters.region.{field} must contain unique layer names");
                }
            }
        }
    }

    private static void ValidateVisualEvidenceMeasurements(
        JsonElement measurements,
        ICollection<string> errors)
    {
        if (measurements.GetArrayLength() > 10000)
        {
            errors.Add("parameters.measurements must contain at most 10000 items");
        }
        var ids = new HashSet<string>(StringComparer.Ordinal);
        foreach (var measurement in measurements.EnumerateArray())
        {
            if (measurement.ValueKind != JsonValueKind.Object)
            {
                errors.Add("parameters.measurements entries must be objects");
                continue;
            }
            var required = new HashSet<string>(StringComparer.Ordinal) { "id", "kind", "reference" };
            ValidateClosedObject(measurement, required, "parameters.measurements entry", errors, "to_reference");
            if (!TryGetString(measurement, "id", out var id)
                || !VisualEvidenceIdentifierPattern.IsMatch(id))
            {
                errors.Add("parameters.measurements.id must be a stable identifier");
            }
            else if (!ids.Add(id))
            {
                errors.Add("parameters.measurements ids must be unique");
            }
            if (!TryGetString(measurement, "kind", out var kind)
                || kind is not ("DISTANCE" or "ANGLE" or "RADIUS" or "DIAMETER" or "BOUNDING_BOX"))
            {
                errors.Add("parameters.measurements.kind is unsupported");
            }
            if (!TryGetProperty(measurement, "reference", out var reference))
            {
                errors.Add("parameters.measurements.reference is required");
            }
            else
            {
                ValidateVisualEvidenceReference(reference, errors);
            }
            if (TryGetProperty(measurement, "to_reference", out var toReference))
            {
                ValidateVisualEvidenceReference(toReference, errors);
            }
        }
    }

    private static void ValidateVisualEvidenceReference(
        JsonElement reference,
        ICollection<string> errors)
    {
        if (reference.ValueKind != JsonValueKind.Object)
        {
            errors.Add("measurement references must be objects");
            return;
        }
        ValidateClosedObject(reference, new HashSet<string>(StringComparer.Ordinal) { "type", "id" }, "measurement reference", errors);
        if (!TryGetString(reference, "type", out var type) || type is not "ENTITY")
        {
            errors.Add("measurement reference type is unsupported");
        }
        if (!TryGetString(reference, "id", out var id) || !VisualEvidenceIdentifierPattern.IsMatch(id))
        {
            errors.Add("measurement reference id must be a stable identifier");
        }
    }

    private static void ValidateVisualEvidencePayload(
        IReadOnlyDictionary<string, JsonElement>? payload,
        ICollection<string> errors)
    {
        if (payload is null)
        {
            errors.Add("visual_evidence_export payload must be an object");
            return;
        }
        var required = new HashSet<string>(StringComparer.Ordinal)
        {
            "run_id",
            "evidence_id",
            "region_id",
            "drawing_sha256_before",
            "drawing_sha256_after",
            "dbmod_before",
            "dbmod_after",
            "latest_mutation_sha256",
            "visual_run_manifest_sha256",
            "region_config_sha256",
            "session_state_sha256_before",
            "session_state_sha256_after",
            "transient_state_restored",
            "captured_at_utc",
            "artifacts"
        };
        foreach (var missing in required.Except(payload.Keys, StringComparer.Ordinal))
        {
            errors.Add($"visual evidence payload is missing '{missing}'");
        }
        foreach (var unsupported in payload.Keys.Except(required, StringComparer.Ordinal))
        {
            errors.Add($"visual evidence payload contains unsupported field '{unsupported}'");
        }
        foreach (var name in new[] { "run_id", "evidence_id", "region_id" })
        {
            if (!TryGetString(payload, name, out var value) || !VisualEvidenceIdentifierPattern.IsMatch(value))
            {
                errors.Add($"visual evidence payload {name} is invalid");
            }
        }
        foreach (var name in new[]
        {
            "drawing_sha256_before", "drawing_sha256_after", "latest_mutation_sha256",
            "visual_run_manifest_sha256", "region_config_sha256", "session_state_sha256_before",
            "session_state_sha256_after"
        })
        {
            if (!TryGetString(payload, name, out var value) || !LowercaseSha256Pattern.IsMatch(value))
            {
                errors.Add($"visual evidence payload {name} is invalid");
            }
        }
        if (TryGetString(payload, "drawing_sha256_before", out var before)
            && TryGetString(payload, "drawing_sha256_after", out var after)
            && !string.Equals(before, after, StringComparison.Ordinal))
        {
            errors.Add("visual evidence drawing hashes must be equal");
        }
        if (TryGetInt64(payload, "dbmod_before", out var dbmodBefore)
            && TryGetInt64(payload, "dbmod_after", out var dbmodAfter)
            && dbmodBefore != dbmodAfter)
        {
            errors.Add("visual evidence DBMOD values must be equal");
        }
        if (TryGetString(payload, "session_state_sha256_before", out var stateBefore)
            && TryGetString(payload, "session_state_sha256_after", out var stateAfter)
            && !string.Equals(stateBefore, stateAfter, StringComparison.Ordinal))
        {
            errors.Add("visual evidence session-state hashes must be equal");
        }
        if (!TryGetBoolean(payload, "transient_state_restored", out var restored) || !restored)
        {
            errors.Add("visual evidence transient state was not restored");
        }
        if (!TryGetString(payload, "captured_at_utc", out var capturedAt)
            || !VisualEvidenceCapturedAtPattern.IsMatch(capturedAt))
        {
            errors.Add("visual evidence captured_at_utc must be RFC3339 UTC");
        }
        if (!TryGetProperty(payload, "artifacts", out var artifacts)
            || artifacts.ValueKind != JsonValueKind.Array
            || artifacts.GetArrayLength() != 3)
        {
            errors.Add("visual evidence must contain exactly three artifacts");
        }
        else
        {
            var kinds = new HashSet<string>(StringComparer.Ordinal);
            foreach (var artifact in artifacts.EnumerateArray())
            {
                ValidateVisualEvidenceArtifact(artifact, kinds, errors);
            }
        }
    }

    private static bool TryGetString(
        IReadOnlyDictionary<string, JsonElement> values,
        string name,
        out string value)
    {
        value = string.Empty;
        return values.TryGetValue(name, out var element)
            && element.ValueKind == JsonValueKind.String
            && (value = element.GetString() ?? string.Empty).Length > 0;
    }

    private static bool TryGetString(JsonElement value, string name, out string text)
    {
        text = string.Empty;
        return value.ValueKind == JsonValueKind.Object
            && value.TryGetProperty(name, out var element)
            && element.ValueKind == JsonValueKind.String
            && (text = element.GetString() ?? string.Empty).Length > 0;
    }

    private static bool TryGetProperty(
        IReadOnlyDictionary<string, JsonElement> values,
        string name,
        out JsonElement value) => values.TryGetValue(name, out value);

    private static bool TryGetProperty(JsonElement value, string name, out JsonElement property)
    {
        property = default;
        return value.ValueKind == JsonValueKind.Object
            && value.TryGetProperty(name, out property);
    }

    private static bool TryGetArray(JsonElement value, string name, out JsonElement array)
    {
        array = default;
        return TryGetProperty(value, name, out array) && array.ValueKind == JsonValueKind.Array;
    }

    private static bool TryGetInt64(
        IReadOnlyDictionary<string, JsonElement> values,
        string name,
        out long number)
    {
        number = 0;
        return values.TryGetValue(name, out var value)
            && value.ValueKind == JsonValueKind.Number
            && value.TryGetInt64(out number)
            && number >= 0;
    }

    private static bool TryGetInt64(JsonElement value, string name, out long number)
    {
        number = 0;
        return TryGetProperty(value, name, out var property)
            && property.ValueKind == JsonValueKind.Number
            && property.TryGetInt64(out number)
            && number >= 0;
    }

    private static bool TryGetBoolean(
        IReadOnlyDictionary<string, JsonElement> values,
        string name,
        out bool value)
    {
        value = false;
        if (!values.TryGetValue(name, out var element)
            || (element.ValueKind != JsonValueKind.True && element.ValueKind != JsonValueKind.False))
        {
            return false;
        }

        value = element.GetBoolean();
        return true;
    }

    private static void ValidateClosedObject(
        JsonElement value,
        IReadOnlySet<string> required,
        string displayName,
        ICollection<string> errors,
        params string[] optional)
    {
        if (value.ValueKind != JsonValueKind.Object)
        {
            errors.Add($"{displayName} must be an object");
            return;
        }
        var allowed = new HashSet<string>(required, StringComparer.Ordinal);
        allowed.UnionWith(optional);
        var present = value.EnumerateObject().Select(property => property.Name).ToHashSet(StringComparer.Ordinal);
        foreach (var missing in required.Except(present, StringComparer.Ordinal))
        {
            errors.Add($"{displayName} is missing '{missing}'");
        }
        foreach (var unsupported in present.Except(allowed, StringComparer.Ordinal))
        {
            errors.Add($"{displayName} contains unsupported field '{unsupported}'");
        }
    }

    private static bool IsSafeRelativePath(string path)
    {
        if (string.IsNullOrWhiteSpace(path)
            || path[0] is '/' or '\\'
            || (path.Length >= 2 && char.IsLetter(path[0]) && path[1] == ':'))
        {
            return false;
        }
        var parts = path.Replace('\\', '/').Split('/');
        return parts.All(part => part is not ("" or "." or ".."));
    }

    private static void ValidateVisualEvidenceArtifact(
        JsonElement artifact,
        ISet<string> kinds,
        ICollection<string> errors)
    {
        if (artifact.ValueKind != JsonValueKind.Object)
        {
            errors.Add("visual evidence artifacts must be objects");
            return;
        }
        var required = new HashSet<string>(StringComparer.Ordinal)
        {
            "artifact_id", "kind", "relative_path", "sha256", "byte_length", "mime_type"
        };
        ValidateClosedObject(artifact, required, "visual evidence artifact", errors, "width", "height");
        if (!TryGetString(artifact, "artifact_id", out var artifactId)
            || !VisualEvidenceIdentifierPattern.IsMatch(artifactId))
        {
            errors.Add("visual evidence artifact_id is invalid");
        }
        if (!TryGetString(artifact, "kind", out var kind)
            || kind is not ("render" or "entity_map" or "measurements"))
        {
            errors.Add("visual evidence artifact kind is unsupported");
        }
        else if (!kinds.Add(kind))
        {
            errors.Add("visual evidence artifact kinds must be unique");
        }
        if (TryGetString(artifact, "relative_path", out var relativePath)
            && !IsSafeRelativePath(relativePath))
        {
            errors.Add("visual evidence artifact path is unsafe");
        }
        if (!TryGetString(artifact, "sha256", out var hash) || !LowercaseSha256Pattern.IsMatch(hash))
        {
            errors.Add("visual evidence artifact hash is invalid");
        }
        if (!TryGetInt64(artifact, "byte_length", out var byteLength)
            || byteLength is < 1 or > 33554432)
        {
            errors.Add("visual evidence artifact byte_length is invalid");
        }
        if (!TryGetString(artifact, "mime_type", out var mimeType)
            || mimeType is not ("image/png" or "application/json"))
        {
            errors.Add("visual evidence artifact MIME type is unsupported");
        }
    }

    private static void ValidateStringList(
        IReadOnlyCollection<string>? values,
        string fieldName,
        ICollection<string> errors)
    {
        if (values is null)
        {
            errors.Add($"{fieldName} must be an array");
            return;
        }

        if (values.Any(value => value is null
            || (string.Equals(fieldName, "entity_handles", StringComparison.Ordinal) && value.Length == 0)))
        {
            errors.Add(fieldName == "entity_handles"
                ? $"{fieldName} must contain non-empty strings"
                : $"{fieldName} must contain strings");
        }
    }
}
