using System.Text.Json.Serialization;

namespace CadAgent.AutoCAD2027.Drawing;

public static class ExactBaseXrefOperationNames
{
    public const string Inspection = "exact_base_xref_inspection";
    public const string Extraction = "exact_base_xref_extraction";
    public const string InspectionTargetRole = "INSPECTION_HOST";
    public const string ExtractionTargetRole = "DISPOSABLE_CANDIDATE";
    public const string ReusedFromBaseCad = "REUSED_FROM_BASE_CAD";
    public const string TransformPolicy = "LOCAL_TRANSLATION_ROTATION_UNIFORM_SCALE_ONLY";
}

public sealed class ExactBaseXrefSourceExpectation
{
    [JsonPropertyName("source_id")]
    public string? SourceId { get; init; }

    [JsonPropertyName("revision")]
    public string? Revision { get; init; }

    [JsonPropertyName("sha256")]
    public string? Sha256 { get; init; }
}

public sealed class ExactBaseXrefIdentityExpectation
{
    [JsonPropertyName("vehicle")]
    public string? Vehicle { get; init; }

    [JsonPropertyName("model")]
    public string? Model { get; init; }
}

public class ExactBaseXrefDimensionExpectation
{
    [JsonPropertyName("control")]
    public string? Control { get; init; }

    [JsonPropertyName("target")]
    public double Target { get; init; }

    [JsonPropertyName("tolerance")]
    public double Tolerance { get; init; }

    [JsonPropertyName("unit")]
    public string? Unit { get; init; }
}

public sealed class ExactBaseXrefReference
{
    [JsonPropertyName("name")]
    public string? Name { get; init; }
}

public class ExactBaseXrefComponentExpectation
{
    [JsonPropertyName("component_type")]
    public string? ComponentType { get; init; }

    [JsonPropertyName("logical_component_id")]
    public string? LogicalComponentId { get; init; }

    [JsonPropertyName("provenance")]
    public string? Provenance { get; init; }

    [JsonPropertyName("source_block")]
    public string? SourceBlock { get; init; }

    [JsonPropertyName("source_handle")]
    public string? SourceHandle { get; init; }

    [JsonPropertyName("source_layer")]
    public string? SourceLayer { get; init; }
}

public sealed class ExactBaseXrefInspectionExpectations
{
    [JsonPropertyName("source")]
    public ExactBaseXrefSourceExpectation? Source { get; init; }

    [JsonPropertyName("identity")]
    public ExactBaseXrefIdentityExpectation? Identity { get; init; }

    [JsonPropertyName("critical_dimensions")]
    public List<ExactBaseXrefDimensionExpectation>? CriticalDimensions { get; init; }

    [JsonPropertyName("xref")]
    public ExactBaseXrefReference? Xref { get; init; }

    [JsonPropertyName("components")]
    public List<ExactBaseXrefComponentExpectation>? Components { get; init; }
}

public sealed class ExactBaseXrefPoint
{
    [JsonPropertyName("x")]
    public double X { get; init; }

    [JsonPropertyName("y")]
    public double Y { get; init; }

    [JsonPropertyName("z")]
    public double Z { get; init; }
}

public sealed class ExactBaseXrefBounding
{
    [JsonPropertyName("min")]
    public ExactBaseXrefPoint? Min { get; init; }

    [JsonPropertyName("max")]
    public ExactBaseXrefPoint? Max { get; init; }
}

public sealed class ExactBaseXrefTransform
{
    [JsonPropertyName("rotation_degrees")]
    public double RotationDegrees { get; init; }

    [JsonPropertyName("translation")]
    public ExactBaseXrefPoint? Translation { get; init; }

    [JsonPropertyName("uniform_scale")]
    public double UniformScale { get; init; }
}

public sealed class ExactBaseXrefPlanComponent : ExactBaseXrefComponentExpectation
{
    [JsonPropertyName("bounding")]
    public ExactBaseXrefBounding? Bounding { get; init; }

    [JsonPropertyName("transform")]
    public ExactBaseXrefTransform? Transform { get; init; }
}

public sealed class ExactBaseXrefApproval
{
    [JsonPropertyName("reference")]
    public string? Reference { get; init; }

    [JsonPropertyName("status")]
    public string? Status { get; init; }
}

public sealed class ExactBaseXrefPlanSource
{
    [JsonPropertyName("relative_path")]
    public string? RelativePath { get; init; }

    [JsonPropertyName("revision")]
    public string? Revision { get; init; }

    [JsonPropertyName("sha256")]
    public string? Sha256 { get; init; }

    [JsonPropertyName("source_id")]
    public string? SourceId { get; init; }
}

public sealed class ExactBaseXrefView
{
    [JsonPropertyName("identity")]
    public string? Identity { get; init; }

    [JsonPropertyName("name")]
    public string? Name { get; init; }
}

public sealed class ExactBaseXrefExtractionPlan
{
    [JsonPropertyName("approval")]
    public ExactBaseXrefApproval? Approval { get; init; }

    [JsonPropertyName("base_source")]
    public ExactBaseXrefPlanSource? BaseSource { get; init; }

    [JsonPropertyName("components")]
    public List<ExactBaseXrefPlanComponent>? Components { get; init; }

    [JsonPropertyName("impacted_views")]
    public List<ExactBaseXrefView>? ImpactedViews { get; init; }

    [JsonPropertyName("inspection_id")]
    public string? InspectionId { get; init; }

    [JsonPropertyName("plan_id")]
    public string? PlanId { get; init; }

    [JsonPropertyName("provenance")]
    public string? Provenance { get; init; }

    [JsonPropertyName("request_id")]
    public string? RequestId { get; init; }

    [JsonPropertyName("run_id")]
    public string? RunId { get; init; }

    [JsonPropertyName("schema_version")]
    public string? SchemaVersion { get; init; }

    [JsonPropertyName("source_revision")]
    public string? SourceRevision { get; init; }

    [JsonPropertyName("target_drawing_sha256")]
    public string? TargetDrawingSha256 { get; init; }

    [JsonPropertyName("transform_policy")]
    public string? TransformPolicy { get; init; }
}

public class ExactBaseXrefInspectionParameters
{
    [JsonPropertyName("run_id")]
    public string? RunId { get; init; }

    [JsonPropertyName("source_full_path")]
    public string? SourceFullPath { get; init; }

    [JsonPropertyName("source_revision")]
    public string? SourceRevision { get; init; }

    [JsonPropertyName("inspection_expectations")]
    public ExactBaseXrefInspectionExpectations? InspectionExpectations { get; init; }

    [JsonPropertyName("target_role")]
    public string? TargetRole { get; init; }
}

public sealed class ExactBaseXrefExtractionParameters : ExactBaseXrefInspectionParameters
{
    [JsonPropertyName("extraction_plan")]
    public ExactBaseXrefExtractionPlan? ExtractionPlan { get; init; }

    [JsonPropertyName("candidate_output_path")]
    public string? CandidateOutputPath { get; init; }
}

public sealed class ExactBaseXrefLiveInspection
{
    [JsonPropertyName("base_source")]
    public ExactBaseXrefPlanSource? BaseSource { get; init; }

    [JsonPropertyName("schema_version")]
    public string? SchemaVersion { get; init; }

    [JsonPropertyName("capture_timestamp")]
    public DateTimeOffset CaptureTimestamp { get; init; }

    [JsonPropertyName("changed")]
    public bool Changed { get; init; }

    [JsonPropertyName("dbmod_before")]
    public int DbmodBefore { get; init; }

    [JsonPropertyName("dbmod_after")]
    public int DbmodAfter { get; init; }

    [JsonPropertyName("eligible")]
    public bool Eligible { get; init; }

    [JsonPropertyName("components")]
    public List<ExactBaseXrefLiveComponent>? Components { get; init; }

    [JsonPropertyName("conflicts")]
    public List<string>? Conflicts { get; init; }

    [JsonPropertyName("critical_dimensions")]
    public List<ExactBaseXrefLiveDimension>? CriticalDimensions { get; init; }

    [JsonPropertyName("identity_observations")]
    public List<ExactBaseXrefIdentityObservation>? IdentityObservations { get; init; }

    [JsonPropertyName("inspection_id")]
    public string? InspectionId { get; init; }

    [JsonPropertyName("request_id")]
    public string? RequestId { get; init; }

    [JsonPropertyName("run_id")]
    public string? RunId { get; init; }

    [JsonPropertyName("target_drawing_sha256")]
    public string? TargetDrawingSha256 { get; init; }

    [JsonPropertyName("warnings")]
    public List<string>? Warnings { get; init; }

    [JsonPropertyName("xref")]
    public ExactBaseXrefLiveXref? Xref { get; init; }
}

public sealed class ExactBaseXrefIdentityObservation
{
    [JsonPropertyName("field")]
    public string? Field { get; init; }

    [JsonPropertyName("observed")]
    public string? Observed { get; init; }

    [JsonPropertyName("status")]
    public string? Status { get; init; }

    [JsonPropertyName("target")]
    public string? Target { get; init; }
}

public sealed class ExactBaseXrefLiveDimension : ExactBaseXrefDimensionExpectation
{
    [JsonPropertyName("observed")]
    public double Observed { get; init; }

    [JsonPropertyName("status")]
    public string? Status { get; init; }
}

public sealed class ExactBaseXrefLiveXref
{
    [JsonPropertyName("name")]
    public string? Name { get; init; }

    [JsonPropertyName("read_only")]
    public bool ReadOnly { get; init; }

    [JsonPropertyName("status")]
    public string? Status { get; init; }
}

public sealed class ExactBaseXrefLiveComponent : ExactBaseXrefComponentExpectation
{
    [JsonPropertyName("bounding")]
    public ExactBaseXrefBounding? Bounding { get; init; }
}

public sealed class ExactBaseXrefCandidateEvidence
{
    [JsonPropertyName("source_mutated")]
    public bool SourceMutated { get; init; }

    [JsonPropertyName("accepted_target_overwrite")]
    public bool AcceptedTargetOverwrite { get; init; }

    [JsonPropertyName("source_handle_to_candidate_handle")]
    public Dictionary<string, string>? SourceHandleToCandidateHandle { get; init; }
}
