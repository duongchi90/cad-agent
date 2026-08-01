using System.Text.Json;
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
