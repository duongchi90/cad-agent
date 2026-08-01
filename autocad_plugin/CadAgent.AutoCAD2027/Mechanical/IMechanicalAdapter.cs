namespace CadAgent.AutoCAD2027.Mechanical;

public interface IMechanicalAdapter
{
    bool IsAvailable { get; }

    MechanicalCapabilityResult GetCapabilities();

    MechanicalOperationResult Execute(MechanicalOperationRequest request);
}
