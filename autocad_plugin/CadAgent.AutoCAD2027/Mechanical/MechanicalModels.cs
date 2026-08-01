namespace CadAgent.AutoCAD2027.Mechanical;

public sealed record MechanicalCapabilityResult(IReadOnlyList<string> SupportedOperations);

public sealed record MechanicalOperationRequest(string OperationName);

public sealed record MechanicalOperationResult(string Status, string OperationName);
