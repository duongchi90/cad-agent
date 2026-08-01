namespace CadAgent.AutoCAD2027.Mechanical;

public sealed class ManagedMechanicalAdapter : IMechanicalAdapter
{
    private const string MechanicalBomOperation = "mechanical_bom";

    private readonly IMechanicalDrawingGateway _gateway;

    public ManagedMechanicalAdapter(IMechanicalDrawingGateway gateway)
    {
        _gateway = gateway;
    }

    public bool IsAvailable => true;

    public MechanicalCapabilityResult GetCapabilities() =>
        new(new[] { MechanicalBomOperation });

    public MechanicalOperationResult Execute(MechanicalOperationRequest request)
    {
        if (request.OperationName != MechanicalBomOperation)
        {
            return new(
                "not_supported",
                request.OperationName,
                false,
                Array.Empty<string>(),
                Array.Empty<string>(),
                Array.Empty<MechanicalComponentSnapshot>());
        }

        return new(
            "success",
            request.OperationName,
            false,
            Array.Empty<string>(),
            Array.Empty<string>(),
            _gateway.ReadMechanicalComponents());
    }
}
