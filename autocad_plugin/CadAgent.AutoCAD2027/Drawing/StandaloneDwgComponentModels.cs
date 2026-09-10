namespace CadAgent.AutoCAD2027.Drawing;

internal static class StandaloneDwgComponentEntityTypeContract
{
    public const string Insert = "INSERT";

    public static string FromNativeTypeName(string nativeTypeName) =>
        string.Equals(nativeTypeName, "BlockReference", StringComparison.Ordinal)
            ? Insert
            : nativeTypeName.ToUpperInvariant();
}

public static class StandaloneDwgComponentOperationNames
{
    public const string Inspection = "standalone_dwg_component_inspection";
    public const string Extraction = "standalone_dwg_component_extraction";
}

public sealed class StandaloneDwgComponentApproval
{
    public string? Reference { get; init; }

    public string? Status { get; init; }
}

public sealed class StandaloneDwgComponentSelectionGroup
{
    public string? GroupId { get; init; }

    public string? LogicalComponentId { get; init; }

    public IReadOnlyList<string> SourceHandles { get; init; } = Array.Empty<string>();

    public IReadOnlyList<string> ExpectedEntityTypes { get; init; } = Array.Empty<string>();

    public IReadOnlyList<string> SourceLayerExpectations { get; init; } = Array.Empty<string>();
}

public sealed class StandaloneDwgComponentInspectionRequest
{
    public string? SchemaVersion { get; init; } = "standalone-dwg-component-inspection-1.0";

    public string? RequestId { get; init; }

    public string? RunId { get; init; }

    public string? SourceDrawingPath { get; init; }

    public string? SourceDrawingSha256 { get; init; }

    public string? SourceSetupAuditSha256 { get; init; }

    public IReadOnlyList<StandaloneDwgComponentSelectionGroup> SelectionGroups { get; init; } =
        Array.Empty<StandaloneDwgComponentSelectionGroup>();

    public int ExpectedDbmod { get; init; }

    public StandaloneDwgComponentApproval? Approval { get; init; }
}

public sealed class StandaloneDwgComponentPoint
{
    public double X { get; init; }

    public double Y { get; init; }

    public double Z { get; init; }
}

public sealed class StandaloneDwgComponentBounds
{
    public StandaloneDwgComponentPoint? Min { get; init; }

    public StandaloneDwgComponentPoint? Max { get; init; }
}

public sealed class StandaloneDwgComponentEntitySnapshot
{
    public string? SourceHandle { get; init; }

    public string? EntityType { get; init; }

    public string? Layer { get; init; }

    public StandaloneDwgComponentBounds? Bounds { get; init; }
}

public sealed class StandaloneDwgComponentInspectionSnapshot
{
    public bool Success { get; init; }

    public string? DrawingFullPath { get; init; }

    public bool Changed { get; init; }

    public bool ReadOnly { get; init; }

    public bool IsXrefSource { get; init; }

    public bool Eligible { get; init; }

    public string? SourceSha256Before { get; init; }

    public string? SourceSha256After { get; init; }

    public int DbmodBefore { get; init; }

    public int DbmodAfter { get; init; }

    public IReadOnlyList<StandaloneDwgComponentEntitySnapshot> Entities { get; init; } =
        Array.Empty<StandaloneDwgComponentEntitySnapshot>();

    public IReadOnlyList<string> Warnings { get; init; } = Array.Empty<string>();

    public IReadOnlyList<string> Errors { get; init; } = Array.Empty<string>();

    public static StandaloneDwgComponentInspectionSnapshot Failure(
        string? drawingFullPath,
        IEnumerable<string> errors) => new()
        {
            Success = false,
            DrawingFullPath = drawingFullPath,
            Changed = false,
            ReadOnly = false,
            Eligible = false,
            Entities = Array.Empty<StandaloneDwgComponentEntitySnapshot>(),
            Warnings = Array.Empty<string>(),
            Errors = errors.ToArray()
        };
}

public sealed class StandaloneDwgComponentTransform
{
    public double RotationDegrees { get; init; }

    public StandaloneDwgComponentPoint? Translation { get; init; }

    public double UniformScale { get; init; } = 1.0;
}

public sealed class StandaloneDwgComponentPlanComponent
{
    public string? GroupId { get; init; }

    public string? LogicalComponentId { get; init; }

    public IReadOnlyList<string> SourceHandles { get; init; } = Array.Empty<string>();

    public StandaloneDwgComponentTransform? Transform { get; init; }
}

public sealed class StandaloneDwgComponentExtractionPlan
{
    public string? SchemaVersion { get; init; } = "standalone-dwg-component-extraction-1.0";

    public string? PlanId { get; init; }

    public string? RequestId { get; init; }

    public string? RunId { get; init; }

    public string? InspectionId { get; init; }

    public string? InspectionSha256 { get; init; }

    public string? SourceDrawingSha256 { get; init; }

    public string? CandidateOutputPath { get; init; }

    public string? CandidateBaseModel { get; init; }

    public IReadOnlyList<StandaloneDwgComponentPlanComponent> Components { get; init; } =
        Array.Empty<StandaloneDwgComponentPlanComponent>();

    public string? TransformPolicy { get; init; }

    public StandaloneDwgComponentApproval? Approval { get; init; }
}

public sealed class StandaloneDwgComponentHandleMapping
{
    public string? SourceHandle { get; init; }

    public string? CandidateHandle { get; init; }
}

public sealed class StandaloneDwgComponentCandidateSnapshot
{
    public bool CandidateCreated { get; init; }

    public string? CandidateOutputPath { get; init; }

    // Raw filesystem identity is kept for the internal cleanup recheck only.
    public string? CandidateCleanupIdentity { get; init; }

    public string? CandidateOutputIdentity { get; init; }

    public string? CandidateOutputSha256 { get; init; }

    public bool SourceMutated { get; init; }

    public string? SourceSha256Before { get; init; }

    public string? SourceSha256After { get; init; }

    public int SourceDbmodBefore { get; init; }

    public int SourceDbmodAfter { get; init; }

    public bool SavePerformed { get; init; }

    public bool Reopenable { get; init; }

    public IReadOnlyList<StandaloneDwgComponentHandleMapping> Mappings { get; init; } =
        Array.Empty<StandaloneDwgComponentHandleMapping>();
}

public sealed class StandaloneDwgComponentExtractionSnapshot
{
    public bool Success { get; init; }

    public bool Changed { get; init; }

    public IReadOnlyList<string> EntityHandles { get; init; } = Array.Empty<string>();

    public StandaloneDwgComponentCandidateSnapshot? Evidence { get; init; }

    public IReadOnlyList<string> Warnings { get; init; } = Array.Empty<string>();

    public IReadOnlyList<string> Errors { get; init; } = Array.Empty<string>();

    public static StandaloneDwgComponentExtractionSnapshot Failure(
        IEnumerable<string> errors,
        StandaloneDwgComponentCandidateSnapshot? evidence = null) => new()
        {
            Success = false,
            Changed = false,
            EntityHandles = Array.Empty<string>(),
            Evidence = evidence,
            Warnings = Array.Empty<string>(),
            Errors = errors.ToArray()
        };
}

public interface IStandaloneDwgComponentDatabase
{
    string? ActiveDocumentFullPath { get; }

    bool? IsSourceReadOnly { get; }

    string ComputeSourceSha256();

    StandaloneDwgComponentInspectionSnapshot ReadSelectedEntities(
        StandaloneDwgComponentInspectionRequest request);

    StandaloneDwgComponentCandidateSnapshot ExtractToNewCandidate(
        StandaloneDwgComponentExtractionPlan plan);

    bool IsCandidatePathAbsent(string path);

    string CaptureCandidateIdentity(string path);

    bool DeleteCandidateIfIdentityMatches(string path, string identity);
}
