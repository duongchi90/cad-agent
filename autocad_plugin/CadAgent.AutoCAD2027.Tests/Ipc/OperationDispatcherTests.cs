using System.Text.Json;
using CadAgent.AutoCAD2027.Commands;
using CadAgent.AutoCAD2027.Drawing;
using CadAgent.AutoCAD2027.Ipc;
using CadAgent.AutoCAD2027.Mechanical;
using CadAgent.AutoCAD2027.Review;
using CadAgent.AutoCAD2027.Tests.DrawingSetup;
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
    public void DrawingSetupAuditRequiresEmptyParametersAndMatchingFullPath()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\temp\setup.dwg",
            DrawingSetup = DrawingSetupFixtures.VerifiedSnapshot(@"C:\temp\setup.dwg")
        };
        var result = CreateDispatcher(gateway).Dispatch(Request(
            "drawing_setup_audit", "setup-001", @"C:\temp\setup.dwg", Parameters()));

        Assert.True(result.Success);
        Assert.False(result.Changed);
        Assert.Equal(0, result.Payload!["dbmod_after"].GetInt32());
        Assert.Equal(1, gateway.ReadDrawingSetupCallCount);
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
    public void MechanicalBomReturnsSortedReadOnlyComponents()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\temp\bom.dxf"
        };
        var mechanical = new FakeMechanicalAdapter(
            new[]
            {
                Component(
                    "A0",
                    "SECOND"),
                Component(
                    "2F",
                    "FIRST",
                    Attribute("tag ", "B"),
                    Attribute(" TAG", "A"),
                    Attribute("QTY", "2"))
            });
        var dispatcher = CreateDispatcher(gateway, mechanicalAdapter: mechanical);

        var result = dispatcher.Dispatch(Request(
            "mechanical_bom",
            "bom-request",
            @"C:\temp\bom.dxf",
            Parameters()));

        Assert.True(result.Success);
        Assert.Equal("mechanical_bom", result.Operation);
        Assert.False(result.Changed);
        Assert.Equal(new[] { "2F", "A0" }, result.EntityHandles);
        Assert.Equal(2, result.Payload!["component_count"].GetInt32());

        var components = result.Payload["components"].EnumerateArray().ToArray();
        Assert.Equal(new[] { "2F", "A0" }, components.Select(component => component.GetProperty("handle").GetString()));
        Assert.Equal("FIRST", components[0].GetProperty("block_name").GetString());
        Assert.Equal(
            new[] { "QTY:2", "TAG:A", "TAG:B" },
            components[0]
                .GetProperty("attributes")
                .EnumerateArray()
                .Select(attribute => $"{attribute.GetProperty("tag").GetString()}:{attribute.GetProperty("value").GetString()}"));
        Assert.Empty(components[1].GetProperty("attributes").EnumerateArray());
        Assert.Equal(1, mechanical.ExecuteCallCount);
    }

    [Fact]
    public void MechanicalBomRejectsAFullPathDocumentMismatchBeforeReadingMechanicalGateway()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\other\bom.dxf"
        };
        var mechanical = new FakeMechanicalAdapter(Array.Empty<MechanicalComponentSnapshot>());
        var dispatcher = CreateDispatcher(gateway, mechanicalAdapter: mechanical);

        var result = dispatcher.Dispatch(Request(
            "mechanical_bom",
            "mismatch-bom-request",
            @"C:\temp\bom.dxf",
            Parameters()));

        Assert.False(result.Success);
        Assert.Contains(result.Errors!, error => error.Contains("full path", StringComparison.OrdinalIgnoreCase));
        Assert.Equal(0, mechanical.ExecuteCallCount);
    }

    [Fact]
    public void MechanicalBomUsesUnavailableDefaultNoOpAdapter()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\temp\bom.dxf"
        };
        var dispatcher = CreateDispatcher(gateway);

        var result = dispatcher.Dispatch(Request(
            "mechanical_bom",
            "no-op-bom-request",
            @"C:\temp\bom.dxf",
            Parameters()));

        Assert.False(result.Success);
        Assert.Contains(result.Errors!, error => error.Contains("not supported", StringComparison.OrdinalIgnoreCase));
        Assert.Empty(result.EntityHandles!);
    }

    [Fact]
    public void MechanicalBomInvalidParametersBlockAdapterAndGatewayExecution()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\temp\bom.dxf"
        };
        var mechanicalGateway = new RecordingMechanicalGateway(
            new[] { Component("2F", "COMP_FRAME") });
        var mechanical = new ManagedMechanicalAdapter(mechanicalGateway);
        var dispatcher = CreateDispatcher(gateway, mechanicalAdapter: mechanical);

        var result = dispatcher.Dispatch(Request(
            "mechanical_bom",
            "invalid-bom-request",
            @"C:\temp\bom.dxf",
            Parameters(("filter", JsonSerializer.SerializeToElement("COMP_FRAME")))));

        Assert.False(result.Success);
        Assert.Contains(result.Errors!, error => error.Contains("empty", StringComparison.OrdinalIgnoreCase));
        Assert.Equal(0, mechanicalGateway.ReadCallCount);
    }

    [Fact]
    public void MechanicalBomPropagatesGatewayWarningsThroughTheT02Boundary()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\temp\bom.dxf"
        };
        var mechanicalWarnings = new List<string>();
        var mechanicalGateway = new WarningingMechanicalGateway(
            mechanicalWarnings,
            new[] { Component("2F", "COMP_FRAME") });
        var mechanical = new ManagedMechanicalAdapter(mechanicalGateway);
        var dispatcher = CreateDispatcher(
            gateway,
            mechanicalAdapter: mechanical,
            mechanicalWarnings: mechanicalWarnings);

        var result = dispatcher.Dispatch(Request(
            "mechanical_bom",
            "warning-bom-request",
            @"C:\temp\bom.dxf",
            Parameters()));

        Assert.True(result.Success);
        Assert.Contains(result.Warnings!, warning => warning.Contains("direct attribute", StringComparison.OrdinalIgnoreCase));
        Assert.Empty(result.Errors!);
    }

    [Fact]
    public void MechanicalBomPropagatesAdapterWarningsAndErrors()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\temp\bom.dxf"
        };
        var mechanical = new FakeMechanicalAdapter(
            Array.Empty<MechanicalComponentSnapshot>(),
            status: "failure",
            warnings: new[] { "mechanical warning" },
            errors: new[] { "mechanical error" });
        var dispatcher = CreateDispatcher(gateway, mechanicalAdapter: mechanical);

        var result = dispatcher.Dispatch(Request(
            "mechanical_bom",
            "warning-error-bom-request",
            @"C:\temp\bom.dxf",
            Parameters()));

        Assert.False(result.Success);
        Assert.Contains("mechanical warning", result.Warnings!);
        Assert.Contains("mechanical error", result.Errors!);
    }

    [Fact]
    public void MechanicalBomTransactionFailureBecomesFailureResult()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\temp\bom.dxf"
        };
        var mechanicalGateway = new ThrowingMechanicalGateway(
            new InvalidOperationException("mechanical transaction failed"));
        var mechanical = new ManagedMechanicalAdapter(mechanicalGateway);
        var dispatcher = CreateDispatcher(gateway, mechanicalAdapter: mechanical);

        var result = dispatcher.Dispatch(Request(
            "mechanical_bom",
            "transaction-bom-request",
            @"C:\temp\bom.dxf",
            Parameters()));

        Assert.False(result.Success);
        Assert.Contains("mechanical transaction failed", result.Errors!);
        Assert.Empty(result.EntityHandles!);
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
        Action? closeWithoutSaving = null,
        IMechanicalAdapter? mechanicalAdapter = null,
        ICollection<string>? mechanicalWarnings = null) =>
        new(new CommandContext(
            new JsonFileStore(Path.Combine(Path.GetTempPath(), "cadagent-t06-tests", Guid.NewGuid().ToString("N"))),
            gateway,
            closeWithoutSaving ?? (() => { }),
            clock: () => new DateTimeOffset(2026, 8, 1, 12, 0, 0, TimeSpan.Zero),
            mechanicalAdapter: mechanicalAdapter,
            mechanicalWarnings: mechanicalWarnings));

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

    private static MechanicalComponentSnapshot Component(
        string handle,
        string blockName,
        params MechanicalAttributeSnapshot[] attributes) =>
        new(handle, blockName, attributes);

    private static MechanicalAttributeSnapshot Attribute(string tag, string value) =>
        new(tag, value);

    private sealed class StubDrawingGateway : IDrawingGateway
    {
        public string? ActiveDocumentFullPath { get; init; }

        public IReadOnlyList<EntitySnapshot> Entities { get; init; } = Array.Empty<EntitySnapshot>();

        public Exception? ExceptionToThrow { get; init; }

        public int ReadEntitiesCallCount { get; private set; }

        public DrawingSetupSnapshot? DrawingSetup { get; init; }

        public int ReadDrawingSetupCallCount { get; private set; }

        public IReadOnlyList<EntitySnapshot> ReadEntities(IReadOnlyCollection<string> handles)
        {
            ReadEntitiesCallCount++;
            if (ExceptionToThrow is not null)
            {
                throw ExceptionToThrow;
            }

            return Entities;
        }

        public DrawingSetupSnapshot ReadDrawingSetup()
        {
            ReadDrawingSetupCallCount++;
            return DrawingSetup ?? throw new InvalidOperationException("Drawing setup fixture is missing.");
        }
    }

    private sealed class FakeMechanicalAdapter : IMechanicalAdapter
    {
        private readonly IReadOnlyList<MechanicalComponentSnapshot> _components;
        private readonly string _status;
        private readonly IReadOnlyList<string> _warnings;
        private readonly IReadOnlyList<string> _errors;

        public FakeMechanicalAdapter(
            IReadOnlyList<MechanicalComponentSnapshot> components,
            string status = "success",
            IReadOnlyList<string>? warnings = null,
            IReadOnlyList<string>? errors = null)
        {
            _components = components;
            _status = status;
            _warnings = warnings ?? Array.Empty<string>();
            _errors = errors ?? Array.Empty<string>();
        }

        public int ExecuteCallCount { get; private set; }

        public bool IsAvailable => true;

        public MechanicalCapabilityResult GetCapabilities() =>
            new(new[] { "mechanical_bom" });

        public MechanicalOperationResult Execute(MechanicalOperationRequest request)
        {
            ExecuteCallCount++;
            return new(
                _status,
                request.OperationName,
                false,
                _warnings,
                _errors,
                _components);
        }
    }

    private sealed class RecordingMechanicalGateway : IMechanicalDrawingGateway
    {
        private readonly IReadOnlyList<MechanicalComponentSnapshot> _components;

        public RecordingMechanicalGateway(IReadOnlyList<MechanicalComponentSnapshot> components)
        {
            _components = components;
        }

        public int ReadCallCount { get; private set; }

        public IReadOnlyList<MechanicalComponentSnapshot> ReadMechanicalComponents()
        {
            ReadCallCount++;
            return _components;
        }
    }

    private sealed class WarningingMechanicalGateway : IMechanicalDrawingGateway
    {
        private readonly ICollection<string> _warnings;
        private readonly IReadOnlyList<MechanicalComponentSnapshot> _components;

        public WarningingMechanicalGateway(
            ICollection<string> warnings,
            IReadOnlyList<MechanicalComponentSnapshot> components)
        {
            _warnings = warnings;
            _components = components;
        }

        public IReadOnlyList<MechanicalComponentSnapshot> ReadMechanicalComponents()
        {
            _warnings.Add("Skipped unreadable direct attribute on insert 2F.");
            return _components;
        }
    }

    private sealed class ThrowingMechanicalGateway : IMechanicalDrawingGateway
    {
        private readonly Exception _exception;

        public ThrowingMechanicalGateway(Exception exception)
        {
            _exception = exception;
        }

        public IReadOnlyList<MechanicalComponentSnapshot> ReadMechanicalComponents() =>
            throw _exception;
    }
}
