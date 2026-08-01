using CadAgent.AutoCAD2027.Mechanical;
using Xunit;

namespace CadAgent.AutoCAD2027.Tests.Mechanical;

public sealed class NoOpMechanicalAdapterTests
{
    [Fact]
    public void IsUnavailable()
    {
        var adapter = new NoOpMechanicalAdapter();

        Assert.False(adapter.IsAvailable);
    }

    [Fact]
    public void ReportsNoSupportedOperations()
    {
        var adapter = new NoOpMechanicalAdapter();

        var capabilities = adapter.GetCapabilities();

        Assert.Empty(capabilities.SupportedOperations);
    }

    [Fact]
    public void ReportsNotSupported()
    {
        var adapter = new NoOpMechanicalAdapter();

        var result = adapter.Execute(new MechanicalOperationRequest("bom.create"));

        Assert.Equal("not_supported", result.Status);
    }

    [Fact]
    public void PreservesTheRequestedOperationName()
    {
        const string operationName = "bom.create";
        var adapter = new NoOpMechanicalAdapter();

        var result = adapter.Execute(new MechanicalOperationRequest(operationName));

        Assert.Equal(operationName, result.OperationName);
    }
}
