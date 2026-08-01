using System.Text.Json;
using System.Text;
using CadAgent.AutoCAD2027.Ipc;
using Xunit;

namespace CadAgent.AutoCAD2027.Tests.Ipc;

public sealed class JsonFileStoreTests
{
    [Fact]
    public void WritesAndReadsRequestWithDeterministicFileName()
    {
        using var fixture = new StoreFixture();
        var request = HealthRequest("request-one");

        fixture.Store.WriteRequest(request);

        Assert.Equal(
            Path.Combine(fixture.DirectoryPath, "cadagent_dotnet_request_request-one.json"),
            fixture.Store.GetRequestPath(request.RequestId!));
        Assert.True(File.Exists(fixture.Store.GetRequestPath(request.RequestId!)));
        var copy = fixture.Store.ReadRequest(request.RequestId!);
        Assert.Equal(request.RequestId, copy.RequestId);
        Assert.Equal(request.DrawingFullPath, copy.DrawingFullPath);
    }

    [Fact]
    public void ReplacesResultAtomically()
    {
        using var fixture = new StoreFixture();
        var first = HealthResult("request-one", success: false);
        var second = HealthResult("request-one", success: true);

        fixture.Store.WriteResult(first);
        var path = fixture.Store.GetResultPath(first.RequestId!);
        var firstJson = File.ReadAllText(path);
        fixture.Store.WriteResult(second);

        Assert.True(File.Exists(path));
        Assert.NotEqual(firstJson, File.ReadAllText(path));
        Assert.True(fixture.Store.ReadResult(second.RequestId!).Success);
        Assert.Empty(Directory.EnumerateFiles(fixture.DirectoryPath, "*.tmp"));
    }

    [Fact]
    public void RejectsReadsLargerThanConfiguredBound()
    {
        using var fixture = new StoreFixture(maxReadBytes: 64);
        var path = fixture.Store.GetResultPath("large-result");
        File.WriteAllText(path, new string('x', 128));

        Assert.Throws<InvalidDataException>(() => fixture.Store.ReadResult("large-result"));
    }

    [Fact]
    public void RejectsRequestWhenDrawingSha256IsOmitted()
    {
        using var fixture = new StoreFixture();
        const string requestId = "request-missing-sha";
        WriteRaw(fixture.Store.GetRequestPath(requestId), WithoutProperty(
            ContractJson.Serialize(HealthRequest(requestId)), "drawing_sha256"));

        Assert.Throws<InvalidDataException>(() => fixture.Store.ReadRequest(requestId));
    }

    [Fact]
    public void RejectsRequestWhenApprovalIsOmitted()
    {
        using var fixture = new StoreFixture();
        const string requestId = "request-missing-approval";
        WriteRaw(fixture.Store.GetRequestPath(requestId), WithoutProperty(
            ContractJson.Serialize(HealthRequest(requestId)), "approval"));

        Assert.Throws<InvalidDataException>(() => fixture.Store.ReadRequest(requestId));
    }

    [Fact]
    public void RejectsRequestWhenDrawingFullPathIsOmitted()
    {
        using var fixture = new StoreFixture();
        const string requestId = "request-missing-path";
        WriteRaw(fixture.Store.GetRequestPath(requestId), WithoutProperty(
            ContractJson.Serialize(HealthRequest(requestId)), "drawing_full_path"));

        Assert.Throws<InvalidDataException>(() => fixture.Store.ReadRequest(requestId));
    }

    [Fact]
    public void RejectsResultWhenSuccessIsOmitted()
    {
        using var fixture = new StoreFixture();
        const string requestId = "result-missing-success";
        WriteRaw(fixture.Store.GetResultPath(requestId), WithoutProperty(
            ContractJson.Serialize(HealthResult(requestId, success: true)), "success"));

        Assert.Throws<InvalidDataException>(() => fixture.Store.ReadResult(requestId));
    }

    [Fact]
    public void RejectsResultWhenChangedIsOmitted()
    {
        using var fixture = new StoreFixture();
        const string requestId = "result-missing-changed";
        WriteRaw(fixture.Store.GetResultPath(requestId), WithoutProperty(
            ContractJson.Serialize(HealthResult(requestId, success: true)), "changed"));

        Assert.Throws<InvalidDataException>(() => fixture.Store.ReadResult(requestId));
    }

    [Fact]
    public void RejectsResultWhenDrawingFullPathIsOmitted()
    {
        using var fixture = new StoreFixture();
        const string requestId = "result-missing-path";
        WriteRaw(fixture.Store.GetResultPath(requestId), WithoutProperty(
            ContractJson.Serialize(HealthResult(requestId, success: true)), "drawing_full_path"));

        Assert.Throws<InvalidDataException>(() => fixture.Store.ReadResult(requestId));
    }

    [Fact]
    public void RejectsRequestWithAnExtraTopLevelProperty()
    {
        using var fixture = new StoreFixture();
        const string requestId = "request-extra-property";
        WriteRaw(fixture.Store.GetRequestPath(requestId), WithExtraProperty(
            ContractJson.Serialize(HealthRequest(requestId))));

        Assert.Throws<InvalidDataException>(() => fixture.Store.ReadRequest(requestId));
    }

    [Fact]
    public void RejectsResultWithAnExtraTopLevelProperty()
    {
        using var fixture = new StoreFixture();
        const string requestId = "result-extra-property";
        WriteRaw(fixture.Store.GetResultPath(requestId), WithExtraProperty(
            ContractJson.Serialize(HealthResult(requestId, success: true))));

        Assert.Throws<InvalidDataException>(() => fixture.Store.ReadResult(requestId));
    }

    [Fact]
    public void RejectsApprovalThatIsNotAnObjectOrNull()
    {
        using var fixture = new StoreFixture();
        const string requestId = "request-invalid-approval";
        WriteRaw(fixture.Store.GetRequestPath(requestId), ReplaceProperty(
            ContractJson.Serialize(HealthRequest(requestId)),
            "approval",
            writer => writer.WriteStringValue("not-an-object")));

        Assert.Throws<InvalidDataException>(() => fixture.Store.ReadRequest(requestId));
    }

    [Fact]
    public void RejectsResultWithAnExplicitNullPayload()
    {
        using var fixture = new StoreFixture();
        const string requestId = "result-null-payload";
        WriteRaw(fixture.Store.GetResultPath(requestId), ReplaceProperty(
            ContractJson.Serialize(HealthResult(requestId, success: true)),
            "payload",
            writer => writer.WriteNullValue()));

        Assert.Throws<InvalidDataException>(() => fixture.Store.ReadResult(requestId));
    }

    [Fact]
    public void RejectsResultWithAnEmptyEntityHandle()
    {
        using var fixture = new StoreFixture();
        const string requestId = "result-empty-handle";
        WriteRaw(fixture.Store.GetResultPath(requestId), ReplaceProperty(
            ContractJson.Serialize(HealthResult(requestId, success: true)),
            "entity_handles",
            writer =>
            {
                writer.WriteStartArray();
                writer.WriteStringValue(string.Empty);
                writer.WriteEndArray();
            }));

        Assert.Throws<InvalidDataException>(() => fixture.Store.ReadResult(requestId));
    }

    [Fact]
    public void RejectsErrorResultWithNullDrawingPathForReview()
    {
        using var fixture = new StoreFixture();
        const string requestId = "review-error-null-path";
        WriteRaw(fixture.Store.GetResultPath(requestId), ContractJson.Serialize(
            ErrorResult(requestId, "review", "review failed")));

        Assert.Throws<InvalidDataException>(() => fixture.Store.ReadResult(requestId));
    }

    [Fact]
    public void RejectsErrorResultWithNullDrawingPathForCloseDisposable()
    {
        using var fixture = new StoreFixture();
        const string requestId = "close-error-null-path";
        WriteRaw(fixture.Store.GetResultPath(requestId), ContractJson.Serialize(
            ErrorResult(requestId, "close_disposable", "close failed")));

        Assert.Throws<InvalidDataException>(() => fixture.Store.ReadResult(requestId));
    }

    [Fact]
    public void CleansOnlyTheCurrentRequestFiles()
    {
        using var fixture = new StoreFixture();
        var first = HealthRequest("request-one");
        var second = HealthRequest("request-two");
        fixture.Store.WriteRequest(first);
        fixture.Store.WriteResult(HealthResult(first.RequestId!, success: true));
        fixture.Store.WriteRequest(second);
        fixture.Store.WriteResult(HealthResult(second.RequestId!, success: true));

        fixture.Store.Cleanup(first.RequestId!);

        Assert.False(File.Exists(fixture.Store.GetRequestPath(first.RequestId!)));
        Assert.False(File.Exists(fixture.Store.GetResultPath(first.RequestId!)));
        Assert.True(File.Exists(fixture.Store.GetRequestPath(second.RequestId!)));
        Assert.True(File.Exists(fixture.Store.GetResultPath(second.RequestId!)));
    }

    private static IpcRequest HealthRequest(string requestId) => new()
    {
        RequestId = requestId,
        SchemaVersion = ContractConstants.SchemaVersion,
        Operation = "health",
        DrawingFullPath = null,
        DrawingSha256 = null,
        Parameters = new Dictionary<string, JsonElement>(),
        Approval = null
    };

    private static IpcResult HealthResult(string requestId, bool success) => new()
    {
        RequestId = requestId,
        Success = success,
        Operation = "health",
        DrawingFullPath = null,
        Changed = false,
        EntityHandles = new List<string>(),
        Warnings = new List<string>(),
        Errors = success ? new List<string>() : new List<string> { "offline" },
        StartedAt = DateTimeOffset.UtcNow,
        CompletedAt = DateTimeOffset.UtcNow,
        Payload = new Dictionary<string, JsonElement>()
    };

    private static IpcResult ErrorResult(string requestId, string operation, string error) => new()
    {
        RequestId = requestId,
        Success = false,
        Operation = operation,
        DrawingFullPath = null,
        Changed = false,
        EntityHandles = new List<string>(),
        Warnings = new List<string>(),
        Errors = new List<string> { error },
        StartedAt = DateTimeOffset.Parse("2026-08-01T00:00:00Z"),
        CompletedAt = DateTimeOffset.Parse("2026-08-01T00:00:01Z"),
        Payload = new Dictionary<string, JsonElement>()
    };

    private static void WriteRaw(string path, string json) => File.WriteAllText(path, json);

    private static string WithoutProperty(string json, string propertyName)
    {
        using var document = JsonDocument.Parse(json);
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream))
        {
            writer.WriteStartObject();
            foreach (var property in document.RootElement.EnumerateObject())
            {
                if (!string.Equals(property.Name, propertyName, StringComparison.Ordinal))
                {
                    property.WriteTo(writer);
                }
            }

            writer.WriteEndObject();
        }

        return Encoding.UTF8.GetString(stream.ToArray());
    }

    private static string WithExtraProperty(string json)
    {
        using var document = JsonDocument.Parse(json);
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream))
        {
            writer.WriteStartObject();
            foreach (var property in document.RootElement.EnumerateObject())
            {
                property.WriteTo(writer);
            }

            writer.WriteBoolean("unexpected", true);
            writer.WriteEndObject();
        }

        return Encoding.UTF8.GetString(stream.ToArray());
    }

    private static string ReplaceProperty(
        string json,
        string propertyName,
        Action<Utf8JsonWriter> writeReplacement)
    {
        using var document = JsonDocument.Parse(json);
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream))
        {
            writer.WriteStartObject();
            foreach (var property in document.RootElement.EnumerateObject())
            {
                writer.WritePropertyName(property.Name);
                if (string.Equals(property.Name, propertyName, StringComparison.Ordinal))
                {
                    writeReplacement(writer);
                }
                else
                {
                    property.Value.WriteTo(writer);
                }
            }

            writer.WriteEndObject();
        }

        return Encoding.UTF8.GetString(stream.ToArray());
    }

    private sealed class StoreFixture : IDisposable
    {
        public StoreFixture(long maxReadBytes = 1024 * 1024)
        {
            DirectoryPath = Path.Combine(Path.GetTempPath(), "cadagent-dotnet-ipc-tests", Guid.NewGuid().ToString("N"));
            Store = new JsonFileStore(DirectoryPath, maxReadBytes);
        }

        public string DirectoryPath { get; }

        public JsonFileStore Store { get; }

        public void Dispose()
        {
            if (Directory.Exists(DirectoryPath))
            {
                Directory.Delete(DirectoryPath, recursive: true);
            }
        }
    }
}
