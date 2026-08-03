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

    private static bool TryGetBoolean(
        IReadOnlyDictionary<string, JsonElement> parameters,
        string name,
        out bool value)
    {
        value = false;
        if (!parameters.TryGetValue(name, out var element)
            || (element.ValueKind != JsonValueKind.True && element.ValueKind != JsonValueKind.False))
        {
            return false;
        }

        value = element.GetBoolean();
        return true;
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
