using System.Text.Json;
using CadAgent.AutoCAD2027.Commands;
using CadAgent.AutoCAD2027.Drawing;
using CadAgent.AutoCAD2027.Ipc;
using CadAgent.AutoCAD2027.Review;
using Xunit;

namespace CadAgent.AutoCAD2027.Tests.Ipc;

public sealed class OperationDispatcherTests
{
    [Fact]
    public void HealthReturnsTheActiveDocumentAndPreservesRequestId()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\drawings\sample.dwg"
        };
        var dispatcher = CreateDispatcher(gateway);

        var result = dispatcher.Dispatch(Request("health", "health-request", null, Parameters()));

        Assert.True(result.Success);
        Assert.Equal("health-request", result.RequestId);
        Assert.Equal("health", result.Operation);
        Assert.Equal(@"C:\drawings\sample.dwg", result.DrawingFullPath);
        Assert.False(result.Changed);
        Assert.Empty(result.Errors!);
        Assert.Equal("1.0.0", result.Payload!["plugin_version"].GetString());
        Assert.True(result.Payload["ipc_readable"].GetBoolean());
        Assert.True(result.Payload["ipc_writable"].GetBoolean());
    }

    [Fact]
    public void ReviewPreservesRequestAndOperationIds()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\drawings\sample.dwg",
            Entities = new[] { Entity("A1", "LINE") }
        };
        var dispatcher = CreateDispatcher(gateway);

        var result = dispatcher.Dispatch(Request(
            "review",
            "review-request",
            @"C:\drawings\sample.dwg",
            Parameters(("handles", JsonSerializer.SerializeToElement(new[] { "A1" })))));

        Assert.True(result.Success);
        Assert.Equal("review-request", result.RequestId);
        Assert.Equal("review", result.Operation);
        Assert.Equal(new[] { "A1" }, result.EntityHandles);
    }

    [Fact]
    public void ReviewRejectsAFullPathDocumentMismatchBeforeReadingEntities()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\other\sample.dwg",
            Entities = new[] { Entity("A1", "LINE") }
        };
        var dispatcher = CreateDispatcher(gateway);

        var result = dispatcher.Dispatch(Request(
            "review",
            "mismatch-request",
            @"C:\drawings\sample.dwg",
            Parameters(("handles", JsonSerializer.SerializeToElement(new[] { "A1" })))));

        Assert.False(result.Success);
        Assert.Contains(result.Errors!, error => error.Contains("full path", StringComparison.OrdinalIgnoreCase));
        Assert.Equal(0, gateway.ReadEntitiesCallCount);
    }

    [Fact]
    public void CloseDisposableRequiresTheNonSavingDisposableGuardBeforeClosing()
    {
        var closeCalls = 0;
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\drawings\sample.dwg"
        };
        var dispatcher = CreateDispatcher(gateway, () => closeCalls++);

        var result = dispatcher.Dispatch(Request(
            "close_disposable",
            "close-request",
            @"C:\drawings\sample.dwg",
            Parameters(
                ("disposable", JsonSerializer.SerializeToElement(false)),
                ("save_changes", JsonSerializer.SerializeToElement(false)))));

        Assert.False(result.Success);
        Assert.Contains(result.Errors!, error => error.Contains("disposable", StringComparison.OrdinalIgnoreCase));
        Assert.Equal(0, closeCalls);
    }

    [Fact]
    public void UnsupportedMutationIsRejectedBeforeTheDrawingBoundary()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\drawings\sample.dwg"
        };
        var dispatcher = CreateDispatcher(gateway);

        var result = dispatcher.Dispatch(Request(
            "repair",
            "repair-request",
            @"C:\drawings\sample.dwg",
            Parameters()));

        Assert.False(result.Success);
        Assert.Contains(result.Errors!, error => error.Contains("not supported", StringComparison.OrdinalIgnoreCase));
        Assert.Equal(0, gateway.ReadEntitiesCallCount);
        Assert.Equal("repair", result.Payload!["requested_operation"].GetString());
    }

    [Fact]
    public void ExceptionsBecomeFailureResultsWithTheOriginalRequestId()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\drawings\sample.dwg",
            ExceptionToThrow = new InvalidOperationException("transaction exploded")
        };
        var dispatcher = CreateDispatcher(gateway);

        var result = dispatcher.Dispatch(Request(
            "review",
            "exception-request",
            @"C:\drawings\sample.dwg",
            Parameters(("handles", JsonSerializer.SerializeToElement(new[] { "A1" })))));

        Assert.False(result.Success);
        Assert.Equal("exception-request", result.RequestId);
        Assert.Equal("review", result.Operation);
        Assert.Contains(result.Errors!, error => error.Contains("transaction exploded", StringComparison.Ordinal));
    }

    private static OperationDispatcher CreateDispatcher(
        StubDrawingGateway gateway,
        Action? closeWithoutSaving = null) =>
        new(new CommandContext(
            new JsonFileStore(Path.Combine(Path.GetTempPath(), "cadagent-t06-tests", Guid.NewGuid().ToString("N"))),
            gateway,
            closeWithoutSaving ?? (() => { }),
            clock: () => new DateTimeOffset(2026, 8, 1, 12, 0, 0, TimeSpan.Zero)));

    private static IpcRequest Request(
        string operation,
        string requestId,
        string? drawingFullPath,
        Dictionary<string, JsonElement> parameters) =>
        new()
        {
            RequestId = requestId,
            SchemaVersion = ContractConstants.SchemaVersion,
            Operation = operation,
            DrawingFullPath = drawingFullPath,
            DrawingSha256 = null,
            Parameters = parameters,
            Approval = null
        };

    private static Dictionary<string, JsonElement> Parameters(
        params (string Name, JsonElement Value)[] values) =>
        values.ToDictionary(value => value.Name, value => value.Value, StringComparer.Ordinal);

    private static EntitySnapshot Entity(string handle, string type) =>
        new(handle, type, "0", new Dictionary<string, JsonElement>(StringComparer.Ordinal));

    private sealed class StubDrawingGateway : IDrawingGateway
    {
        public string? ActiveDocumentFullPath { get; init; }

        public IReadOnlyList<EntitySnapshot> Entities { get; init; } = Array.Empty<EntitySnapshot>();

        public Exception? ExceptionToThrow { get; init; }

        public int ReadEntitiesCallCount { get; private set; }

        public IReadOnlyList<EntitySnapshot> ReadEntities(IReadOnlyCollection<string> handles)
        {
            ReadEntitiesCallCount++;
            if (ExceptionToThrow is not null)
            {
                throw ExceptionToThrow;
            }

            return Entities;
        }
    }
}
