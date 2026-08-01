namespace CadAgent.AutoCAD2027.Mechanical;

public sealed record MechanicalCapabilityResult(IReadOnlyList<string> SupportedOperations);

public sealed record MechanicalOperationRequest(string OperationName);

public sealed record MechanicalAttributeSnapshot(string Tag, string Value);

public sealed record MechanicalComponentSnapshot(
    string Handle,
    string BlockName,
    IReadOnlyList<MechanicalAttributeSnapshot> Attributes);

public sealed record MechanicalOperationResult(
    string Status,
    string OperationName,
    bool Changed,
    IReadOnlyList<string> Warnings,
    IReadOnlyList<string> Errors,
    IReadOnlyList<MechanicalComponentSnapshot> Components);
