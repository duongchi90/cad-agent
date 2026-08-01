using CadAgent.AutoCAD2027.Mechanical;

namespace CadAgent.AutoCAD2027.Tests.Mechanical;

public static class NoOpMechanicalAdapterTests
{
    public static void RunAll()
    {
        IsUnavailable();
        ReportsNoSupportedOperations();
        ReportsNotSupported();
        PreservesTheRequestedOperationName();
    }

    public static void IsUnavailable()
    {
        var adapter = new NoOpMechanicalAdapter();

        Assert(!adapter.IsAvailable, "The no-op adapter must be unavailable.");
    }

    public static void ReportsNoSupportedOperations()
    {
        var adapter = new NoOpMechanicalAdapter();

        var capabilities = adapter.GetCapabilities();

        Assert(capabilities.SupportedOperations.Count == 0,
            "The no-op adapter must report no supported operations.");
    }

    public static void ReportsNotSupported()
    {
        var adapter = new NoOpMechanicalAdapter();

        var result = adapter.Execute(new MechanicalOperationRequest("bom.create"));

        Assert(result.Status == "not_supported",
            "The no-op adapter must report not_supported.");
    }

    public static void PreservesTheRequestedOperationName()
    {
        const string operationName = "bom.create";
        var adapter = new NoOpMechanicalAdapter();

        var result = adapter.Execute(new MechanicalOperationRequest(operationName));

        Assert(result.OperationName == operationName,
            "The no-op result must preserve the requested operation name.");
    }

    private static void Assert(bool condition, string message)
    {
        if (!condition)
        {
            throw new InvalidOperationException(message);
        }
    }
}
