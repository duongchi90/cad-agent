using System.Text.Json;
using System.Text.Json.Serialization;

namespace CadAgent.AutoCAD2027.Ipc;

public static class ContractConstants
{
    public const string SchemaVersion = "1.0";
    public const long DefaultMaxReadBytes = 1024 * 1024;
    public const int MaxRequestIdLength = 128;

    public static readonly IReadOnlySet<string> SupportedOperations =
        new HashSet<string>(StringComparer.Ordinal)
        {
            "health",
            "review",
            "close_disposable",
            "mechanical_bom",
            "drawing_setup_audit",
            "visual_evidence_export",
            "native_render_evidence",
            "exact_base_xref_inspection",
            "exact_base_xref_extraction"
        };
}

public sealed record IpcRequest
{
    [JsonPropertyName("request_id")]
    public string? RequestId { get; init; }

    [JsonPropertyName("schema_version")]
    public string? SchemaVersion { get; init; }

    [JsonPropertyName("operation")]
    public string? Operation { get; init; }

    [JsonPropertyName("drawing_full_path")]
    public string? DrawingFullPath { get; init; }

    [JsonPropertyName("drawing_sha256")]
    public string? DrawingSha256 { get; init; }

    [JsonPropertyName("parameters")]
    public Dictionary<string, JsonElement>? Parameters { get; init; }

    [JsonPropertyName("approval")]
    public JsonElement? Approval { get; init; }
}

public sealed record IpcResult
{
    [JsonPropertyName("request_id")]
    public string? RequestId { get; init; }

    [JsonPropertyName("success")]
    public bool Success { get; init; }

    [JsonPropertyName("operation")]
    public string? Operation { get; init; }

    [JsonPropertyName("drawing_full_path")]
    public string? DrawingFullPath { get; init; }

    [JsonPropertyName("changed")]
    public bool Changed { get; init; }

    [JsonPropertyName("entity_handles")]
    public List<string>? EntityHandles { get; init; }

    [JsonPropertyName("warnings")]
    public List<string>? Warnings { get; init; }

    [JsonPropertyName("errors")]
    public List<string>? Errors { get; init; }

    [JsonPropertyName("started_at")]
    public DateTimeOffset StartedAt { get; init; }

    [JsonPropertyName("completed_at")]
    public DateTimeOffset CompletedAt { get; init; }

    [JsonPropertyName("payload")]
    public Dictionary<string, JsonElement>? Payload { get; init; } = new(StringComparer.Ordinal);
}

public static class ContractJson
{
    private static readonly IReadOnlySet<string> RequestProperties =
        new HashSet<string>(StringComparer.Ordinal)
        {
            "request_id",
            "schema_version",
            "operation",
            "drawing_full_path",
            "drawing_sha256",
            "parameters",
            "approval"
        };

    private static readonly IReadOnlySet<string> RequestRequiredProperties =
        new HashSet<string>(RequestProperties, StringComparer.Ordinal);

    private static readonly IReadOnlySet<string> ResultProperties =
        new HashSet<string>(StringComparer.Ordinal)
        {
            "request_id",
            "success",
            "operation",
            "drawing_full_path",
            "changed",
            "entity_handles",
            "warnings",
            "errors",
            "started_at",
            "completed_at",
            "payload"
        };

    private static readonly IReadOnlySet<string> ResultRequiredProperties =
        new HashSet<string>(StringComparer.Ordinal)
        {
            "request_id",
            "success",
            "operation",
            "drawing_full_path",
            "changed",
            "entity_handles",
            "warnings",
            "errors",
            "started_at",
            "completed_at"
        };

    public static readonly JsonSerializerOptions Options = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = false,
        DefaultIgnoreCondition = JsonIgnoreCondition.Never
    };

    public static string Serialize(IpcRequest request) =>
        JsonSerializer.Serialize(request, Options);

    public static string Serialize(IpcResult result) =>
        JsonSerializer.Serialize(result, Options);

    public static IpcRequest DeserializeRequest(string json)
    {
        using var document = JsonDocument.Parse(json);
        ValidateObjectShape(document.RootElement, RequestProperties, RequestRequiredProperties, "request");
        ValidateNullableObjectProperty(document.RootElement, "approval", "request.approval");

        return JsonSerializer.Deserialize<IpcRequest>(json, Options)
            ?? throw new JsonException("The request JSON was null.");
    }

    public static IpcResult DeserializeResult(string json)
    {
        using var document = JsonDocument.Parse(json);
        ValidateObjectShape(document.RootElement, ResultProperties, ResultRequiredProperties, "result");

        if (document.RootElement.TryGetProperty("payload", out var payload)
            && payload.ValueKind == JsonValueKind.Null)
        {
            throw new JsonException("result.payload must be an object when present.");
        }

        return JsonSerializer.Deserialize<IpcResult>(json, Options)
            ?? throw new JsonException("The result JSON was null.");
    }

    private static void ValidateObjectShape(
        JsonElement root,
        IReadOnlySet<string> allowedProperties,
        IReadOnlySet<string> requiredProperties,
        string contractName)
    {
        if (root.ValueKind != JsonValueKind.Object)
        {
            throw new JsonException($"The {contractName} JSON root must be an object.");
        }

        var presentProperties = new HashSet<string>(StringComparer.Ordinal);
        foreach (var property in root.EnumerateObject())
        {
            if (!allowedProperties.Contains(property.Name))
            {
                throw new JsonException($"The {contractName} JSON contains unsupported property '{property.Name}'.");
            }

            presentProperties.Add(property.Name);
        }

        foreach (var requiredProperty in requiredProperties)
        {
            if (!presentProperties.Contains(requiredProperty))
            {
                throw new JsonException($"The {contractName} JSON is missing required property '{requiredProperty}'.");
            }
        }
    }

    private static void ValidateNullableObjectProperty(
        JsonElement root,
        string propertyName,
        string displayName)
    {
        var property = root.GetProperty(propertyName);
        if (property.ValueKind is not (JsonValueKind.Object or JsonValueKind.Null))
        {
            throw new JsonException($"{displayName} must be an object or null.");
        }
    }
}
