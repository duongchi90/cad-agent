using System.Globalization;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Microsoft.Win32.SafeHandles;
using CadAgent.AutoCAD2027.Ipc;

namespace CadAgent.AutoCAD2027.Drawing;

public sealed record ExactBaseXrefServerConfiguration(
    string? DisposableRoot,
    string? AcceptedDwgPath,
    string? AcceptedDwgSha256,
    string? ExactBaseSourcePath,
    string? ExactBaseSourceSha256,
    string? ExactBaseSourceRevision);

public sealed class ExactBaseXrefPolicyException : InvalidOperationException
{
    public ExactBaseXrefPolicyException(string code, string message)
        : base($"{code}: {message}")
    {
        Code = code;
    }

    public string Code { get; }
}

public sealed class ExactBaseXrefPolicy
{
    public const string DisposableRootEnvironmentVariable = "CAD_AGENT_S3B_DISPOSABLE_ROOT";
    public const string AcceptedDwgPathEnvironmentVariable = "CAD_AGENT_S3B_ACCEPTED_DWG_PATH";
    public const string AcceptedDwgSha256EnvironmentVariable = "CAD_AGENT_S3B_ACCEPTED_DWG_SHA256";
    public const string ExactBaseSourcePathEnvironmentVariable = "CAD_AGENT_S3B_EXACT_BASE_SOURCE_PATH";
    public const string ExactBaseSourceSha256EnvironmentVariable = "CAD_AGENT_S3B_EXACT_BASE_SOURCE_SHA256";
    public const string ExactBaseSourceRevisionEnvironmentVariable = "CAD_AGENT_S3B_EXACT_BASE_SOURCE_REVISION";

    public const string ConfigurationRequiredCode = "S3B_CONFIGURATION_REQUIRED";
    public const string RequestInvalidCode = "S3B_REQUEST_INVALID";
    public const string ActiveDocumentMismatchCode = "S3B_ACTIVE_DOCUMENT_MISMATCH";
    public const string SourceIdentityMismatchCode = "S3B_SOURCE_IDENTITY_MISMATCH";
    public const string SourceHashMismatchCode = "S3B_SOURCE_HASH_MISMATCH";
    public const string SourceRevisionMismatchCode = "S3B_SOURCE_REVISION_MISMATCH";
    public const string CandidatePathUnsafeCode = "S3B_CANDIDATE_PATH_UNSAFE";
    public const string CandidateOutputExistsCode = "S3B_CANDIDATE_OUTPUT_EXISTS";
    public const string SourceAliasCode = "S3B_SOURCE_ALIAS";
    public const string AcceptedAliasCode = "S3B_ACCEPTED_ALIAS";
    public const string ApprovalRequiredCode = "S3B_APPROVAL_REQUIRED";
    public const string ApprovalMismatchCode = "S3B_APPROVAL_MISMATCH";
    public const string TransformPolicyCode = "S3B_TRANSFORM_POLICY";
    public const string LivePreflightRequiredCode = "S3B_LIVE_PREFLIGHT_REQUIRED";
    public const string ReparsePointCode = "S3B_REPARSE_POINT_REJECTED";

    private static readonly Regex IdentifierPattern = new(
        "^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$",
        RegexOptions.CultureInvariant | RegexOptions.Compiled);
    private static readonly Regex HashPattern = new(
        "^[0-9a-f]{64}$",
        RegexOptions.CultureInvariant | RegexOptions.Compiled);
    private static readonly Regex HandlePattern = new(
        "^[0-9A-Fa-f]{1,64}$",
        RegexOptions.CultureInvariant | RegexOptions.Compiled);
    private static readonly IReadOnlySet<string> RequiredControls = new HashSet<string>(
        new[] { "axle", "cabin", "chassis", "track", "wheelbase" },
        StringComparer.Ordinal);

    private static readonly IReadOnlySet<string> InspectionParameterFields = new HashSet<string>(
        new[] { "run_id", "source_full_path", "source_revision", "inspection_expectations", "target_role" },
        StringComparer.Ordinal);
    private static readonly IReadOnlySet<string> ExpectationFields = new HashSet<string>(
        new[] { "source", "identity", "critical_dimensions", "xref", "components" },
        StringComparer.Ordinal);
    private static readonly IReadOnlySet<string> SourceFields = new HashSet<string>(
        new[] { "source_id", "revision", "sha256" },
        StringComparer.Ordinal);
    private static readonly IReadOnlySet<string> IdentityFields = new HashSet<string>(
        new[] { "vehicle", "model" },
        StringComparer.Ordinal);
    private static readonly IReadOnlySet<string> DimensionFields = new HashSet<string>(
        new[] { "control", "target", "tolerance", "unit" },
        StringComparer.Ordinal);
    private static readonly IReadOnlySet<string> XrefFields = new HashSet<string>(
        new[] { "name" },
        StringComparer.Ordinal);
    private static readonly IReadOnlySet<string> ComponentFields = new HashSet<string>(
        new[] { "component_type", "logical_component_id", "provenance", "source_block", "source_handle", "source_layer" },
        StringComparer.Ordinal);
    private static readonly IReadOnlySet<string> ExtractionPlanFields = new HashSet<string>(
        new[]
        {
            "approval", "base_source", "components", "impacted_views", "inspection_id", "plan_id",
            "provenance", "request_id", "run_id", "schema_version", "source_revision",
            "target_drawing_sha256", "transform_policy"
        },
        StringComparer.Ordinal);
    private static readonly IReadOnlySet<string> ApprovalFields = new HashSet<string>(
        new[] { "reference", "status" },
        StringComparer.Ordinal);
    private static readonly IReadOnlySet<string> PlanSourceFields = new HashSet<string>(
        new[] { "relative_path", "revision", "sha256", "source_id" },
        StringComparer.Ordinal);
    private static readonly IReadOnlySet<string> PlanComponentFields = new HashSet<string>(
        ComponentFields.Concat(new[] { "bounding", "transform" }),
        StringComparer.Ordinal);
    private static readonly IReadOnlySet<string> BoundingFields = new HashSet<string>(
        new[] { "min", "max" },
        StringComparer.Ordinal);
    private static readonly IReadOnlySet<string> PointFields = new HashSet<string>(
        new[] { "x", "y", "z" },
        StringComparer.Ordinal);
    private static readonly IReadOnlySet<string> TransformFields = new HashSet<string>(
        new[] { "rotation_degrees", "translation", "uniform_scale" },
        StringComparer.Ordinal);
    private static readonly IReadOnlySet<string> ViewFields = new HashSet<string>(
        new[] { "identity", "name" },
        StringComparer.Ordinal);

    private readonly ExactBaseXrefServerConfiguration _configuration;

    public ExactBaseXrefPolicy(ExactBaseXrefServerConfiguration configuration)
    {
        _configuration = configuration ?? throw new ArgumentNullException(nameof(configuration));
        ConfigurationErrors = ValidateConfigurationShape(configuration).ToArray();
    }

    public IReadOnlyList<string> ConfigurationErrors { get; }

    public bool IsConfigured => ConfigurationErrors.Count == 0;

    public ExactBaseXrefServerConfiguration Configuration => _configuration;

    public static ExactBaseXrefPolicy FromEnvironment(
        Func<string, string?>? getEnvironmentVariable = null)
    {
        getEnvironmentVariable ??= Environment.GetEnvironmentVariable;
        return new ExactBaseXrefPolicy(new ExactBaseXrefServerConfiguration(
            getEnvironmentVariable(DisposableRootEnvironmentVariable),
            getEnvironmentVariable(AcceptedDwgPathEnvironmentVariable),
            getEnvironmentVariable(AcceptedDwgSha256EnvironmentVariable),
            getEnvironmentVariable(ExactBaseSourcePathEnvironmentVariable),
            getEnvironmentVariable(ExactBaseSourceSha256EnvironmentVariable),
            getEnvironmentVariable(ExactBaseSourceRevisionEnvironmentVariable)));
    }

    public ExactBaseXrefInspectionParameters ValidateInspectionRequest(IpcRequest request)
    {
        var parameters = ParseInspectionParameters(request, extraction: false);
        EnsureConfigured();
        EnsureSourceMatchesConfiguration(parameters.SourceFullPath, parameters.SourceRevision, parameters.InspectionExpectations!);
        EnsureTargetHash(request, allowAcceptedTarget: true);
        return parameters;
    }

    public ExactBaseXrefExtractionParameters ValidateExtractionRequest(IpcRequest request)
    {
        var parameters = ParseExtractionParameters(request);
        EnsureConfigured();
        EnsureSourceMatchesConfiguration(parameters.SourceFullPath, parameters.SourceRevision, parameters.InspectionExpectations!);
        EnsureTargetHash(request, allowAcceptedTarget: false);
        EnsureCandidatePaths(request, parameters);
        return parameters;
    }

    public void ValidateLiveInspection(
        ExactBaseXrefLiveInspection evidence,
        ExactBaseXrefInspectionParameters request,
        string targetDrawingSha256)
    {
        ArgumentNullException.ThrowIfNull(evidence);
        ArgumentNullException.ThrowIfNull(request);
        if (evidence.SchemaVersion != "exact-base-xref-inspection-1.0"
            || evidence.Changed
            || !evidence.Eligible
            || evidence.DbmodBefore < 0
            || evidence.DbmodAfter < 0
            || evidence.DbmodBefore != evidence.DbmodAfter
            || evidence.CaptureTimestamp == default
            || evidence.CaptureTimestamp.Offset != TimeSpan.Zero)
        {
            throw InvalidRequest("live inspection must be read-only, eligible, DBMOD-stable, and timestamped in UTC");
        }
        if (evidence.RunId != request.RunId
            || evidence.RequestId is null
            || evidence.TargetDrawingSha256 != targetDrawingSha256
            || !HashPattern.IsMatch(evidence.TargetDrawingSha256))
        {
            throw new ExactBaseXrefPolicyException(
                SourceIdentityMismatchCode,
                "live inspection identity or target hash does not match the request");
        }
        if (evidence.BaseSource is null
            || evidence.BaseSource.SourceId != request.InspectionExpectations!.Source!.SourceId
            || evidence.BaseSource.Revision != _configuration.ExactBaseSourceRevision
            || evidence.BaseSource.Sha256 != _configuration.ExactBaseSourceSha256)
        {
            throw new ExactBaseXrefPolicyException(
                SourceHashMismatchCode,
                "live inspection source evidence does not match the server-owned source");
        }

        var expectedIdentity = new Dictionary<string, string>(StringComparer.Ordinal)
        {
            ["vehicle"] = request.InspectionExpectations.Identity!.Vehicle!,
            ["model"] = request.InspectionExpectations.Identity.Model!
        };
        var identityObservations = evidence.IdentityObservations ?? throw InvalidRequest("live identity observations are required");
        if (identityObservations.Count != expectedIdentity.Count
            || identityObservations.Select(observation => observation.Field).Distinct(StringComparer.Ordinal).Count()
                != identityObservations.Count)
        {
            throw new ExactBaseXrefPolicyException(
                SourceIdentityMismatchCode,
                "live identity observations must contain vehicle and model exactly once");
        }
        foreach (var observation in identityObservations)
        {
            if (observation.Field is null
                || !expectedIdentity.TryGetValue(observation.Field, out var expected)
                || observation.Observed != expected
                || observation.Target != expected
                || observation.Status != "PASS")
            {
                throw new ExactBaseXrefPolicyException(
                    SourceIdentityMismatchCode,
                    "live vehicle/model identity did not PASS exactly");
            }
        }

        var expectedDimensions = request.InspectionExpectations.CriticalDimensions!
            .ToDictionary(dimension => dimension.Control!, StringComparer.Ordinal);
        var dimensions = evidence.CriticalDimensions ?? throw InvalidRequest("live critical dimensions are required");
        if (dimensions.Count != expectedDimensions.Count
            || dimensions.Select(dimension => dimension.Control).Distinct(StringComparer.Ordinal).Count() != dimensions.Count)
        {
            throw InvalidRequest("live critical dimensions must contain every required control exactly once");
        }
        foreach (var dimension in dimensions)
        {
            if (dimension.Control is null
                || !expectedDimensions.TryGetValue(dimension.Control, out var expected)
                || dimension.Status != "PASS"
                || dimension.Unit != expected.Unit
                || dimension.Target != expected.Target
                || dimension.Tolerance != expected.Tolerance
                || Math.Abs(dimension.Observed - expected.Target) > expected.Tolerance)
            {
                throw InvalidRequest("a live critical dimension did not PASS its approved tolerance");
            }
        }

        if (evidence.Xref is null
            || evidence.Xref.Name != request.InspectionExpectations.Xref!.Name
            || !evidence.Xref.ReadOnly
            || evidence.Xref.Status != "INSPECTED")
        {
            throw new ExactBaseXrefPolicyException(
                SourceIdentityMismatchCode,
                "the exact-base Xref must be inspected and read-only");
        }

        var components = evidence.Components ?? throw InvalidRequest("live Xref components are required");
        var seenIds = new HashSet<string>(StringComparer.Ordinal);
        var seenHandles = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var component in components)
        {
            if (component.LogicalComponentId is null
                || !seenIds.Add(component.LogicalComponentId)
                || component.SourceHandle is null
                || !seenHandles.Add(component.SourceHandle)
                || component.Bounding is null
                || !IsValidBounding(component.Bounding))
            {
                throw InvalidRequest("live Xref components must have unique bounded BLOCK evidence");
            }
            var expected = request.InspectionExpectations.Components!
                .SingleOrDefault(item => item.LogicalComponentId == component.LogicalComponentId);
            if (expected is null
                || component.ComponentType != expected.ComponentType
                || component.Provenance != expected.Provenance
                || component.SourceBlock != expected.SourceBlock
                || component.SourceHandle != expected.SourceHandle
                || component.SourceLayer != expected.SourceLayer)
            {
                throw new ExactBaseXrefPolicyException(
                    SourceIdentityMismatchCode,
                    "live Xref component provenance does not match inspection expectations");
            }
        }
        if (evidence.Conflicts is null || evidence.Conflicts.Count != 0
            || evidence.Warnings is null || evidence.Warnings.Any(string.IsNullOrWhiteSpace))
        {
            throw InvalidRequest("live inspection conflicts and warnings must be closed");
        }
    }

    public void RequireFreshLivePreflight(string? runId)
    {
        throw new ExactBaseXrefPolicyException(
            LivePreflightRequiredCode,
            "the AutoCAD-owned full live preflight is not available at the Task 3 boundary; run_id is informational only");
    }

    public static void ValidateRequestShape(IpcRequest request, ICollection<string> errors)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentNullException.ThrowIfNull(errors);
        if (request.Operation is not ExactBaseXrefOperationNames.Inspection
            and not ExactBaseXrefOperationNames.Extraction)
        {
            return;
        }

        try
        {
            if (request.Operation == ExactBaseXrefOperationNames.Inspection)
            {
                ParseInspectionParameters(request, extraction: false);
            }
            else
            {
                ParseExtractionParameters(request);
            }
        }
        catch (ExactBaseXrefPolicyException exception)
        {
            errors.Add($"{exception.Code}: {exception.Message}");
        }
    }

    private static ExactBaseXrefInspectionParameters ParseInspectionParameters(
        IpcRequest request,
        bool extraction)
    {
        var expectedOperation = extraction
            ? ExactBaseXrefOperationNames.Extraction
            : ExactBaseXrefOperationNames.Inspection;
        if (request.Operation != expectedOperation)
        {
            throw InvalidRequest($"operation must be {expectedOperation}");
        }

        var parameters = request.Parameters
            ?? throw InvalidRequest("parameters must be an object");
        var parameterObject = JsonSerializer.SerializeToElement(parameters, ContractJson.Options);
        var fields = extraction
            ? InspectionParameterFields.Concat(new[] { "extraction_plan", "candidate_output_path" }).ToHashSet(StringComparer.Ordinal)
            : InspectionParameterFields;
        RequireClosedObject(parameterObject, fields, "parameters");
        var baseParameters = new ExactBaseXrefInspectionParameters
        {
            RunId = RequiredIdentifier(parameters, "run_id"),
            SourceFullPath = RequiredAbsolutePath(parameters, "source_full_path"),
            SourceRevision = RequiredIdentifier(parameters, "source_revision"),
            InspectionExpectations = ParseInspectionExpectations(
                RequiredProperty(parameters, "inspection_expectations")),
            TargetRole = RequiredString(parameters, "target_role")
        };
        if (baseParameters.TargetRole != (extraction
                ? ExactBaseXrefOperationNames.ExtractionTargetRole
                : ExactBaseXrefOperationNames.InspectionTargetRole))
        {
            throw InvalidRequest("target_role is not valid for this operation");
        }

        if (request.Approval.HasValue && request.Approval.Value.ValueKind != JsonValueKind.Null)
        {
            if (!extraction)
            {
                throw InvalidRequest("inspection approval must be null");
            }
        }
        else if (extraction)
        {
            throw new ExactBaseXrefPolicyException(
                ApprovalRequiredCode,
                "extraction approval is required");
        }

        if (!extraction)
        {
            return baseParameters;
        }

        var extractionParameters = new ExactBaseXrefExtractionParameters
        {
            RunId = baseParameters.RunId,
            SourceFullPath = baseParameters.SourceFullPath,
            SourceRevision = baseParameters.SourceRevision,
            InspectionExpectations = baseParameters.InspectionExpectations,
            TargetRole = baseParameters.TargetRole,
            ExtractionPlan = ParseExtractionPlan(RequiredProperty(parameters, "extraction_plan")),
            CandidateOutputPath = RequiredAbsolutePath(parameters, "candidate_output_path")
        };
        ValidateExtractionApproval(request.Approval!.Value, parameters["extraction_plan"]);
        ValidatePlanAgainstRequest(extractionParameters, request);
        return extractionParameters;
    }

    private static ExactBaseXrefExtractionParameters ParseExtractionParameters(IpcRequest request) =>
        (ExactBaseXrefExtractionParameters)ParseInspectionParameters(request, extraction: true);

    private static ExactBaseXrefInspectionExpectations ParseInspectionExpectations(JsonElement value)
    {
        var objectValue = RequireClosedObject(value, ExpectationFields, "inspection_expectations");
        var source = RequireClosedObject(RequiredProperty(objectValue, "source"), SourceFields, "inspection_expectations.source");
        var identity = RequireClosedObject(RequiredProperty(objectValue, "identity"), IdentityFields, "inspection_expectations.identity");
        var xref = RequireClosedObject(RequiredProperty(objectValue, "xref"), XrefFields, "inspection_expectations.xref");
        var dimensions = RequireArray(RequiredProperty(objectValue, "critical_dimensions"), "inspection_expectations.critical_dimensions");
        if (dimensions.Count != 5)
        {
            throw InvalidRequest("inspection_expectations.critical_dimensions must contain exactly five controls");
        }

        var parsedDimensions = dimensions
            .Select((item, index) => ParseDimension(item, $"inspection_expectations.critical_dimensions[{index}]") )
            .ToList();
        if (parsedDimensions.Select(item => item.Control).Distinct(StringComparer.Ordinal).Count() != parsedDimensions.Count
            || !parsedDimensions.Select(item => item.Control).ToHashSet(StringComparer.Ordinal).SetEquals(RequiredControls))
        {
            throw InvalidRequest("inspection_expectations.critical_dimensions must contain each required control once");
        }

        var components = RequireArray(RequiredProperty(objectValue, "components"), "inspection_expectations.components");
        if (components.Count == 0)
        {
            throw InvalidRequest("inspection_expectations.components must not be empty");
        }
        var parsedComponents = components
            .Select((item, index) => ParseComponent(item, $"inspection_expectations.components[{index}]") )
            .ToList();
        EnsureUniqueComponents(parsedComponents, "inspection_expectations.components");

        var result = new ExactBaseXrefInspectionExpectations
        {
            Source = new ExactBaseXrefSourceExpectation
            {
                SourceId = RequiredIdentifier(RequiredProperty(source, "source_id"), "source_id"),
                Revision = RequiredIdentifier(RequiredProperty(source, "revision"), "revision"),
                Sha256 = RequiredHash(RequiredProperty(source, "sha256"), "sha256")
            },
            Identity = new ExactBaseXrefIdentityExpectation
            {
                Vehicle = RequiredIdentifier(RequiredProperty(identity, "vehicle"), "vehicle"),
                Model = RequiredIdentifier(RequiredProperty(identity, "model"), "model")
            },
            CriticalDimensions = parsedDimensions,
            Xref = new ExactBaseXrefReference
            {
                Name = RequiredIdentifier(RequiredProperty(xref, "name"), "name")
            },
            Components = parsedComponents
        };
        return result;
    }

    private static ExactBaseXrefDimensionExpectation ParseDimension(JsonElement value, string name)
    {
        var item = RequireClosedObject(value, DimensionFields, name);
        var target = RequiredFiniteNumber(RequiredProperty(item, "target"), "target");
        var tolerance = RequiredFiniteNumber(RequiredProperty(item, "tolerance"), "tolerance");
        var unit = RequiredString(RequiredProperty(item, "unit"), "unit");
        if (tolerance < 0 || unit is not ("in" or "mm"))
        {
            throw InvalidRequest($"{name} has an invalid tolerance or unit");
        }

        return new ExactBaseXrefDimensionExpectation
        {
            Control = RequiredIdentifier(RequiredProperty(item, "control"), "control"),
            Target = target,
            Tolerance = tolerance,
            Unit = unit
        };
    }

    private static ExactBaseXrefComponentExpectation ParseComponent(JsonElement value, string name)
    {
        var item = RequireClosedObject(value, ComponentFields, name);
        var componentType = RequiredString(RequiredProperty(item, "component_type"), "component_type");
        var provenance = RequiredString(RequiredProperty(item, "provenance"), "provenance");
        if (componentType != "BLOCK" || provenance != ExactBaseXrefOperationNames.ReusedFromBaseCad)
        {
            throw InvalidRequest($"{name} must be a reused BLOCK component");
        }

        return new ExactBaseXrefComponentExpectation
        {
            ComponentType = componentType,
            LogicalComponentId = RequiredIdentifier(RequiredProperty(item, "logical_component_id"), "logical_component_id"),
            Provenance = provenance,
            SourceBlock = RequiredIdentifier(RequiredProperty(item, "source_block"), "source_block"),
            SourceHandle = RequiredHandle(RequiredProperty(item, "source_handle"), "source_handle"),
            SourceLayer = RequiredNonEmptyString(RequiredProperty(item, "source_layer"), "source_layer")
        };
    }

    private static ExactBaseXrefExtractionPlan ParseExtractionPlan(JsonElement value)
    {
        var item = RequireClosedObject(value, ExtractionPlanFields, "extraction_plan");
        var approval = ParseApproval(RequiredProperty(item, "approval"), "extraction_plan.approval");
        var baseSource = RequireClosedObject(RequiredProperty(item, "base_source"), PlanSourceFields, "extraction_plan.base_source");
        var components = RequireArray(RequiredProperty(item, "components"), "extraction_plan.components");
        if (components.Count == 0)
        {
            throw InvalidRequest("extraction_plan.components must not be empty");
        }
        var parsedComponents = components
            .Select((component, index) => ParsePlanComponent(component, $"extraction_plan.components[{index}]") )
            .ToList();
        EnsureUniqueComponents(parsedComponents, "extraction_plan.components");

        var views = RequireArray(RequiredProperty(item, "impacted_views"), "extraction_plan.impacted_views");
        if (views.Count == 0)
        {
            throw InvalidRequest("extraction_plan.impacted_views must not be empty");
        }
        var parsedViews = views.Select((view, index) =>
        {
            var viewObject = RequireClosedObject(view, ViewFields, $"extraction_plan.impacted_views[{index}]");
            return new ExactBaseXrefView
            {
                Identity = RequiredIdentifier(RequiredProperty(viewObject, "identity"), "identity"),
                Name = RequiredNonEmptyString(RequiredProperty(viewObject, "name"), "name")
            };
        }).ToList();
        if (parsedViews.Select(view => view.Identity).Distinct(StringComparer.Ordinal).Count() != parsedViews.Count)
        {
            throw InvalidRequest("extraction_plan.impacted_views contains duplicate identities");
        }

        var result = new ExactBaseXrefExtractionPlan
        {
            Approval = approval,
            BaseSource = new ExactBaseXrefPlanSource
            {
                RelativePath = RequiredSafeRelativePath(RequiredProperty(baseSource, "relative_path"), "relative_path"),
                Revision = RequiredIdentifier(RequiredProperty(baseSource, "revision"), "revision"),
                Sha256 = RequiredHash(RequiredProperty(baseSource, "sha256"), "sha256"),
                SourceId = RequiredIdentifier(RequiredProperty(baseSource, "source_id"), "source_id")
            },
            Components = parsedComponents,
            ImpactedViews = parsedViews,
            InspectionId = RequiredIdentifier(RequiredProperty(item, "inspection_id"), "inspection_id"),
            PlanId = RequiredIdentifier(RequiredProperty(item, "plan_id"), "plan_id"),
            Provenance = RequiredString(RequiredProperty(item, "provenance"), "provenance"),
            RequestId = RequiredIdentifier(RequiredProperty(item, "request_id"), "request_id"),
            RunId = RequiredIdentifier(RequiredProperty(item, "run_id"), "run_id"),
            SchemaVersion = RequiredString(RequiredProperty(item, "schema_version"), "schema_version"),
            SourceRevision = RequiredIdentifier(RequiredProperty(item, "source_revision"), "source_revision"),
            TargetDrawingSha256 = RequiredHash(RequiredProperty(item, "target_drawing_sha256"), "target_drawing_sha256"),
            TransformPolicy = RequiredString(RequiredProperty(item, "transform_policy"), "transform_policy")
        };
        if (result.Provenance != ExactBaseXrefOperationNames.ReusedFromBaseCad
            || result.SchemaVersion != "exact-base-xref-extraction-plan-1.0"
            || result.TransformPolicy != ExactBaseXrefOperationNames.TransformPolicy
            || result.SourceRevision != result.BaseSource.Revision)
        {
            throw InvalidRequest("extraction_plan contains unsupported provenance, schema, revision, or transform policy");
        }
        return result;
    }

    private static ExactBaseXrefPlanComponent ParsePlanComponent(JsonElement value, string name)
    {
        var item = RequireClosedObject(value, PlanComponentFields, name);
        var componentFields = ComponentFields.ToDictionary(
            field => field,
            field => RequiredProperty(item, field),
            StringComparer.Ordinal);
        var component = ParseComponent(
            JsonSerializer.SerializeToElement(componentFields, ContractJson.Options),
            name);
        var bounding = RequireClosedObject(RequiredProperty(item, "bounding"), BoundingFields, $"{name}.bounding");
        var min = ParsePoint(RequiredProperty(bounding, "min"), $"{name}.bounding.min");
        var max = ParsePoint(RequiredProperty(bounding, "max"), $"{name}.bounding.max");
        if (min.X > max.X || min.Y > max.Y || min.Z > max.Z)
        {
            throw InvalidRequest($"{name}.bounding min must not exceed max");
        }

        var transform = RequireClosedObject(RequiredProperty(item, "transform"), TransformFields, $"{name}.transform");
        var rotation = RequiredFiniteNumber(RequiredProperty(transform, "rotation_degrees"), "rotation_degrees");
        var scale = RequiredFiniteNumber(RequiredProperty(transform, "uniform_scale"), "uniform_scale");
        if (rotation is < -360 or > 360 || scale <= 0 || scale > 100)
        {
            throw new ExactBaseXrefPolicyException(
                TransformPolicyCode,
                $"{name} must use local translation, rotation, and positive uniform scale only");
        }

        return new ExactBaseXrefPlanComponent
        {
            ComponentType = component.ComponentType,
            LogicalComponentId = component.LogicalComponentId,
            Provenance = component.Provenance,
            SourceBlock = component.SourceBlock,
            SourceHandle = component.SourceHandle,
            SourceLayer = component.SourceLayer,
            Bounding = new ExactBaseXrefBounding { Min = min, Max = max },
            Transform = new ExactBaseXrefTransform
            {
                RotationDegrees = rotation,
                Translation = ParsePoint(RequiredProperty(transform, "translation"), $"{name}.transform.translation"),
                UniformScale = scale
            }
        };
    }

    private static ExactBaseXrefPoint ParsePoint(JsonElement value, string name)
    {
        var item = RequireClosedObject(value, PointFields, name);
        return new ExactBaseXrefPoint
        {
            X = RequiredFiniteNumber(RequiredProperty(item, "x"), "x"),
            Y = RequiredFiniteNumber(RequiredProperty(item, "y"), "y"),
            Z = RequiredFiniteNumber(RequiredProperty(item, "z"), "z")
        };
    }

    private static ExactBaseXrefApproval ParseApproval(JsonElement value, string name)
    {
        var item = RequireClosedObject(value, ApprovalFields, name);
        var status = RequiredString(RequiredProperty(item, "status"), "status");
        var reference = RequiredIdentifier(RequiredProperty(item, "reference"), "reference");
        if (status != "APPROVED")
        {
            throw new ExactBaseXrefPolicyException(
                ApprovalRequiredCode,
                $"{name}.status must be APPROVED");
        }

        return new ExactBaseXrefApproval { Reference = reference, Status = status };
    }

    private static void ValidateExtractionApproval(JsonElement envelope, JsonElement plan)
    {
        var envelopeApproval = ParseApproval(envelope, "approval");
        var planObject = RequireObject(plan, "extraction_plan");
        var planApproval = ParseApproval(RequiredProperty(planObject, "approval"), "extraction_plan.approval");
        if (!string.Equals(envelopeApproval.Reference, planApproval.Reference, StringComparison.Ordinal)
            || !string.Equals(envelopeApproval.Status, planApproval.Status, StringComparison.Ordinal)
            || !string.Equals(CanonicalJson(envelope), CanonicalJson(RequiredProperty(planObject, "approval")), StringComparison.Ordinal))
        {
            throw new ExactBaseXrefPolicyException(
                ApprovalMismatchCode,
                "extraction_plan.approval must match the approval envelope canonically");
        }
    }

    private static void ValidatePlanAgainstRequest(
        ExactBaseXrefExtractionParameters parameters,
        IpcRequest request)
    {
        var plan = parameters.ExtractionPlan!;
        if (plan.RunId != parameters.RunId
            || plan.SourceRevision != parameters.SourceRevision
            || plan.TargetDrawingSha256 != request.DrawingSha256)
        {
            throw InvalidRequest("extraction_plan is stale or does not match the request identity");
        }

        var expectation = parameters.InspectionExpectations!;
        if (plan.BaseSource!.SourceId != expectation.Source!.SourceId
            || plan.BaseSource.Revision != expectation.Source.Revision
            || plan.BaseSource.Sha256 != expectation.Source.Sha256)
        {
            throw new ExactBaseXrefPolicyException(
                SourceIdentityMismatchCode,
                "extraction_plan.base_source must match inspection_expectations.source");
        }

        var inspected = expectation.Components!.ToDictionary(
            component => component.LogicalComponentId!,
            StringComparer.Ordinal);
        foreach (var component in plan.Components!)
        {
            if (!inspected.TryGetValue(component.LogicalComponentId!, out var expected)
                || component.ComponentType != expected.ComponentType
                || component.Provenance != expected.Provenance
                || component.SourceBlock != expected.SourceBlock
                || component.SourceHandle != expected.SourceHandle
                || component.SourceLayer != expected.SourceLayer)
            {
                throw new ExactBaseXrefPolicyException(
                    SourceIdentityMismatchCode,
                    "extraction_plan component is not an exact inspected source component");
            }
        }
    }

    private void EnsureSourceMatchesConfiguration(
        string? sourcePath,
        string? sourceRevision,
        ExactBaseXrefInspectionExpectations expectations)
    {
        var configuredSource = EnsureExistingCanonicalFile(
            _configuration.ExactBaseSourcePath,
            SourceIdentityMismatchCode,
            "configured exact-base source");
        var requestedSource = EnsureExistingCanonicalFile(sourcePath, SourceIdentityMismatchCode, "request source");
        if (!SameFile(configuredSource, requestedSource))
        {
            throw new ExactBaseXrefPolicyException(
                SourceIdentityMismatchCode,
                "source_full_path is not the server-configured exact-base source file");
        }
        if (!string.Equals(sourceRevision, _configuration.ExactBaseSourceRevision, StringComparison.Ordinal)
            || !string.Equals(expectations.Source!.Revision, _configuration.ExactBaseSourceRevision, StringComparison.Ordinal))
        {
            throw new ExactBaseXrefPolicyException(
                SourceRevisionMismatchCode,
                "source revision does not match the server-configured source revision");
        }
        if (!string.Equals(expectations.Source.Sha256, _configuration.ExactBaseSourceSha256, StringComparison.Ordinal))
        {
            throw new ExactBaseXrefPolicyException(
                SourceHashMismatchCode,
                "source hash does not match the server-configured source hash");
        }

        var accepted = EnsureExistingCanonicalFile(
            _configuration.AcceptedDwgPath,
            AcceptedAliasCode,
            "configured accepted DWG");
        if (SameFile(configuredSource, accepted))
        {
            throw new ExactBaseXrefPolicyException(
                SourceAliasCode,
                "configured source and accepted DWG resolve to the same file identity");
        }
    }

    private void EnsureTargetHash(IpcRequest request, bool allowAcceptedTarget)
    {
        if (request.DrawingSha256 is null || !HashPattern.IsMatch(request.DrawingSha256))
        {
            throw new ExactBaseXrefPolicyException(
                RequestInvalidCode,
                "drawing_sha256 must be a lowercase SHA-256");
        }

        var accepted = EnsureExistingCanonicalFile(
            _configuration.AcceptedDwgPath,
            AcceptedAliasCode,
            "configured accepted DWG");
        var target = EnsureExistingCanonicalFile(
            request.DrawingFullPath,
            ActiveDocumentMismatchCode,
            "active drawing");
        if (SameFile(target, accepted))
        {
            if (!allowAcceptedTarget)
            {
                throw new ExactBaseXrefPolicyException(
                    AcceptedAliasCode,
                    "extraction cannot mutate or target the accepted DWG");
            }
            if (!string.Equals(request.DrawingSha256, _configuration.AcceptedDwgSha256, StringComparison.Ordinal))
            {
                throw new ExactBaseXrefPolicyException(
                    SourceHashMismatchCode,
                    "accepted DWG hash does not match the server-configured accepted hash");
            }
        }
    }

    private void EnsureCandidatePaths(
        IpcRequest request,
        ExactBaseXrefExtractionParameters parameters)
    {
        var root = EnsureExistingCanonicalDirectory(_configuration.DisposableRoot);
        var source = EnsureExistingCanonicalFile(_configuration.ExactBaseSourcePath, SourceAliasCode, "source");
        var accepted = EnsureExistingCanonicalFile(_configuration.AcceptedDwgPath, AcceptedAliasCode, "accepted DWG");
        var input = EnsureExistingCanonicalFile(request.DrawingFullPath, CandidatePathUnsafeCode, "candidate input");
        if (!IsUnderRoot(root, input))
        {
            throw new ExactBaseXrefPolicyException(
                CandidatePathUnsafeCode,
                "candidate input must be contained by the disposable root");
        }
        if (SameFile(input, source))
        {
            throw new ExactBaseXrefPolicyException(
                SourceAliasCode,
                "candidate input aliases the exact-base source");
        }
        if (SameFile(input, accepted))
        {
            throw new ExactBaseXrefPolicyException(
                AcceptedAliasCode,
                "candidate input aliases the accepted DWG");
        }

        var output = CanonicalizeNonExistingPath(parameters.CandidateOutputPath);
        if (!IsUnderRoot(root, output))
        {
            throw new ExactBaseXrefPolicyException(
                CandidatePathUnsafeCode,
                "candidate output must be contained by the disposable root");
        }
        if (SamePath(output, input))
        {
            throw new ExactBaseXrefPolicyException(
                CandidatePathUnsafeCode,
                "candidate input and output must be distinct files");
        }
        if (File.Exists(output) || Directory.Exists(output))
        {
            throw new ExactBaseXrefPolicyException(
                CandidateOutputExistsCode,
                "candidate output must not already exist");
        }
        if (SamePath(output, source))
        {
            throw new ExactBaseXrefPolicyException(SourceAliasCode, "candidate output aliases the source");
        }
        if (SamePath(output, accepted))
        {
            throw new ExactBaseXrefPolicyException(AcceptedAliasCode, "candidate output aliases the accepted DWG");
        }
    }

    private void EnsureConfigured()
    {
        if (!IsConfigured)
        {
            throw new ExactBaseXrefPolicyException(
                ConfigurationRequiredCode,
                string.Join(", ", ConfigurationErrors));
        }
    }

    private static IReadOnlyList<string> ValidateConfigurationShape(ExactBaseXrefServerConfiguration configuration)
    {
        var errors = new List<string>();
        if (string.IsNullOrWhiteSpace(configuration.DisposableRoot)) errors.Add("disposable root is missing");
        if (string.IsNullOrWhiteSpace(configuration.AcceptedDwgPath)) errors.Add("accepted DWG path is missing");
        if (string.IsNullOrWhiteSpace(configuration.ExactBaseSourcePath)) errors.Add("exact-base source path is missing");
        if (configuration.DisposableRoot is not null
            && !ContractValidator.TryNormalizeWindowsAbsolutePath(configuration.DisposableRoot, out _)) errors.Add("disposable root path is invalid");
        if (configuration.AcceptedDwgPath is not null
            && !ContractValidator.TryNormalizeWindowsAbsolutePath(configuration.AcceptedDwgPath, out _)) errors.Add("accepted DWG path is invalid");
        if (configuration.ExactBaseSourcePath is not null
            && !ContractValidator.TryNormalizeWindowsAbsolutePath(configuration.ExactBaseSourcePath, out _)) errors.Add("exact-base source path is invalid");
        if (configuration.AcceptedDwgSha256 is null || !HashPattern.IsMatch(configuration.AcceptedDwgSha256)) errors.Add("accepted DWG hash is invalid");
        if (configuration.ExactBaseSourceSha256 is null || !HashPattern.IsMatch(configuration.ExactBaseSourceSha256)) errors.Add("exact-base source hash is invalid");
        if (configuration.ExactBaseSourceRevision is null || !IdentifierPattern.IsMatch(configuration.ExactBaseSourceRevision)) errors.Add("exact-base source revision is invalid");
        return errors;
    }

    private static string EnsureExistingCanonicalDirectory(string? path)
    {
        var canonical = CanonicalizePath(path, ConfigurationRequiredCode, "disposable root");
        if (!Directory.Exists(canonical))
        {
            throw new ExactBaseXrefPolicyException(ConfigurationRequiredCode, "disposable root does not exist");
        }
        EnsureNoReparsePoints(canonical, ReparsePointCode);
        return CanonicalizeExistingHandlePath(canonical, ConfigurationRequiredCode, "disposable root");
    }

    private static string EnsureExistingCanonicalFile(string? path, string code, string name)
    {
        var canonical = CanonicalizePath(path, code, name);
        if (!File.Exists(canonical))
        {
            throw new ExactBaseXrefPolicyException(code, $"{name} does not exist as a regular file");
        }
        EnsureNoReparsePoints(canonical, ReparsePointCode);
        return CanonicalizeExistingHandlePath(canonical, code, name);
    }

    private static string CanonicalizeNonExistingPath(string? path)
    {
        var canonical = CanonicalizePath(path, CandidatePathUnsafeCode, "candidate output");
        var parent = Path.GetDirectoryName(canonical);
        if (string.IsNullOrWhiteSpace(parent) || !Directory.Exists(parent))
        {
            throw new ExactBaseXrefPolicyException(
                CandidatePathUnsafeCode,
                "candidate output parent directory must exist");
        }
        EnsureNoReparsePoints(parent, ReparsePointCode);
        var finalParent = CanonicalizeExistingHandlePath(parent, CandidatePathUnsafeCode, "candidate output parent");
        return Path.Combine(finalParent, Path.GetFileName(canonical));
    }

    private static string CanonicalizeExistingHandlePath(string path, string code, string name)
    {
        if (!OperatingSystem.IsWindows())
        {
            return path;
        }

        try
        {
            using var handle = File.OpenHandle(
                path,
                FileMode.Open,
                FileAccess.Read,
                FileShare.ReadWrite | FileShare.Delete,
                (FileOptions)0x02000000);
            if (handle.IsInvalid)
            {
                throw new ExactBaseXrefPolicyException(code, $"{name} could not be opened for final-path canonicalization");
            }

            var capacity = 512;
            while (capacity <= 32768)
            {
                var buffer = new StringBuilder(capacity);
                var length = GetFinalPathNameByHandle(handle, buffer, (uint)buffer.Capacity, 0);
                if (length == 0)
                {
                    throw new ExactBaseXrefPolicyException(code, $"{name} final path could not be resolved");
                }
                if (length < buffer.Capacity - 1)
                {
                    var finalPath = NormalizeFinalPathPrefix(buffer.ToString());
                    return ContractValidator.NormalizeWindowsAbsolutePath(finalPath);
                }
                capacity *= 2;
            }
        }
        catch (ExactBaseXrefPolicyException)
        {
            throw;
        }
        catch (IOException exception)
        {
            throw new ExactBaseXrefPolicyException(code, $"{name} final path could not be resolved: {exception.Message}");
        }
        catch (UnauthorizedAccessException exception)
        {
            throw new ExactBaseXrefPolicyException(code, $"{name} final path could not be resolved: {exception.Message}");
        }

        throw new ExactBaseXrefPolicyException(code, $"{name} final path exceeds the supported length");
    }

    private static string NormalizeFinalPathPrefix(string path) =>
        path.StartsWith(@"\\?\UNC\", StringComparison.OrdinalIgnoreCase)
            ? @"\" + path[7..]
            : path.StartsWith(@"\\?\", StringComparison.Ordinal)
                ? path[4..]
                : path;

    private static string CanonicalizePath(string? path, string code, string name)
    {
        if (!ContractValidator.TryNormalizeWindowsAbsolutePath(path, out var normalized))
        {
            throw new ExactBaseXrefPolicyException(code, $"{name} must be a full absolute Windows path");
        }
        try
        {
            return Path.GetFullPath(normalized).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        }
        catch (Exception exception) when (exception is ArgumentException or NotSupportedException)
        {
            throw new ExactBaseXrefPolicyException(code, $"{name} could not be canonicalized");
        }
    }

    private static bool IsUnderRoot(string root, string candidate)
    {
        var relative = Path.GetRelativePath(root, candidate);
        return !Path.IsPathRooted(relative)
            && relative is not "."
            && !relative.Equals("..", StringComparison.Ordinal)
            && !relative.StartsWith(".." + Path.DirectorySeparatorChar, StringComparison.Ordinal)
            && !relative.StartsWith(".." + Path.AltDirectorySeparatorChar, StringComparison.Ordinal);
    }

    private static bool SamePath(string left, string right) =>
        StringComparer.OrdinalIgnoreCase.Equals(left, right);

    private static bool SameFile(string left, string right)
    {
        if (SamePath(left, right))
        {
            return true;
        }

        return TryGetFileIdentity(left, out var leftIdentity)
            && TryGetFileIdentity(right, out var rightIdentity)
            && leftIdentity == rightIdentity;
    }

    private static void EnsureNoReparsePoints(string path, string code)
    {
        var root = Path.GetPathRoot(path);
        if (string.IsNullOrWhiteSpace(root))
        {
            throw new ExactBaseXrefPolicyException(code, "path root is unavailable");
        }

        var current = root.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        var remainder = path[root.Length..];
        foreach (var segment in remainder.Split(
                     new[] { Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar },
                     StringSplitOptions.RemoveEmptyEntries))
        {
            current = Path.Combine(current, segment);
            if (!File.Exists(current) && !Directory.Exists(current))
            {
                break;
            }
            try
            {
                if ((File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0)
                {
                    throw new ExactBaseXrefPolicyException(code, $"reparse point is not allowed: {current}");
                }
            }
            catch (FileNotFoundException)
            {
                throw new ExactBaseXrefPolicyException(code, $"path disappeared during canonicalization: {current}");
            }
        }
    }

    private static bool TryGetFileIdentity(string path, out FileIdentity identity)
    {
        identity = default;
        if (!OperatingSystem.IsWindows())
        {
            return false;
        }

        try
        {
            using var handle = File.OpenHandle(
                path,
                FileMode.Open,
                FileAccess.Read,
                FileShare.ReadWrite | FileShare.Delete);
            if (handle.IsInvalid || !GetFileInformationByHandle(handle, out var information))
            {
                return false;
            }
            identity = new FileIdentity(
                information.VolumeSerialNumber,
                information.FileIndexHigh,
                information.FileIndexLow);
            return true;
        }
        catch (IOException)
        {
            return false;
        }
        catch (UnauthorizedAccessException)
        {
            return false;
        }
    }

    private static JsonElement RequireObject(JsonElement? value, string name)
    {
        if (!value.HasValue || value.Value.ValueKind != JsonValueKind.Object)
        {
            throw InvalidRequest($"{name} must be an object");
        }
        return value.Value;
    }

    private static JsonElement RequireObject(IReadOnlyDictionary<string, JsonElement>? value, string name)
    {
        if (value is null)
        {
            throw InvalidRequest($"{name} must be an object");
        }
        return JsonSerializer.SerializeToElement(value, ContractJson.Options);
    }

    private static JsonElement RequireClosedObject(JsonElement value, IReadOnlySet<string> fields, string name)
    {
        if (value.ValueKind != JsonValueKind.Object)
        {
            throw InvalidRequest($"{name} must be an object");
        }
        var present = value.EnumerateObject().Select(property => property.Name).ToHashSet(StringComparer.Ordinal);
        var unknown = present.Except(fields, StringComparer.Ordinal).ToArray();
        if (unknown.Length > 0)
        {
            throw InvalidRequest($"{name} contains unsupported field '{unknown[0]}'");
        }
        var missing = fields.Except(present, StringComparer.Ordinal).ToArray();
        if (missing.Length > 0)
        {
            throw InvalidRequest($"{name} is missing field '{missing[0]}'");
        }
        return value;
    }

    private static JsonElement RequiredProperty(JsonElement value, string name)
    {
        if (!value.TryGetProperty(name, out var property))
        {
            throw InvalidRequest($"missing property '{name}'");
        }
        return property;
    }

    private static JsonElement RequiredProperty(IReadOnlyDictionary<string, JsonElement> value, string name)
    {
        if (!value.TryGetValue(name, out var property))
        {
            throw InvalidRequest($"missing property '{name}'");
        }
        return property;
    }

    private static List<JsonElement> RequireArray(JsonElement value, string name)
    {
        if (value.ValueKind != JsonValueKind.Array)
        {
            throw InvalidRequest($"{name} must be an array");
        }
        return value.EnumerateArray().ToList();
    }

    private static string RequiredString(IReadOnlyDictionary<string, JsonElement> value, string name) =>
        value.TryGetValue(name, out var property)
            ? RequiredString(property, name)
            : throw InvalidRequest($"missing property '{name}'");

    private static string RequiredString(JsonElement value, string name)
    {
        if (value.ValueKind != JsonValueKind.String || string.IsNullOrWhiteSpace(value.GetString()))
        {
            throw InvalidRequest($"{name} must be a non-empty string");
        }
        var result = value.GetString()!;
        if (result.Any(character => character < ' ' || character == '\u007f'))
        {
            throw InvalidRequest($"{name} contains a control character");
        }
        return result;
    }

    private static string RequiredNonEmptyString(JsonElement value, string name) =>
        RequiredString(value, name);

    private static string RequiredIdentifier(JsonElement value, string name)
    {
        var result = RequiredString(value, name);
        if (!IdentifierPattern.IsMatch(result))
        {
            throw InvalidRequest($"{name} is not a safe identifier");
        }
        return result;
    }

    private static string RequiredIdentifier(IReadOnlyDictionary<string, JsonElement> value, string name) =>
        RequiredIdentifier(RequiredProperty(value, name), name);

    private static string RequiredAbsolutePath(IReadOnlyDictionary<string, JsonElement> value, string name)
    {
        var result = RequiredString(value, name);
        if (!ContractValidator.TryNormalizeWindowsAbsolutePath(result, out _))
        {
            throw InvalidRequest($"{name} must be a full absolute Windows path");
        }
        return result;
    }

    private static string RequiredHash(JsonElement value, string name)
    {
        var result = RequiredString(value, name);
        if (!HashPattern.IsMatch(result))
        {
            throw new ExactBaseXrefPolicyException(SourceHashMismatchCode, $"{name} must be a lowercase SHA-256");
        }
        return result;
    }

    private static string RequiredHandle(JsonElement value, string name)
    {
        var result = RequiredString(value, name);
        if (!HandlePattern.IsMatch(result))
        {
            throw InvalidRequest($"{name} must be a hexadecimal source handle");
        }
        return result;
    }

    private static string RequiredSafeRelativePath(JsonElement value, string name)
    {
        var result = RequiredString(value, name);
        if (result.StartsWith('/') || result.StartsWith('\\') || result.Contains('\\')
            || result.Contains("//", StringComparison.Ordinal)
            || result.Contains(':', StringComparison.Ordinal)
            || result.Split('/').Any(part => part is "." or ".."))
        {
            throw InvalidRequest($"{name} must be a safe relative POSIX path");
        }
        return result;
    }

    private static double RequiredFiniteNumber(JsonElement value, string name)
    {
        if (value.ValueKind != JsonValueKind.Number || !value.TryGetDouble(out var result)
            || double.IsNaN(result) || double.IsInfinity(result))
        {
            throw InvalidRequest($"{name} must be a finite number");
        }
        return result;
    }

    private static double RequiredFiniteNumber(IReadOnlyDictionary<string, JsonElement> value, string name) =>
        RequiredFiniteNumber(RequiredProperty(value, name), name);

    private static void EnsureUniqueComponents(
        IReadOnlyList<ExactBaseXrefComponentExpectation> components,
        string name)
    {
        var ids = components.Select(component => component.LogicalComponentId).ToArray();
        var handles = components.Select(component => component.SourceHandle?.ToUpperInvariant()).ToArray();
        if (ids.Length != ids.Distinct(StringComparer.Ordinal).Count()
            || handles.Length != handles.Distinct(StringComparer.Ordinal).Count())
        {
            throw InvalidRequest($"{name} contains duplicate component identity");
        }
    }

    private static bool IsValidBounding(ExactBaseXrefBounding bounding) =>
        bounding.Min is not null
        && bounding.Max is not null
        && IsFinitePoint(bounding.Min)
        && IsFinitePoint(bounding.Max)
        && bounding.Min.X <= bounding.Max.X
        && bounding.Min.Y <= bounding.Max.Y
        && bounding.Min.Z <= bounding.Max.Z;

    private static bool IsFinitePoint(ExactBaseXrefPoint point) =>
        double.IsFinite(point.X) && double.IsFinite(point.Y) && double.IsFinite(point.Z);

    private static ExactBaseXrefPolicyException InvalidRequest(string message) =>
        new(RequestInvalidCode, message);

    private static string CanonicalJson(JsonElement value)
    {
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream))
        {
            WriteCanonical(value, writer);
        }
        return Encoding.UTF8.GetString(stream.ToArray());
    }

    private static void WriteCanonical(JsonElement value, Utf8JsonWriter writer)
    {
        switch (value.ValueKind)
        {
            case JsonValueKind.Object:
                writer.WriteStartObject();
                foreach (var property in value.EnumerateObject().OrderBy(property => property.Name, StringComparer.Ordinal))
                {
                    writer.WritePropertyName(property.Name);
                    WriteCanonical(property.Value, writer);
                }
                writer.WriteEndObject();
                break;
            case JsonValueKind.Array:
                writer.WriteStartArray();
                foreach (var item in value.EnumerateArray())
                {
                    WriteCanonical(item, writer);
                }
                writer.WriteEndArray();
                break;
            default:
                value.WriteTo(writer);
                break;
        }
    }

    private readonly record struct FileIdentity(uint VolumeSerialNumber, uint FileIndexHigh, uint FileIndexLow);

    [StructLayout(LayoutKind.Sequential)]
    private struct ByHandleFileInformation
    {
        public uint FileAttributes;
        public System.Runtime.InteropServices.ComTypes.FILETIME CreationTime;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastAccessTime;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastWriteTime;
        public uint VolumeSerialNumber;
        public uint FileSizeHigh;
        public uint FileSizeLow;
        public uint NumberOfLinks;
        public uint FileIndexHigh;
        public uint FileIndexLow;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetFileInformationByHandle(
        SafeFileHandle handle,
        out ByHandleFileInformation fileInformation);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern uint GetFinalPathNameByHandle(
        SafeFileHandle handle,
        StringBuilder filePath,
        uint filePathLength,
        uint flags);
}
