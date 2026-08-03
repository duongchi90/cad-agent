using System.Text.Json;
using CadAgent.AutoCAD2027.Commands;
using CadAgent.AutoCAD2027.Drawing;
using CadAgent.AutoCAD2027.DrawingSetup;
using CadAgent.AutoCAD2027.Ipc;
using CadAgent.AutoCAD2027.Review;
using Xunit;

namespace CadAgent.AutoCAD2027.Tests.Commands;

public sealed class CommandGuardTests
{
    [Fact]
    public void RegistersExactlyTheFourTaskCommands()
    {
        Assert.Equal(
            new[]
            {
                "CADAGENT_CLOSE_DISPOSABLE",
                "CADAGENT_DISPATCH",
                "CADAGENT_HEALTH",
                "CADAGENT_REVIEW"
            },
            CadAgentCommands.RegisteredCommandNames.OrderBy(name => name, StringComparer.Ordinal));
    }

    [Fact]
    public void ReviewCommandDelegatesToReadOnlyReviewEngineAndReportsResult()
    {
        var reports = new List<string>();
        var gateway = new SpyDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\drawings\sample.dwg"
        };
        var context = CreateContext(gateway, reports, () => { });
        var commands = new CadAgentCommands(() => context);

        commands.Review();

        Assert.Equal(1, gateway.ReadEntitiesCallCount);
        Assert.Empty(gateway.LastHandles!);
        var result = ContractJson.DeserializeResult(reports.Single());
        Assert.True(result.Success);
        Assert.Equal("manual-review", result.RequestId);
        Assert.Equal("review", result.Operation);
        Assert.Equal(@"C:\drawings\sample.dwg", result.DrawingFullPath);
        Assert.False(result.Changed);
    }

    [Fact]
    public void CloseDisposableCommandUsesGuardedNonSavingCloseAndReportsResult()
    {
        var reports = new List<string>();
        var closeCalls = 0;
        var gateway = new SpyDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\drawings\sample.dwg"
        };
        var context = CreateContext(gateway, reports, () => closeCalls++);
        var commands = new CadAgentCommands(() => context);

        commands.CloseDisposable();

        Assert.Equal(1, closeCalls);
        var result = ContractJson.DeserializeResult(reports.Single());
        Assert.True(result.Success);
        Assert.Equal("manual-close-disposable", result.RequestId);
        Assert.Equal("close_disposable", result.Operation);
        Assert.True(result.Payload!["closed_without_saving"].GetBoolean());
    }

    [Fact]
    public void CloseDisposableCommandDoesNotCloseWithoutAnActiveDocument()
    {
        var reports = new List<string>();
        var closeCalls = 0;
        var context = CreateContext(new SpyDrawingGateway(), reports, () => closeCalls++);
        var commands = new CadAgentCommands(() => context);

        commands.CloseDisposable();

        Assert.Equal(0, closeCalls);
        var result = ContractJson.DeserializeResult(reports.Single());
        Assert.False(result.Success);
        Assert.NotEmpty(result.Errors!);
    }

    [Fact]
    public void OneShotIdleCloseSchedulerUnsubscribesBeforeClosingAndIgnoresLaterIdleEvents()
    {
        EventHandler? pendingIdle = null;
        var events = new List<string>();
        var scheduler = new OneShotIdleCloseScheduler(
            handler =>
            {
                events.Add("subscribe");
                pendingIdle = handler;
            },
            handler =>
            {
                Assert.Same(pendingIdle, handler);
                events.Add("unsubscribe");
                pendingIdle = null;
            },
            () => events.Add("close"));

        scheduler.Schedule();
        scheduler.Schedule();

        Assert.Equal(new[] { "subscribe" }, events);
        var idleCallback = pendingIdle;
        Assert.NotNull(idleCallback);

        idleCallback!(null, EventArgs.Empty);
        idleCallback!(null, EventArgs.Empty);

        Assert.Equal(new[] { "subscribe", "unsubscribe", "close" }, events);
    }

    [Fact]
    public void DispatchPersistsCloseResultBeforeSchedulingOneShotCloseAfterCommandReturn()
    {
        const string requestId = "close-ordering";
        const string drawingPath = @"C:\drawings\sample.dwg";
        var reports = new List<string>();
        var store = new JsonFileStore(Path.Combine(
            Path.GetTempPath(),
            "cadagent-t14-command-tests",
            Guid.NewGuid().ToString("N")));
        store.WriteRequest(new IpcRequest
        {
            RequestId = requestId,
            SchemaVersion = ContractConstants.SchemaVersion,
            Operation = "close_disposable",
            DrawingFullPath = drawingPath,
            DrawingSha256 = null,
            Parameters = new Dictionary<string, JsonElement>(StringComparer.Ordinal)
            {
                ["disposable"] = JsonSerializer.SerializeToElement(true),
                ["save_changes"] = JsonSerializer.SerializeToElement(false)
            },
            Approval = null
        });

        var closeCalls = 0;
        var schedulerSawPersistedResult = false;
        var dispatchReturned = false;
        var subscribeCalls = 0;
        var unsubscribeCalls = 0;
        EventHandler? pendingIdle = null;
        var scheduler = new OneShotIdleCloseScheduler(
            handler =>
            {
                subscribeCalls++;
                schedulerSawPersistedResult = File.Exists(store.GetResultPath(requestId));
                pendingIdle = handler;
            },
            handler =>
            {
                unsubscribeCalls++;
                Assert.Same(pendingIdle, handler);
                pendingIdle = null;
            },
            () =>
            {
                Assert.True(dispatchReturned);
                closeCalls++;
            });
        var context = new CommandContext(
            store,
            new SpyDrawingGateway
            {
                ActiveDocumentFullPath = drawingPath
            },
            scheduler.Schedule,
            reports.Add,
            () => new DateTimeOffset(2026, 8, 1, 12, 0, 0, TimeSpan.Zero));

        new CadAgentCommands(() => context).Dispatch();

        var result = store.ReadResult(requestId);
        Assert.True(result.Success);
        Assert.True(result.Payload!["closed_without_saving"].GetBoolean());
        Assert.True(schedulerSawPersistedResult);
        Assert.Equal(1, subscribeCalls);
        Assert.Equal(0, closeCalls);
        Assert.NotNull(pendingIdle);

        var idleCallback = pendingIdle;
        dispatchReturned = true;
        idleCallback!(null, EventArgs.Empty);
        idleCallback!(null, EventArgs.Empty);

        Assert.Equal(1, unsubscribeCalls);
        Assert.Equal(1, closeCalls);
    }

    private static CommandContext CreateContext(
        SpyDrawingGateway gateway,
        ICollection<string> reports,
        Action closeWithoutSaving) =>
        new(
            new JsonFileStore(Path.Combine(
                Path.GetTempPath(),
                "cadagent-t06-command-tests",
                Guid.NewGuid().ToString("N"))),
            gateway,
            closeWithoutSaving,
            reports.Add,
            () => new DateTimeOffset(2026, 8, 1, 12, 0, 0, TimeSpan.Zero));

    private sealed class SpyDrawingGateway : IDrawingGateway
    {
        public string? ActiveDocumentFullPath { get; init; }

        public int ReadEntitiesCallCount { get; private set; }

        public IReadOnlyCollection<string>? LastHandles { get; private set; }

        public IReadOnlyList<EntitySnapshot> ReadEntities(IReadOnlyCollection<string> handles)
        {
            ReadEntitiesCallCount++;
            LastHandles = handles.ToArray();
            return Array.Empty<EntitySnapshot>();
        }

        public DrawingSetupSnapshot ReadDrawingSetup() =>
            throw new NotSupportedException();
    }
}
