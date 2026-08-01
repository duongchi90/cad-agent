namespace CadAgent.AutoCAD2027.Mechanical;

public sealed class NoOpMechanicalAdapter : IMechanicalAdapter
{
    public bool IsAvailable => false;

    public MechanicalCapabilityResult GetCapabilities() =>
        new(Array.Empty<string>());

    public MechanicalOperationResult Execute(MechanicalOperationRequest request) =>
        new(
            "not_supported",
            request.OperationName,
            false,
            Array.Empty<string>(),
            Array.Empty<string>(),
            Array.Empty<MechanicalComponentSnapshot>());
}
