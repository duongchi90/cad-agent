using System.Text.Json;
using System.Text.Json.Serialization;
using CadAgent.AutoCAD2027.Ipc;

namespace CadAgent.AutoCAD2027.Drawing;

public static class ViewportQueryOperationNames
{
    public const string Operation = "viewport_query";
    public const string ResultSchemaVersion = "viewport-query-result-1.0";
    public const string ViewportType = "VIEWPORT";

    public static readonly IReadOnlySet<string> FieldNames =
        new HashSet<string>(StringComparer.Ordinal)
        {
            "center_point",
            "width",
            "height",
            "view_center",
            "view_height",
            "view_target",
            "twist_angle"
        };
}

public static class ViewportFieldStatuses
{
    public const string Observed = "OBSERVED";
    public const string Unsupported = "UNSUPPORTED";
    public const string Error = "ERROR";
}

public static class ViewportFieldReasons
{
    public const string PropertyUnavailable = "PROPERTY_UNAVAILABLE";
    public const string PropertyReadFailed = "PROPERTY_READ_FAILED";
    public const string InvalidValue = "INVALID_VALUE";
}

public sealed record ViewportQueryRequest(
    string RequestId,
    string DrawingFullPath,
    string DrawingSha256,
    string Handle)
{
    public static ViewportQueryRequest FromIpc(IpcRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        var validation = ContractValidator.ValidateRequest(request);
        if (!validation.IsValid)
        {
            throw new ContractValidationException(validation.Errors);
        }

        var parameters = request.Parameters!;
        var handle = parameters["handle"].GetString()!;
        return new ViewportQueryRequest(
            request.RequestId!,
            request.DrawingFullPath!,
            request.DrawingSha256!,
            handle.ToUpperInvariant());
    }
}

public sealed record ViewportFieldState
{
    [JsonPropertyName("status")]
    public required string Status { get; init; }

    [JsonPropertyName("value")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public JsonElement? Value { get; init; }

    [JsonPropertyName("reason")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? Reason { get; init; }

    public static ViewportFieldState Observed(JsonElement value) => new()
    {
        Status = ViewportFieldStatuses.Observed,
        Value = value
    };

    public static ViewportFieldState Unsupported(string reason = ViewportFieldReasons.PropertyUnavailable) => new()
    {
        Status = ViewportFieldStatuses.Unsupported,
        Reason = reason
    };

    public static ViewportFieldState Error(string reason = ViewportFieldReasons.PropertyReadFailed) => new()
    {
        Status = ViewportFieldStatuses.Error,
        Reason = reason
    };
}

public sealed record ViewportQueryResult(
    string Handle,
    string Type,
    string Layer,
    IReadOnlyDictionary<string, ViewportFieldState> Fields,
    string DrawingSha256Before,
    string DrawingSha256After,
    int DbmodBefore,
    int DbmodAfter)
{
    public Dictionary<string, JsonElement> ToPayload()
    {
        var payload = JsonSerializer.SerializeToElement(new
        {
            schema_version = ViewportQueryOperationNames.ResultSchemaVersion,
            handle = Handle,
            type = Type,
            layer = Layer,
            fields = Fields,
            drawing_sha256_before = DrawingSha256Before,
            drawing_sha256_after = DrawingSha256After,
            dbmod_before = DbmodBefore,
            dbmod_after = DbmodAfter
        });

        return payload.EnumerateObject()
            .ToDictionary(property => property.Name, property => property.Value.Clone(), StringComparer.Ordinal);
    }
}
