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
            "close_disposable"
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

    public static IpcRequest DeserializeRequest(string json) =>
        JsonSerializer.Deserialize<IpcRequest>(json, Options)
        ?? throw new JsonException("The request JSON was null.");

    public static IpcResult DeserializeResult(string json) =>
        JsonSerializer.Deserialize<IpcResult>(json, Options)
        ?? throw new JsonException("The result JSON was null.");
}
