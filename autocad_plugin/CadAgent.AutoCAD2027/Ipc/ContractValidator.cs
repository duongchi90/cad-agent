using System.Globalization;
using System.Text.Json;
using System.Text.RegularExpressions;
using CadAgent.AutoCAD2027.Drawing;

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

    private static readonly Regex NativeRenderTimestampPattern =
        new("^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?Z$", RegexOptions.CultureInvariant | RegexOptions.Compiled);

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
        else if (string.Equals(request.Operation, "native_render_evidence", StringComparison.Ordinal))
        {
            ValidateNativeRenderEvidenceRequest(request, errors);
        }

        if (request.Operation is ExactBaseXrefOperationNames.Inspection
            or ExactBaseXrefOperationNames.Extraction)
        {
            ExactBaseXrefPolicy.ValidateRequestShape(request, errors);
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
        if (string.Equals(result.Operation, "native_render_evidence", StringComparison.Ordinal))
        {
            if (result.Changed || (result.EntityHandles?.Count ?? 0) != 0)
            {
                errors.Add("native_render_evidence results must be read-only and contain no entity handles");
            }
            if (result.Success)
            {
                ValidateNativeRenderEvidencePayload(result.Payload, null, errors);
            }
            else if (result.Payload is not null && result.Payload.Count != 0)
            {
                errors.Add("native_render_evidence failure results must contain an empty payload");
            }
        }
        if (string.Equals(result.Operation, ExactBaseXrefOperationNames.Inspection, StringComparison.Ordinal))
        {
            if (result.Changed || (result.EntityHandles?.Count ?? 0) != 0)
            {
                errors.Add("exact_base_xref_inspection results must be read-only and contain no entity handles");
            }
        }
        if (string.Equals(result.Operation, ExactBaseXrefOperationNames.Extraction, StringComparison.Ordinal))
        {
            if (!result.Success && (result.Changed || (result.EntityHandles?.Count ?? 0) != 0))
            {
                errors.Add("exact_base_xref_extraction failure results must be unchanged and contain no entity handles");
            }
            if (result.Success && !result.Changed)
            {
                errors.Add("successful exact_base_xref_extraction results must report changed=true");
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

    private static void ValidateNativeRenderEvidenceRequest(
        IpcRequest request,
        ICollection<string> errors)
    {
        if (request.DrawingSha256 is null || !LowercaseSha256Pattern.IsMatch(request.DrawingSha256))
        {
            errors.Add("native_render_evidence drawing_sha256 must be a lowercase SHA-256");
        }
        if (request.Approval.HasValue && request.Approval.Value.ValueKind != JsonValueKind.Null)
        {
            errors.Add("native_render_evidence approval is not allowed");
        }

        var parameters = request.Parameters!;
        var required = new HashSet<string>(StringComparer.Ordinal)
        {
            "run_id",
            "latest_mutation_sha256",
            "visual_run_manifest_sha256",
            "layout",
            "artifact_kind",
            "render_options",
            "requested_at"
        };
        foreach (var missing in required.Except(parameters.Keys, StringComparer.Ordinal))
        {
            errors.Add($"native_render_evidence parameters are missing '{missing}'");
        }
        foreach (var unsupported in parameters.Keys.Except(required, StringComparer.Ordinal))
        {
            errors.Add($"native_render_evidence parameters contain unsupported field '{unsupported}'");
        }

        if (!TryGetString(parameters, "run_id", out var runId)
            || !IsNativeRenderString(runId, identifier: true))
        {
            errors.Add("native_render_evidence parameters.run_id is invalid");
        }
        foreach (var name in new[] { "latest_mutation_sha256", "visual_run_manifest_sha256" })
        {
            if (!TryGetString(parameters, name, out var hash) || !LowercaseSha256Pattern.IsMatch(hash))
            {
                errors.Add($"native_render_evidence parameters.{name} must be a lowercase SHA-256");
            }
        }
        if (TryGetProperty(parameters, "layout", out var layout))
        {
            ValidateNativeRenderLayout(layout, "native_render_evidence parameters.layout", errors);
        }
        if (!TryGetString(parameters, "artifact_kind", out var artifactKind)
            || artifactKind is not ("PNG" or "PDF"))
        {
            errors.Add("native_render_evidence parameters.artifact_kind must be PNG or PDF");
        }
        if (TryGetProperty(parameters, "render_options", out var renderOptions))
        {
            ValidateNativeRenderOptions(
                renderOptions,
                "native_render_evidence parameters.render_options",
                errors);
        }
        if (!TryGetString(parameters, "requested_at", out var requestedAt)
            || !IsNativeRenderTimestamp(requestedAt))
        {
            errors.Add("native_render_evidence parameters.requested_at must be UTC");
        }
    }

    private static void ValidateNativeRenderLayout(
        JsonElement layout,
        string displayName,
        ICollection<string> errors)
    {
        var required = new HashSet<string>(StringComparer.Ordinal) { "identity", "name" };
        ValidateClosedObject(layout, required, displayName, errors);
        if (!TryGetString(layout, "identity", out var identity)
            || !IsNativeRenderString(identity, identifier: true))
        {
            errors.Add($"{displayName}.identity is invalid");
        }
        if (!TryGetString(layout, "name", out var name)
            || !IsNativeRenderString(name))
        {
            errors.Add($"{displayName}.name is invalid");
        }
    }

    private static void ValidateNativeRenderOptions(
        JsonElement options,
        string displayName,
        ICollection<string> errors)
    {
        var required = new HashSet<string>(StringComparer.Ordinal)
        {
            "background", "dpi", "fit_to_paper", "paper_size", "plot_style"
        };
        ValidateClosedObject(options, required, displayName, errors);
        if (!TryGetString(options, "background", out var background)
            || background is not ("black" or "white"))
        {
            errors.Add($"{displayName}.background is unsupported");
        }
        if (!TryGetInt64(options, "dpi", out var dpi) || dpi is < 1 or > 2400)
        {
            errors.Add($"{displayName}.dpi is invalid");
        }
        if (!TryGetBoolean(options, "fit_to_paper", out _))
        {
            errors.Add($"{displayName}.fit_to_paper must be a boolean");
        }
        foreach (var name in new[] { "paper_size", "plot_style" })
        {
            if (!TryGetString(options, name, out var value) || !IsNativeRenderString(value))
            {
                errors.Add($"{displayName}.{name} is invalid");
            }
        }
    }

    private static bool IsNativeRenderString(string value, bool identifier = false) =>
        value.Length is > 0 and <= 512
        && value.All(character => character >= ' ' && character != '\u007f')
        && (!identifier || VisualEvidenceIdentifierPattern.IsMatch(value));

    private static bool IsNativeRenderTimestamp(string value)
    {
        if (!NativeRenderTimestampPattern.IsMatch(value))
        {
            return false;
        }

        return DateTimeOffset.TryParseExact(
            value,
            new[] { "yyyy-MM-dd'T'HH:mm:ss'Z'", "yyyy-MM-dd'T'HH:mm:ss.FFFFFF'Z'" },
            CultureInfo.InvariantCulture,
            DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal,
            out _);
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
            "measurements",
            "datum_bindings"
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
            var datumBindingIds = ValidateVisualEvidenceDatumBindings(request, errors);
            ValidateVisualEvidenceMeasurements(measurements, datumBindingIds, errors);
        }
    }

    private static HashSet<string> ValidateVisualEvidenceDatumBindings(
        IpcRequest request,
        ICollection<string> errors)
    {
        var ids = new HashSet<string>(StringComparer.Ordinal);
        if (!request.Parameters!.TryGetValue("datum_bindings", out var bindings)
            || bindings.ValueKind != JsonValueKind.Array)
        {
            errors.Add("parameters.datum_bindings must be an array");
            return ids;
        }

        if (bindings.GetArrayLength() > 10000)
        {
            errors.Add("parameters.datum_bindings must contain at most 10000 items");
        }

        foreach (var binding in bindings.EnumerateArray())
        {
            if (binding.ValueKind != JsonValueKind.Object)
            {
                errors.Add("parameters.datum_bindings entries must be objects");
                continue;
            }

            var required = new HashSet<string>(StringComparer.Ordinal)
            {
                "id",
                "entity_handle",
                "run_id",
                "region_id",
                "visual_run_manifest_sha256",
                "dimension_register_sha256",
                "dimension_id",
                "approval"
            };
            ValidateClosedObject(binding, required, "parameters.datum_bindings entry", errors);

            if (!TryGetString(binding, "id", out var id)
                || !VisualEvidenceIdentifierPattern.IsMatch(id))
            {
                errors.Add("parameters.datum_bindings.id must be a stable identifier");
            }
            else if (!ids.Add(id))
            {
                errors.Add("parameters.datum_bindings ids must be unique");
            }

            foreach (var name in new[] { "entity_handle", "run_id", "region_id", "dimension_id" })
            {
                if (!TryGetString(binding, name, out var value)
                    || !VisualEvidenceIdentifierPattern.IsMatch(value))
                {
                    errors.Add($"parameters.datum_bindings.{name} is invalid");
                }
            }

            foreach (var name in new[] { "visual_run_manifest_sha256", "dimension_register_sha256" })
            {
                if (!TryGetString(binding, name, out var value)
                    || !LowercaseSha256Pattern.IsMatch(value))
                {
                    errors.Add($"parameters.datum_bindings.{name} must be a lowercase SHA-256");
                }
            }

            if (!TryGetString(binding, "approval", out var approval)
                || !string.Equals(approval, "DIMENSION_REGISTER_CONFIRMED", StringComparison.Ordinal))
            {
                errors.Add("parameters.datum_bindings.approval is not approved");
            }

            if (TryGetString(request.Parameters!, "run_id", out var requestRunId)
                && TryGetString(binding, "run_id", out var bindingRunId)
                && !string.Equals(requestRunId, bindingRunId, StringComparison.Ordinal))
            {
                errors.Add("parameters.datum_bindings.run_id does not match the request");
            }
            if (TryGetString(request.Parameters!, "region_id", out var requestRegionId)
                && TryGetString(binding, "region_id", out var bindingRegionId)
                && !string.Equals(requestRegionId, bindingRegionId, StringComparison.Ordinal))
            {
                errors.Add("parameters.datum_bindings.region_id does not match the request");
            }
            if (TryGetString(request.Parameters!, "visual_run_manifest_sha256", out var requestManifestSha256)
                && TryGetString(binding, "visual_run_manifest_sha256", out var bindingManifestSha256)
                && !string.Equals(requestManifestSha256, bindingManifestSha256, StringComparison.Ordinal))
            {
                errors.Add("parameters.datum_bindings.visual_run_manifest_sha256 does not match the request");
            }
        }

        return ids;
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
        IReadOnlySet<string> datumBindingIds,
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
                ValidateVisualEvidenceReference(reference, datumBindingIds, errors);
            }
            if (TryGetProperty(measurement, "to_reference", out var toReference))
            {
                ValidateVisualEvidenceReference(toReference, datumBindingIds, errors);
            }
        }
    }

    private static void ValidateVisualEvidenceReference(
        JsonElement reference,
        IReadOnlySet<string> datumBindingIds,
        ICollection<string> errors)
    {
        if (reference.ValueKind != JsonValueKind.Object)
        {
            errors.Add("measurement references must be objects");
            return;
        }
        ValidateClosedObject(reference, new HashSet<string>(StringComparer.Ordinal) { "type", "id" }, "measurement reference", errors);
        if (!TryGetString(reference, "type", out var type) || type is not ("ENTITY" or "DATUM"))
        {
            errors.Add("measurement reference type is unsupported");
        }
        else if (type == "DATUM"
            && (!TryGetString(reference, "id", out var datumId) || !datumBindingIds.Contains(datumId)))
        {
            errors.Add("measurement DATUM reference is not provenance-bound");
        }

        if (!TryGetString(reference, "id", out var id) || !VisualEvidenceIdentifierPattern.IsMatch(id))
        {
            errors.Add("measurement reference id must be a stable identifier");
        }
    }

    private static void ValidateNativeRenderEvidencePayload(
        IReadOnlyDictionary<string, JsonElement>? payload,
        IpcRequest? request,
        ICollection<string> errors)
    {
        if (payload is null)
        {
            errors.Add("native_render_evidence payload must be an object");
            return;
        }

        var required = new HashSet<string>(StringComparer.Ordinal)
        {
            "schema_version",
            "request_id",
            "run_id",
            "drawing_sha256",
            "latest_mutation_sha256",
            "visual_run_manifest_sha256",
            "layout",
            "artifact_kind",
            "render_options",
            "renderer",
            "artifact",
            "capture_timestamp",
            "changed",
            "dbmod_before",
            "dbmod_after",
            "warnings"
        };
        foreach (var missing in required.Except(payload.Keys, StringComparer.Ordinal))
        {
            errors.Add($"native_render_evidence payload is missing '{missing}'");
        }
        foreach (var unsupported in payload.Keys.Except(required, StringComparer.Ordinal))
        {
            errors.Add($"native_render_evidence payload contains unsupported field '{unsupported}'");
        }

        if (!TryGetString(payload, "schema_version", out var schemaVersion)
            || !string.Equals(schemaVersion, "autocad-native-render-evidence-1.0", StringComparison.Ordinal))
        {
            errors.Add("native_render_evidence payload schema_version is unsupported");
        }
        foreach (var name in new[] { "request_id", "run_id" })
        {
            if (!TryGetString(payload, name, out var identifier)
                || !IsNativeRenderString(identifier, identifier: true))
            {
                errors.Add($"native_render_evidence payload {name} is invalid");
            }
        }
        foreach (var name in new[]
        {
            "drawing_sha256", "latest_mutation_sha256", "visual_run_manifest_sha256"
        })
        {
            if (!TryGetString(payload, name, out var hash) || !LowercaseSha256Pattern.IsMatch(hash))
            {
                errors.Add($"native_render_evidence payload {name} must be a lowercase SHA-256");
            }
        }
        if (TryGetProperty(payload, "layout", out var layout))
        {
            ValidateNativeRenderLayout(layout, "native_render_evidence payload.layout", errors);
        }
        if (!TryGetString(payload, "artifact_kind", out var artifactKind)
            || artifactKind is not ("PNG" or "PDF"))
        {
            errors.Add("native_render_evidence payload.artifact_kind must be PNG or PDF");
        }
        if (TryGetProperty(payload, "render_options", out var renderOptions))
        {
            ValidateNativeRenderOptions(
                renderOptions,
                "native_render_evidence payload.render_options",
                errors);
        }
        if (!TryGetString(payload, "renderer", out var renderer)
            || !string.Equals(renderer, "AUTOCAD_NATIVE", StringComparison.Ordinal))
        {
            errors.Add("native_render_evidence payload.renderer must be AUTOCAD_NATIVE");
        }
        if (TryGetProperty(payload, "artifact", out var artifact)
            && (artifactKind is "PNG" or "PDF"))
        {
            ValidateNativeRenderArtifact(artifact, artifactKind, errors);
        }
        if (!TryGetString(payload, "capture_timestamp", out var captureTimestamp)
            || !IsNativeRenderTimestamp(captureTimestamp))
        {
            errors.Add("native_render_evidence payload.capture_timestamp must be UTC");
        }
        if (!TryGetBoolean(payload, "changed", out var changed) || changed)
        {
            errors.Add("native_render_evidence payload.changed must be false");
        }
        if (!TryGetInt64(payload, "dbmod_before", out var dbmodBefore)
            || !TryGetInt64(payload, "dbmod_after", out var dbmodAfter)
            || dbmodBefore < 0
            || dbmodAfter < 0)
        {
            errors.Add("native_render_evidence payload DBMOD values must be non-negative integers");
        }
        else if (dbmodBefore != dbmodAfter)
        {
            errors.Add("native_render_evidence payload DBMOD values must be equal");
        }
        if (!TryGetArray(payload, "warnings", out var warnings)
            || warnings.EnumerateArray().Any(value =>
                value.ValueKind != JsonValueKind.String
                || !IsNativeRenderString(value.GetString() ?? string.Empty)))
        {
            errors.Add("native_render_evidence payload.warnings must be an array of strings");
        }

        if (request is not null)
        {
            ValidateNativeRenderPayloadMatchesRequest(payload, request, errors);
        }
    }

    private static void ValidateNativeRenderPayloadMatchesRequest(
        IReadOnlyDictionary<string, JsonElement> payload,
        IpcRequest request,
        ICollection<string> errors)
    {
        var parameters = request.Parameters!;
        MatchNativeRenderString(payload, "request_id", request.RequestId, errors);
        MatchNativeRenderString(payload, "run_id", parameters, "run_id", errors);
        MatchNativeRenderString(payload, "drawing_sha256", request.DrawingSha256, errors);
        MatchNativeRenderString(payload, "latest_mutation_sha256", parameters, "latest_mutation_sha256", errors);
        MatchNativeRenderString(payload, "visual_run_manifest_sha256", parameters, "visual_run_manifest_sha256", errors);
        MatchNativeRenderString(payload, "artifact_kind", parameters, "artifact_kind", errors);

        if (TryGetProperty(payload, "layout", out var payloadLayout)
            && TryGetProperty(parameters, "layout", out var requestLayout))
        {
            MatchNativeRenderString(payloadLayout, "identity", requestLayout, "identity", errors, "layout");
            MatchNativeRenderString(payloadLayout, "name", requestLayout, "name", errors, "layout");
        }
        if (TryGetProperty(payload, "render_options", out var payloadOptions)
            && TryGetProperty(parameters, "render_options", out var requestOptions))
        {
            foreach (var name in new[] { "background", "dpi", "fit_to_paper", "paper_size", "plot_style" })
            {
                MatchNativeRenderJsonValue(payloadOptions, name, requestOptions, name, errors, "render_options");
            }
        }
    }

    private static void MatchNativeRenderString(
        IReadOnlyDictionary<string, JsonElement> payload,
        string payloadName,
        string? expected,
        ICollection<string> errors)
    {
        if (expected is not null
            && TryGetString(payload, payloadName, out var actual)
            && !string.Equals(actual, expected, StringComparison.Ordinal))
        {
            errors.Add($"native_render_evidence payload.{payloadName} does not match request");
        }
    }

    private static void MatchNativeRenderString(
        IReadOnlyDictionary<string, JsonElement> payload,
        string payloadName,
        IReadOnlyDictionary<string, JsonElement> expectedValues,
        string expectedName,
        ICollection<string> errors,
        string displayName = "request")
    {
        if (TryGetString(expectedValues, expectedName, out var expected))
        {
            MatchNativeRenderString(payload, payloadName, expected, errors);
        }
        else
        {
            errors.Add($"native_render_evidence {displayName}.{expectedName} is missing");
        }
    }

    private static void MatchNativeRenderString(
        JsonElement payload,
        string payloadName,
        JsonElement expectedValues,
        string expectedName,
        ICollection<string> errors,
        string displayName)
    {
        if (TryGetString(expectedValues, expectedName, out var expected))
        {
            if (!TryGetString(payload, payloadName, out var actual)
                || !string.Equals(actual, expected, StringComparison.Ordinal))
            {
                errors.Add($"native_render_evidence payload.{displayName}.{payloadName} does not match request");
            }
        }
    }

    private static void MatchNativeRenderJsonValue(
        JsonElement payload,
        string payloadName,
        JsonElement expectedValues,
        string expectedName,
        ICollection<string> errors,
        string displayName)
    {
        if (TryGetProperty(payload, payloadName, out var actual)
            && TryGetProperty(expectedValues, expectedName, out var expected)
            && actual.GetRawText() != expected.GetRawText())
        {
            errors.Add($"native_render_evidence payload.{displayName}.{payloadName} does not match request");
        }
    }

    private static void ValidateNativeRenderArtifact(
        JsonElement artifact,
        string artifactKind,
        ICollection<string> errors)
    {
        var required = artifactKind == "PNG"
            ? new HashSet<string>(StringComparer.Ordinal) { "relative_path", "sha256", "width", "height" }
            : new HashSet<string>(StringComparer.Ordinal) { "relative_path", "sha256", "page_count" };
        ValidateClosedObject(artifact, required, "native_render_evidence artifact", errors);
        if (!TryGetString(artifact, "relative_path", out var relativePath)
            || !IsSafeNativeRenderArtifactPath(relativePath, artifactKind))
        {
            errors.Add("native_render_evidence artifact path is unsafe");
        }
        if (!TryGetString(artifact, "sha256", out var hash) || !LowercaseSha256Pattern.IsMatch(hash))
        {
            errors.Add("native_render_evidence artifact hash is invalid");
        }
        if (artifactKind == "PNG")
        {
            if (!TryGetInt64(artifact, "width", out var width) || width is < 1 or > 100000)
            {
                errors.Add("native_render_evidence PNG width is invalid");
            }
            if (!TryGetInt64(artifact, "height", out var height) || height is < 1 or > 100000)
            {
                errors.Add("native_render_evidence PNG height is invalid");
            }
            if (TryGetInt64(artifact, "width", out width)
                && TryGetInt64(artifact, "height", out height)
                && width * height > 100000000)
            {
                errors.Add("native_render_evidence PNG dimensions exceed the maximum pixel count");
            }
        }
        else if (!TryGetInt64(artifact, "page_count", out var pageCount)
            || pageCount is < 1 or > 100000)
        {
            errors.Add("native_render_evidence PDF page_count is invalid");
        }
    }

    private static bool IsSafeNativeRenderArtifactPath(string path, string artifactKind)
    {
        if (path.Length is 0 or > 512
            || path[0] is '/' or '\\'
            || (path.Length >= 2 && char.IsLetter(path[0]) && path[1] == ':')
            || path.Contains('\\')
            || path.Contains("//", StringComparison.Ordinal))
        {
            return false;
        }
        var parts = path.Split('/');
        return parts.All(part => part is not ("" or "." or ".."))
            && path.EndsWith(artifactKind == "PNG" ? ".png" : ".pdf", StringComparison.Ordinal);
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

    private static bool TryGetArray(
        IReadOnlyDictionary<string, JsonElement> values,
        string name,
        out JsonElement array)
    {
        array = default;
        return values.TryGetValue(name, out array) && array.ValueKind == JsonValueKind.Array;
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

    private static bool TryGetBoolean(JsonElement value, string name, out bool result)
    {
        result = false;
        if (!TryGetProperty(value, name, out var element)
            || (element.ValueKind != JsonValueKind.True && element.ValueKind != JsonValueKind.False))
        {
            return false;
        }

        result = element.GetBoolean();
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
