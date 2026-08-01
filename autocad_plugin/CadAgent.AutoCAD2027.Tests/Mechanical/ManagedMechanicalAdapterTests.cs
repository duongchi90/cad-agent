using CadAgent.AutoCAD2027.Mechanical;
using Xunit;

namespace CadAgent.AutoCAD2027.Tests.Mechanical;

public sealed class ManagedMechanicalAdapterTests
{
    [Fact]
    public void IsAvailableAndReportsExactlyMechanicalBomCapability()
    {
        var adapter = new ManagedMechanicalAdapter(
            new RecordingGateway(Array.Empty<MechanicalComponentSnapshot>()));

        Assert.True(adapter.IsAvailable);
        Assert.Equal(
            new[] { "mechanical_bom" },
            adapter.GetCapabilities().SupportedOperations);
    }

    [Fact]
    public void MechanicalBomReturnsGatewaySnapshotsAsAnUnchangedSuccess()
    {
        var snapshots = new[]
        {
            new MechanicalComponentSnapshot(
                "1A",
                "MECH_PART",
                new[]
                {
                    new MechanicalAttributeSnapshot("PART_NO", "P-100"),
                    new MechanicalAttributeSnapshot("QTY", "2")
                })
        };
        var gateway = new RecordingGateway(snapshots);
        var adapter = new ManagedMechanicalAdapter(gateway);

        var result = adapter.Execute(new MechanicalOperationRequest("mechanical_bom"));

        Assert.Equal("success", result.Status);
        Assert.Equal("mechanical_bom", result.OperationName);
        Assert.False(result.Changed);
        Assert.Empty(result.Warnings);
        Assert.Empty(result.Errors);
        var component = Assert.Single(result.Components);
        Assert.Equal("1A", component.Handle);
        Assert.Equal("MECH_PART", component.BlockName);
        Assert.Equal(
            new[]
            {
                new MechanicalAttributeSnapshot("PART_NO", "P-100"),
                new MechanicalAttributeSnapshot("QTY", "2")
            },
            component.Attributes);
        Assert.Equal(1, gateway.ReadCallCount);
    }

    [Fact]
    public void UnsupportedOperationDoesNotReadTheGateway()
    {
        var gateway = new RecordingGateway(
            new[]
            {
                new MechanicalComponentSnapshot(
                    "1A",
                    "MECH_PART",
                    Array.Empty<MechanicalAttributeSnapshot>())
            });
        var adapter = new ManagedMechanicalAdapter(gateway);

        var result = adapter.Execute(new MechanicalOperationRequest("bom.create"));

        Assert.Equal("not_supported", result.Status);
        Assert.Equal("bom.create", result.OperationName);
        Assert.False(result.Changed);
        Assert.Empty(result.Components);
        Assert.Empty(result.Warnings);
        Assert.Empty(result.Errors);
        Assert.Equal(0, gateway.ReadCallCount);
    }

    private sealed class RecordingGateway : IMechanicalDrawingGateway
    {
        private readonly IReadOnlyList<MechanicalComponentSnapshot> _snapshots;

        public RecordingGateway(IReadOnlyList<MechanicalComponentSnapshot> snapshots)
        {
            _snapshots = snapshots;
        }

        public int ReadCallCount { get; private set; }

        public IReadOnlyList<MechanicalComponentSnapshot> ReadMechanicalComponents()
        {
            ReadCallCount++;
            return _snapshots;
        }
    }
}
