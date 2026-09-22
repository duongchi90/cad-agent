namespace CadAgent.AutoCAD2027.Drawing;

public static class BoundedNativeLineEditOperationNames
{
    public const string Edit = "bounded_native_line_edit";
    public const string ResultSchemaVersion = "bounded-native-line-edit-1.1";
}

public static class BoundedNativeLineEditDurableStates
{
    public const string Changed = "CHANGED";
    public const string Unchanged = "UNCHANGED";
    public const string Uncertain = "UNCERTAIN";

    public static string ResolveAfterSaveFailure(bool rollbackPersisted) =>
        rollbackPersisted ? Unchanged : Uncertain;
}

public sealed record BoundedNativeLineEditRequest(
    string RequestId,
    string DrawingFullPath,
    string DrawingSha256,
    string RunId,
    string TargetRole,
    IReadOnlyList<string> TargetHandles,
    IReadOnlyList<string> ProtectedCompetingHandles,
    string ExpectedType,
    double ExpectedBeforeLength,
    double TargetAfterLength,
    double LengthTolerance,
    string Direction,
    bool Save,
    string ApprovalReference);

public sealed record BoundedNativeLineEditEntityEvidence(
    string Handle,
    string Type,
    string Layer,
    string OwnerHandle,
    string OwnerName,
    IReadOnlyList<string> ReferenceHandles,
    bool SharedWithCompetingOccurrence,
    double BeforeLength,
    double AfterLength,
    double BeforeStartX,
    double BeforeStartY,
    double BeforeEndX,
    double BeforeEndY,
    double AfterStartX,
    double AfterStartY,
    double AfterEndX,
    double AfterEndY);

public sealed record BoundedNativeLineEditSnapshot(
    bool Success,
    string? DrawingFullPath,
    bool Changed,
    IReadOnlyList<string> EntityHandles,
    IReadOnlyList<string> Warnings,
    IReadOnlyList<string> Errors,
    int DbmodBefore,
    int DbmodAfter,
    bool SavePerformed,
    string DurableState,
    IReadOnlyList<BoundedNativeLineEditEntityEvidence> TargetEntities,
    IReadOnlyList<BoundedNativeLineEditEntityEvidence> ProtectedEntities)
{
    public static BoundedNativeLineEditSnapshot Failure(
        string? drawingFullPath,
        IEnumerable<string> errors) =>
        new(
            Success: false,
            DrawingFullPath: drawingFullPath,
            Changed: false,
            EntityHandles: Array.Empty<string>(),
            Warnings: Array.Empty<string>(),
            Errors: errors.ToArray(),
            DbmodBefore: 0,
            DbmodAfter: 0,
            SavePerformed: false,
            DurableState: BoundedNativeLineEditDurableStates.Unchanged,
            TargetEntities: Array.Empty<BoundedNativeLineEditEntityEvidence>(),
            ProtectedEntities: Array.Empty<BoundedNativeLineEditEntityEvidence>());
}
