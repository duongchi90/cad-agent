using System.Text.Json;
using System.Text.RegularExpressions;
using CadAgent.AutoCAD2027.Drawing;

namespace CadAgent.AutoCAD2027.Ipc;

public static class BoundedNativeLineEditPolicy
{
    private static readonly Regex IdentifierPattern = new(
        "^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$",
        RegexOptions.CultureInvariant | RegexOptions.Compiled);

    private static readonly Regex HandlePattern = new(
        "^[0-9A-Fa-f]{1,64}$",
        RegexOptions.CultureInvariant | RegexOptions.Compiled);

    private static readonly IReadOnlySet<string> ParameterFields = new HashSet<string>(
        new[]
        {
            "run_id",
            "target_role",
            "target_handles",
            "protected_competing_handles",
            "expected_type",
            "expected_before_length",
            "target_after_length",
            "length_tolerance",
            "direction",
            "save"
        },
        StringComparer.Ordinal);

    public static readonly IReadOnlyList<string> TargetHandles = new[]
    {
        "15DC51C", "15DC51A", "15DC518", "15DC516", "15DC514", "15DC512",
        "15DC510", "15DC50E", "15DC50C", "15DC50A", "15DC508", "15DC506"
    };

    public static readonly IReadOnlyList<string> ProtectedCompetingHandles = new[]
    {
        "15DC51D", "15DC51B", "15DC519", "15DC517", "15DC515", "15DC513",
        "15DC511", "15DC50F", "15DC50D", "15DC50B", "15DC509", "15DC507"
    };

    public static IReadOnlyList<string> ValidateRequestShape(IpcRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        var errors = new List<string>();
        if (request.Operation != BoundedNativeLineEditOperationNames.Edit)
        {
            errors.Add($"operation must be {BoundedNativeLineEditOperationNames.Edit}");
            return errors;
        }

        if (request.DrawingFullPath is null)
        {
            errors.Add("bounded_native_line_edit drawing_full_path is required");
        }

        if (request.DrawingSha256 is null || !request.DrawingSha256.Equals(
                request.DrawingSha256.ToLowerInvariant(),
                StringComparison.Ordinal)
            || request.DrawingSha256.Length != 64)
        {
            errors.Add("bounded_native_line_edit drawing_sha256 must be a lowercase SHA-256");
        }

        ValidateApproval(request.Approval, errors);
        if (request.Parameters is null)
        {
            errors.Add("bounded_native_line_edit parameters must be an object");
            return errors;
        }

        var unsupported = request.Parameters.Keys
            .Except(ParameterFields, StringComparer.Ordinal)
            .ToArray();
        if (unsupported.Length > 0)
        {
            errors.Add($"bounded_native_line_edit parameters contain unsupported field '{unsupported[0]}'");
        }

        foreach (var missing in ParameterFields.Except(request.Parameters.Keys, StringComparer.Ordinal))
        {
            errors.Add($"bounded_native_line_edit parameters are missing '{missing}'");
        }

        if (TryGetString(request.Parameters, "run_id", out var runId)
            && !IdentifierPattern.IsMatch(runId))
        {
            errors.Add("bounded_native_line_edit run_id is invalid");
        }

        if (!TryGetString(request.Parameters, "target_role", out var targetRole)
            || targetRole != "ACCEPTED_NATIVE_DWG")
        {
            errors.Add("bounded_native_line_edit target_role must be ACCEPTED_NATIVE_DWG");
        }

        ValidateHandleSet(request.Parameters, "target_handles", TargetHandles, errors);
        ValidateHandleSet(
            request.Parameters,
            "protected_competing_handles",
            ProtectedCompetingHandles,
            errors);

        if (TryGetString(request.Parameters, "expected_type", out var expectedType)
            && expectedType != "LINE")
        {
            errors.Add("bounded_native_line_edit expected_type must be LINE");
        }

        if (TryGetDouble(request.Parameters, "expected_before_length", out var beforeLength)
            && Math.Abs(beforeLength - 490d) > 0.000001d)
        {
            errors.Add("bounded_native_line_edit expected_before_length must be 490");
        }

        if (TryGetDouble(request.Parameters, "target_after_length", out var afterLength)
            && Math.Abs(afterLength - 500d) > 0.000001d)
        {
            errors.Add("bounded_native_line_edit target_after_length must be 500");
        }

        if (TryGetDouble(request.Parameters, "length_tolerance", out var tolerance)
            && (!double.IsFinite(tolerance) || tolerance <= 0 || tolerance > 1))
        {
            errors.Add("bounded_native_line_edit length_tolerance must be finite and between 0 and 1");
        }

        if (TryGetString(request.Parameters, "direction", out var direction)
            && direction != "POSITIVE_Y")
        {
            errors.Add("bounded_native_line_edit direction must be POSITIVE_Y");
        }

        if (!TryGetBoolean(request.Parameters, "save", out var save) || !save)
        {
            errors.Add("bounded_native_line_edit save must be true");
        }

        if (TryGetHandleValues(request.Parameters, "target_handles", out var targetValues)
            && TryGetHandleValues(request.Parameters, "protected_competing_handles", out var protectedValues)
            && targetValues.Intersect(protectedValues, StringComparer.OrdinalIgnoreCase).Any())
        {
            errors.Add("bounded_native_line_edit target and protected handles must not overlap");
        }

        return errors;
    }

    public static BoundedNativeLineEditRequest Parse(IpcRequest request)
    {
        var errors = ValidateRequestShape(request);
        if (errors.Count != 0)
        {
            throw new ContractValidationException(errors);
        }

        var parameters = request.Parameters!;
        var approval = request.Approval!.Value;
        return new BoundedNativeLineEditRequest(
            request.RequestId!,
            request.DrawingFullPath!,
            request.DrawingSha256!,
            parameters["run_id"].GetString()!,
            parameters["target_role"].GetString()!,
            ReadHandleValues(parameters["target_handles"]),
            ReadHandleValues(parameters["protected_competing_handles"]),
            parameters["expected_type"].GetString()!,
            parameters["expected_before_length"].GetDouble(),
            parameters["target_after_length"].GetDouble(),
            parameters["length_tolerance"].GetDouble(),
            parameters["direction"].GetString()!,
            parameters["save"].GetBoolean(),
            approval.GetProperty("reference").GetString()!);
    }

    private static void ValidateApproval(JsonElement? approval, ICollection<string> errors)
    {
        if (!approval.HasValue || approval.Value.ValueKind != JsonValueKind.Object)
        {
            errors.Add("bounded_native_line_edit approval must be an object");
            return;
        }

        var properties = approval.Value.EnumerateObject()
            .Select(property => property.Name)
            .ToHashSet(StringComparer.Ordinal);
        foreach (var unsupported in properties.Except(new[] { "reference", "status" }, StringComparer.Ordinal))
        {
            errors.Add($"bounded_native_line_edit approval contains unsupported field '{unsupported}'");
        }

        if (!TryGetString(approval.Value, "reference", out var reference)
            || !IdentifierPattern.IsMatch(reference))
        {
            errors.Add("bounded_native_line_edit approval.reference is invalid");
        }

        if (!TryGetString(approval.Value, "status", out var status) || status != "APPROVED")
        {
            errors.Add("bounded_native_line_edit approval.status must be APPROVED");
        }
    }

    private static void ValidateHandleSet(
        IReadOnlyDictionary<string, JsonElement> parameters,
        string name,
        IReadOnlyList<string> expected,
        ICollection<string> errors)
    {
        if (!TryGetHandleValues(parameters, name, out var values))
        {
            errors.Add($"bounded_native_line_edit {name} must be a non-empty handle array");
            return;
        }

        if (values.Count != values.Distinct(StringComparer.OrdinalIgnoreCase).Count())
        {
            errors.Add($"bounded_native_line_edit {name} must not contain duplicates");
        }

        var actual = values.ToHashSet(StringComparer.OrdinalIgnoreCase);
        var required = expected.ToHashSet(StringComparer.OrdinalIgnoreCase);
        if (!actual.SetEquals(required))
        {
            errors.Add($"bounded_native_line_edit {name} does not match the authorized Sheet 4 occurrence");
        }
    }

    private static bool TryGetHandleValues(
        IReadOnlyDictionary<string, JsonElement> parameters,
        string name,
        out IReadOnlyList<string> values)
    {
        values = Array.Empty<string>();
        if (!parameters.TryGetValue(name, out var property) || property.ValueKind != JsonValueKind.Array)
        {
            return false;
        }

        var result = new List<string>();
        foreach (var item in property.EnumerateArray())
        {
            if (!TryGetString(item, out var handle) || !HandlePattern.IsMatch(handle))
            {
                return false;
            }
            result.Add(handle);
        }

        values = result;
        return result.Count > 0;
    }

    private static IReadOnlyList<string> ReadHandleValues(JsonElement value) =>
        value.EnumerateArray().Select(item => item.GetString()!).ToArray();

    private static bool TryGetString(
        IReadOnlyDictionary<string, JsonElement> values,
        string name,
        out string value)
    {
        value = string.Empty;
        return values.TryGetValue(name, out var property)
            && TryGetString(property, out value);
    }

    private static bool TryGetString(JsonElement value, out string result)
    {
        result = string.Empty;
        if (value.ValueKind != JsonValueKind.String || string.IsNullOrWhiteSpace(value.GetString()))
        {
            return false;
        }

        result = value.GetString()!;
        return true;
    }

    private static bool TryGetDouble(
        IReadOnlyDictionary<string, JsonElement> values,
        string name,
        out double value)
    {
        value = 0;
        return values.TryGetValue(name, out var property)
            && property.ValueKind == JsonValueKind.Number
            && property.TryGetDouble(out value)
            && double.IsFinite(value);
    }

    private static bool TryGetBoolean(
        IReadOnlyDictionary<string, JsonElement> values,
        string name,
        out bool value)
    {
        value = false;
        if (!values.TryGetValue(name, out var property)
            || property.ValueKind != JsonValueKind.True)
        {
            return false;
        }

        value = true;
        return true;
    }

    private static bool TryGetString(JsonElement value, string name, out string result)
    {
        result = string.Empty;
        return value.ValueKind == JsonValueKind.Object
            && value.TryGetProperty(name, out var property)
            && TryGetString(property, out result);
    }
}
