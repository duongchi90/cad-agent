using System.Text.Json;
using System.Security.Cryptography;
using System.Text;
using Autodesk.AutoCAD.ApplicationServices;
using CadAgent.AutoCAD2027.Commands;
using CadAgent.AutoCAD2027.Drawing;
using CadAgent.AutoCAD2027.DrawingSetup;
using CadAgent.AutoCAD2027.Mechanical;
using CadAgent.AutoCAD2027.Review;
using AcadApplication = Autodesk.AutoCAD.ApplicationServices.Application;

namespace CadAgent.AutoCAD2027.Ipc;

public sealed class OperationDispatcher
{
    public const string PluginVersion = "1.0.0";

    private readonly CommandContext _context;
    private readonly ReviewEngine _reviewEngine;
    private readonly Func<AutoCadStandaloneDwgComponentReader> _standaloneReaderFactory;

    public OperationDispatcher(
        CommandContext context,
        Func<AutoCadStandaloneDwgComponentReader>? standaloneReaderFactory = null)
    {
        _context = context ?? throw new ArgumentNullException(nameof(context));
        _reviewEngine = new ReviewEngine(context.DrawingGateway);
        _standaloneReaderFactory = standaloneReaderFactory ?? CreateLiveStandaloneReader;
    }

    public IpcResult Dispatch(IpcRequest? request)
    {
        var startedAt = _context.Clock();
        _context.ClearMechanicalWarnings();
        if (request is null)
        {
            return ErrorToResult(null, new ArgumentNullException(nameof(request)), startedAt);
        }

        try
        {
            var validation = ContractValidator.ValidateRequest(request);
            if (!validation.IsValid)
            {
                return Failure(request, validation.Errors, startedAt);
            }

            return request.Operation switch
            {
                "health" => DispatchHealth(request, startedAt),
                "review" => DispatchReview(request, startedAt),
                "close_disposable" => DispatchCloseDisposable(request, startedAt),
                "mechanical_bom" => DispatchMechanicalBom(request, startedAt),
                "drawing_setup_audit" => DispatchDrawingSetupAudit(request, startedAt),
                "visual_evidence_export" => DispatchVisualEvidenceExport(request, startedAt),
                "native_render_evidence" => DispatchNativeRenderEvidence(request, startedAt),
                ViewportQueryOperationNames.Operation => DispatchViewportQuery(request, startedAt),
                ExactBaseXrefOperationNames.Inspection => DispatchExactBaseXrefInspection(request, startedAt),
                ExactBaseXrefOperationNames.Extraction => DispatchExactBaseXrefExtraction(request, startedAt),
                StandaloneDwgComponentOperationNames.Inspection => DispatchStandaloneInspection(request, startedAt),
                StandaloneDwgComponentOperationNames.Extraction => DispatchStandaloneExtraction(request, startedAt),
                _ => Failure(request, new[] { "operation is not supported" }, startedAt)
            };
        }
        catch (System.Exception exception)
        {
            return ErrorToResult(request, exception, startedAt);
        }
    }

    public IpcResult ErrorToResult(
        IpcRequest? request,
        System.Exception exception,
        DateTimeOffset? startedAt = null)
    {
        ArgumentNullException.ThrowIfNull(exception);
        var started = startedAt ?? _context.Clock();
        var operation = GetResultOperation(request?.Operation);
        var payload = new Dictionary<string, JsonElement>(StringComparer.Ordinal);
        if (!string.IsNullOrWhiteSpace(request?.Operation)
            && !string.Equals(request.Operation, operation, StringComparison.Ordinal))
        {
            payload["requested_operation"] = JsonSerializer.SerializeToElement(request.Operation);
        }

        return CreateResult(
            request?.RequestId is { Length: > 0 } requestId ? requestId : "invalid-request",
            operation,
            NormalizePathOrNull(request?.DrawingFullPath),
            success: false,
            changed: false,
            entityHandles: Array.Empty<string>(),
            warnings: _context.MechanicalWarnings,
            errors: new[] { exception.Message },
            payload,
            started);
    }

    private IpcResult DispatchHealth(IpcRequest request, DateTimeOffset startedAt)
    {
        string? activePath;
        if (request.DrawingFullPath is not null
            && !TryMatchActiveDocument(request.DrawingFullPath, out activePath, out var error))
        {
            return Failure(request, new[] { error }, startedAt);
        }

        activePath = NormalizePathOrNull(_context.DrawingGateway.ActiveDocumentFullPath);
        var pluginIdentity = LoadedPluginIdentity.Capture(typeof(OperationDispatcher).Assembly);
        var payload = new Dictionary<string, JsonElement>(StringComparer.Ordinal)
        {
            ["host"] = JsonSerializer.SerializeToElement("AutoCAD Mechanical 2027"),
            ["plugin_version"] = JsonSerializer.SerializeToElement(PluginVersion),
            ["plugin_binary_path"] = JsonSerializer.SerializeToElement(pluginIdentity.BinaryPath),
            ["plugin_binary_sha256"] = JsonSerializer.SerializeToElement(pluginIdentity.Sha256),
            ["active_document"] = JsonSerializer.SerializeToElement(activePath is not null),
            ["ipc_directory"] = JsonSerializer.SerializeToElement(_context.Store.IpcDirectory),
            ["ipc_readable"] = JsonSerializer.SerializeToElement(true),
            ["ipc_writable"] = JsonSerializer.SerializeToElement(true),
            ["read_only"] = JsonSerializer.SerializeToElement(true)
        };

        return CreateResult(
            request.RequestId!,
            "health",
            activePath,
            success: true,
            changed: false,
            entityHandles: Array.Empty<string>(),
            warnings: Array.Empty<string>(),
            errors: Array.Empty<string>(),
            payload,
            startedAt);
    }

    private IpcResult DispatchReview(IpcRequest request, DateTimeOffset startedAt)
    {
        var handles = request.Parameters!["handles"]
            .EnumerateArray()
            .Select(value => value.GetString()!)
            .ToArray();
        var review = _reviewEngine.Review(new ReviewRequest(request.DrawingFullPath, handles));
        return CreateResult(
            request.RequestId!,
            "review",
            review.DrawingFullPath,
            review.Success,
            review.Changed,
            review.EntityHandles,
            review.Warnings,
            review.Errors,
            review.Payload.ToDictionary(item => item.Key, item => item.Value, StringComparer.Ordinal),
            startedAt);
    }

    private IpcResult DispatchCloseDisposable(IpcRequest request, DateTimeOffset startedAt)
    {
        if (!TryMatchActiveDocument(request.DrawingFullPath, out var activePath, out var error))
        {
            return Failure(request, new[] { error }, startedAt);
        }

        var payload = new Dictionary<string, JsonElement>(StringComparer.Ordinal)
        {
            ["closed_without_saving"] = JsonSerializer.SerializeToElement(true)
        };
        return CreateResult(
            request.RequestId!,
            "close_disposable",
            activePath,
            success: true,
            changed: false,
            entityHandles: Array.Empty<string>(),
            warnings: Array.Empty<string>(),
            errors: Array.Empty<string>(),
            payload,
            startedAt);
    }

    private IpcResult DispatchMechanicalBom(IpcRequest request, DateTimeOffset startedAt)
    {
        if (!TryMatchActiveDocument(request.DrawingFullPath, out var activePath, out var error))
        {
            return Failure(request, new[] { error }, startedAt);
        }

        var mechanicalResult = _context.MechanicalAdapter.Execute(
            new MechanicalOperationRequest("mechanical_bom"));
        var components = NormalizeMechanicalComponents(mechanicalResult.Components);
        var errors = mechanicalResult.Errors.ToArray();
        var warnings = _context.MechanicalWarnings
            .Concat(mechanicalResult.Warnings)
            .ToArray();
        var success = string.Equals(mechanicalResult.Status, "success", StringComparison.Ordinal);
        if (!success && errors.Length == 0)
        {
            errors = new[] { "mechanical_bom is not supported by the active adapter." };
        }

        var payload = new Dictionary<string, JsonElement>(StringComparer.Ordinal)
        {
            ["component_count"] = JsonSerializer.SerializeToElement(components.Count),
            ["components"] = JsonSerializer.SerializeToElement(
                components.Select(component => new
                {
                    handle = component.Handle,
                    block_name = component.BlockName,
                    attributes = component.Attributes.Select(attribute => new
                    {
                        tag = attribute.Tag,
                        value = attribute.Value
                    }).ToArray()
                }).ToArray())
        };

        return CreateResult(
            request.RequestId!,
            "mechanical_bom",
            activePath,
            success,
            changed: false,
            components.Select(component => component.Handle),
            warnings,
            errors,
            payload,
            startedAt);
    }

    private IpcResult DispatchDrawingSetupAudit(IpcRequest request, DateTimeOffset startedAt)
    {
        if (!TryMatchActiveDocument(request.DrawingFullPath, out var activePath, out var error))
        {
            return Failure(request, new[] { error }, startedAt);
        }

        var snapshot = _context.DrawingGateway.ReadDrawingSetup();
        return CreateResult(
            request.RequestId!,
            "drawing_setup_audit",
            activePath,
            success: true,
            changed: false,
            entityHandles: Array.Empty<string>(),
            warnings: Array.Empty<string>(),
            errors: Array.Empty<string>(),
            payload: DrawingSetupPayload.Create(snapshot),
            startedAt);
    }

    private IpcResult DispatchVisualEvidenceExport(IpcRequest request, DateTimeOffset startedAt)
    {
        if (!TryMatchActiveDocument(request.DrawingFullPath, out var activePath, out var error))
        {
            return Failure(request, new[] { error }, startedAt);
        }

        var evidenceRequest = VisualEvidenceRequest.FromIpc(request);
        var snapshot = _context.DrawingGateway.ReadVisualEvidence(evidenceRequest);
        var boundaryErrors = VisualEvidenceReadOnlyBoundary.Validate(evidenceRequest, snapshot);
        if (boundaryErrors.Count != 0)
        {
            return Failure(request, boundaryErrors, startedAt);
        }

        return CreateResult(
            request.RequestId!,
            "visual_evidence_export",
            activePath,
            success: true,
            changed: false,
            entityHandles: Array.Empty<string>(),
            warnings: Array.Empty<string>(),
            errors: Array.Empty<string>(),
            payload: VisualEvidencePayload.Create(snapshot),
            startedAt);
    }

    private IpcResult DispatchNativeRenderEvidence(IpcRequest request, DateTimeOffset startedAt)
    {
        if (!TryMatchActiveDocument(request.DrawingFullPath, out var activePath, out var error))
        {
            return Failure(request, new[] { error }, startedAt);
        }

        var nativeRequest = NativeRenderRequest.FromIpc(request);
        var snapshot = _context.DrawingGateway.ReadNativeRenderEvidence(nativeRequest);
        NativeRenderPolicy.EnsureMatchesRequest(nativeRequest, snapshot);

        return CreateResult(
            request.RequestId!,
            "native_render_evidence",
            activePath,
            success: true,
            changed: false,
            entityHandles: Array.Empty<string>(),
            warnings: snapshot.Warnings,
            errors: Array.Empty<string>(),
            payload: NativeRenderPayload.Create(snapshot),
            startedAt);
    }

    private IpcResult DispatchViewportQuery(IpcRequest request, DateTimeOffset startedAt)
    {
        if (!TryMatchActiveDocument(request.DrawingFullPath, out var activePath, out var error))
        {
            return Failure(request, new[] { error }, startedAt);
        }

        var viewportRequest = ViewportQueryRequest.FromIpc(request);
        var snapshot = _context.DrawingGateway.ReadViewportQuery(viewportRequest);
        if (!string.Equals(
                snapshot.Handle,
                viewportRequest.Handle,
                StringComparison.Ordinal)
            || !string.Equals(
                snapshot.DrawingSha256Before,
                viewportRequest.DrawingSha256,
                StringComparison.Ordinal))
        {
            return Failure(
                request,
                new[] { "viewport_query result did not match the requested handle or source hash" },
                startedAt);
        }

        var result = CreateResult(
            request.RequestId!,
            ViewportQueryOperationNames.Operation,
            activePath,
            success: true,
            changed: false,
            entityHandles: new[] { snapshot.Handle },
            warnings: Array.Empty<string>(),
            errors: Array.Empty<string>(),
            payload: snapshot.ToPayload(),
            startedAt);
        var validation = ContractValidator.ValidateResult(result);
        return validation.IsValid
            ? result
            : Failure(request, validation.Errors, startedAt);
    }

    private IpcResult DispatchExactBaseXrefInspection(IpcRequest request, DateTimeOffset startedAt)
    {
        if (!TryMatchActiveDocument(request.DrawingFullPath, out var activePath, out var error))
        {
            return Failure(
                request,
                new[] { $"{ExactBaseXrefPolicy.ActiveDocumentMismatchCode}: {error}" },
                startedAt);
        }

        var parameters = _context.ExactBaseXrefPolicy.ValidateInspectionRequest(request);
        var snapshot = _context.DrawingGateway.ReadExactBaseXrefInspection(parameters);
        var snapshotErrors = snapshot.Errors.ToList();
        if (!snapshot.Success || snapshot.Evidence is null)
        {
            return Failure(request, snapshotErrors, startedAt);
        }

        if (snapshot.Changed
            || snapshot.Evidence.Changed
            || snapshot.EntityHandles.Count != 0)
        {
            snapshotErrors.Add(
                "S3B_INSPECTION_MUTATION: live inspection must return changed=false and no entity handles");
            return Failure(request, snapshotErrors, startedAt);
        }

        return CreateResult(
            request.RequestId!,
            ExactBaseXrefOperationNames.Inspection,
            activePath,
            success: true,
            changed: false,
            entityHandles: Array.Empty<string>(),
            warnings: snapshot.Warnings,
            errors: Array.Empty<string>(),
            payload: SerializeInspectionEvidence(snapshot.Evidence),
            startedAt);
    }

    private IpcResult DispatchExactBaseXrefExtraction(IpcRequest request, DateTimeOffset startedAt)
    {
        if (!TryMatchActiveDocument(request.DrawingFullPath, out var activePath, out var error))
        {
            return Failure(
                request,
                new[] { $"{ExactBaseXrefPolicy.ActiveDocumentMismatchCode}: {error}" },
                startedAt);
        }

        var parameters = _context.ExactBaseXrefPolicy.ValidateExtractionRequest(request);
        var snapshot = _context.DrawingGateway.ExtractExactBaseXref(
            parameters,
            request.RequestId!);
        if (!snapshot.Success || snapshot.Evidence is null)
        {
            return Failure(request, snapshot.Errors, startedAt);
        }

        return CreateResult(
            request.RequestId!,
            ExactBaseXrefOperationNames.Extraction,
            snapshot.DrawingFullPath ?? activePath,
            success: true,
            changed: true,
            snapshot.EntityHandles,
            snapshot.Warnings,
            snapshot.Errors,
            SerializeExtractionEvidence(snapshot.Evidence),
            startedAt);
    }

    private IpcResult DispatchStandaloneInspection(IpcRequest request, DateTimeOffset startedAt)
    {
        if (!TryMatchActiveDocument(request.DrawingFullPath, out var activePath, out var error))
        {
            return Failure(request, new[] { $"{StandaloneDwgComponentPolicy.SourceIdentityMismatchCode}: {error}" }, startedAt);
        }

        var inspectionRequest = ParseStandaloneInspectionRequest(request);
        var snapshot = _standaloneReaderFactory().Inspect(inspectionRequest);
        if (!snapshot.Success)
        {
            return Failure(request, snapshot.Errors, startedAt);
        }

        var payload = SerializeStandaloneInspectionPayload(request, inspectionRequest, snapshot);
        return CreateResult(
            request.RequestId!,
            StandaloneDwgComponentOperationNames.Inspection,
            activePath,
            success: true,
            changed: false,
            entityHandles: Array.Empty<string>(),
            warnings: snapshot.Warnings,
            errors: Array.Empty<string>(),
            payload,
            startedAt);
    }

    private IpcResult DispatchStandaloneExtraction(IpcRequest request, DateTimeOffset startedAt)
    {
        if (!TryMatchActiveDocument(request.DrawingFullPath, out var activePath, out var error))
        {
            return Failure(request, new[] { $"{StandaloneDwgComponentPolicy.SourceIdentityMismatchCode}: {error}" }, startedAt);
        }

        var plan = ParseStandaloneExtractionPlan(request);
        var snapshot = _standaloneReaderFactory().Extract(plan);
        if (!snapshot.Success || snapshot.Evidence is null)
        {
            var failurePayload = SerializeStandaloneExtractionFailurePayload(request, plan, snapshot);
            return CreateResult(
                request.RequestId!,
                StandaloneDwgComponentOperationNames.Extraction,
                activePath,
                success: false,
                changed: false,
                entityHandles: Array.Empty<string>(),
                warnings: snapshot.Warnings,
                errors: snapshot.Errors,
                failurePayload,
                startedAt);
        }

        var payload = SerializeStandaloneExtractionPayload(plan, snapshot.Evidence);
        return CreateResult(
            request.RequestId!,
            StandaloneDwgComponentOperationNames.Extraction,
            activePath,
            success: true,
            changed: true,
            snapshot.EntityHandles,
            snapshot.Warnings,
            snapshot.Errors,
            payload,
            startedAt);
    }

    private AutoCadStandaloneDwgComponentReader CreateLiveStandaloneReader()
    {
        var document = AcadApplication.DocumentManager.MdiActiveDocument
            ?? throw new InvalidOperationException("No active AutoCAD document is available.");
        var disposableRoot = _context.ExactBaseXrefPolicy.Configuration.DisposableRoot
            ?? throw new InvalidOperationException(
                "CAD_AGENT_S3B_DISPOSABLE_ROOT is required for standalone extraction.");
        return new AutoCadStandaloneDwgComponentReader(
            new AutoCadStandaloneDwgComponentDatabase(document),
            new StandaloneDwgComponentPolicy(disposableRoot));
    }

    private static StandaloneDwgComponentInspectionRequest ParseStandaloneInspectionRequest(IpcRequest request)
    {
        var parameters = request.Parameters!;
        return new StandaloneDwgComponentInspectionRequest
        {
            SchemaVersion = RequiredString(parameters, "schema_version"),
            RequestId = RequiredString(parameters, "request_id"),
            RunId = RequiredString(parameters, "run_id"),
            SourceDrawingPath = RequiredString(parameters, "source_drawing_path"),
            SourceDrawingSha256 = RequiredString(parameters, "source_drawing_sha256"),
            SourceSetupAuditSha256 = RequiredString(parameters, "source_setup_audit_sha256"),
            ExpectedDbmod = checked((int)parameters["expected_dbmod"].GetInt64()),
            SelectionGroups = parameters["selection_groups"].EnumerateArray()
                .Select(group => new StandaloneDwgComponentSelectionGroup
                {
                    GroupId = RequiredString(group, "group_id"),
                    LogicalComponentId = RequiredString(group, "logical_component_id"),
                    SourceHandles = StringArray(group, "source_handles"),
                    ExpectedEntityTypes = StringArray(group, "expected_entity_types"),
                    SourceLayerExpectations = StringArray(group, "source_layer_expectations")
                })
                .ToArray()
        };
    }

    private static StandaloneDwgComponentExtractionPlan ParseStandaloneExtractionPlan(IpcRequest request)
    {
        var parameters = request.Parameters!;
        var approval = parameters["approval"];
        return new StandaloneDwgComponentExtractionPlan
        {
            PlanId = RequiredString(parameters, "plan_id"),
            RequestId = RequiredString(parameters, "request_id"),
            RunId = RequiredString(parameters, "run_id"),
            InspectionId = RequiredString(parameters, "inspection_id"),
            InspectionSha256 = RequiredString(parameters, "inspection_sha256"),
            SourceDrawingSha256 = RequiredString(parameters, "source_drawing_sha256"),
            CandidateOutputPath = RequiredString(parameters, "candidate_output_path"),
            CandidateBaseModel = RequiredString(parameters, "candidate_base_model"),
            TransformPolicy = RequiredString(parameters, "transform_policy"),
            Approval = new StandaloneDwgComponentApproval
            {
                Reference = RequiredString(approval, "reference"),
                Status = RequiredString(approval, "status")
            },
            Components = parameters["components"].EnumerateArray()
                .Select(component =>
                {
                    var transform = component.GetProperty("transform");
                    var translation = transform.GetProperty("translation");
                    return new StandaloneDwgComponentPlanComponent
                    {
                        GroupId = RequiredString(component, "group_id"),
                        LogicalComponentId = RequiredString(component, "logical_component_id"),
                        SourceHandles = StringArray(component, "source_handles"),
                        Transform = new StandaloneDwgComponentTransform
                        {
                            RotationDegrees = transform.GetProperty("rotation_degrees").GetDouble(),
                            UniformScale = transform.GetProperty("uniform_scale").GetDouble(),
                            Translation = new StandaloneDwgComponentPoint
                            {
                                X = translation.GetProperty("x").GetDouble(),
                                Y = translation.GetProperty("y").GetDouble(),
                                Z = translation.GetProperty("z").GetDouble()
                            }
                        }
                    };
                })
                .ToArray()
        };
    }

    private static Dictionary<string, JsonElement> SerializeStandaloneInspectionPayload(
        IpcRequest request,
        StandaloneDwgComponentInspectionRequest inspectionRequest,
        StandaloneDwgComponentInspectionSnapshot snapshot)
    {
        var groups = inspectionRequest.SelectionGroups
            .Select(group =>
            {
                var selected = snapshot.Entities
                    .Where(entity => group.SourceHandles.Contains(entity.SourceHandle, StringComparer.OrdinalIgnoreCase))
                    .ToArray();
                var groupPayload = new Dictionary<string, JsonElement>(StringComparer.Ordinal)
                {
                    ["group_id"] = JsonSerializer.SerializeToElement(group.GroupId),
                    ["logical_component_id"] = JsonSerializer.SerializeToElement(group.LogicalComponentId),
                    ["source_handles"] = JsonSerializer.SerializeToElement(group.SourceHandles),
                    ["entity_types"] = JsonSerializer.SerializeToElement(selected.Select(entity => entity.EntityType).Distinct(StringComparer.Ordinal).OrderBy(value => value, StringComparer.Ordinal).ToArray()),
                    ["layers"] = JsonSerializer.SerializeToElement(selected.Select(entity => entity.Layer).Distinct(StringComparer.Ordinal).OrderBy(value => value, StringComparer.Ordinal).ToArray())
                };
                groupPayload["signature_sha256"] = JsonSerializer.SerializeToElement(CanonicalSha256(groupPayload));
                return groupPayload;
            })
            .ToArray();
        var payload = new Dictionary<string, JsonElement>(StringComparer.Ordinal)
        {
            ["schema_version"] = JsonSerializer.SerializeToElement("standalone-dwg-component-inspection-result-1.0"),
            ["inspection_id"] = JsonSerializer.SerializeToElement(inspectionRequest.RequestId),
            ["request_id"] = JsonSerializer.SerializeToElement(inspectionRequest.RequestId),
            ["source_identity"] = JsonSerializer.SerializeToElement(new
            {
                path = snapshot.DrawingFullPath,
                sha256 = snapshot.SourceSha256Before,
                dbmod = snapshot.DbmodBefore,
                xref_count = 0
            }),
            ["source_sha256_before"] = JsonSerializer.SerializeToElement(snapshot.SourceSha256Before),
            ["source_sha256_after"] = JsonSerializer.SerializeToElement(snapshot.SourceSha256After),
            ["dbmod_before"] = JsonSerializer.SerializeToElement(snapshot.DbmodBefore),
            ["dbmod_after"] = JsonSerializer.SerializeToElement(snapshot.DbmodAfter),
            ["read_only"] = JsonSerializer.SerializeToElement(snapshot.ReadOnly),
            ["groups"] = JsonSerializer.SerializeToElement(groups),
            ["warnings"] = JsonSerializer.SerializeToElement(snapshot.Warnings),
            ["conflicts"] = JsonSerializer.SerializeToElement(Array.Empty<string>()),
            ["changed"] = JsonSerializer.SerializeToElement(snapshot.Changed),
            ["eligible"] = JsonSerializer.SerializeToElement(snapshot.Eligible),
        };
        payload["inspection_sha256"] = JsonSerializer.SerializeToElement(CanonicalSha256(payload));
        return payload;
    }

    private static Dictionary<string, JsonElement> SerializeStandaloneExtractionPayload(
        StandaloneDwgComponentExtractionPlan plan,
        StandaloneDwgComponentCandidateSnapshot evidence)
    {
        var mappingBySource = evidence.Mappings.ToDictionary(
            mapping => StandaloneDwgComponentPolicy.NormalizeHandle(mapping.SourceHandle),
            mapping => StandaloneDwgComponentPolicy.NormalizeHandle(mapping.CandidateHandle),
            StringComparer.OrdinalIgnoreCase);
        var components = plan.Components.Select(component => new
        {
            group_id = component.GroupId,
            logical_component_id = component.LogicalComponentId,
            source_handles = component.SourceHandles.Select(StandaloneDwgComponentPolicy.NormalizeHandle).ToArray(),
            candidate_handles = component.SourceHandles
                .Select(StandaloneDwgComponentPolicy.NormalizeHandle)
                .Select(handle => mappingBySource[handle])
                .ToArray()
        }).ToArray();
        var payload = new Dictionary<string, JsonElement>(StringComparer.Ordinal)
        {
            ["schema_version"] = JsonSerializer.SerializeToElement("standalone-dwg-component-extraction-result-1.0"),
            ["request_id"] = JsonSerializer.SerializeToElement(plan.RequestId),
            ["run_id"] = JsonSerializer.SerializeToElement(plan.RunId),
            ["source_drawing_sha256"] = JsonSerializer.SerializeToElement(plan.SourceDrawingSha256),
            ["candidate_base_model"] = JsonSerializer.SerializeToElement("EMPTY_NEW_DATABASE"),
            ["candidate_output_sha256"] = JsonSerializer.SerializeToElement(evidence.CandidateOutputSha256),
            ["candidate_output_identity"] = JsonSerializer.SerializeToElement(new
            {
                path = evidence.CandidateOutputPath,
                file_id = evidence.CandidateOutputIdentity
            }),
            ["source_mutated"] = JsonSerializer.SerializeToElement(evidence.SourceMutated),
            ["source_dbmod_before"] = JsonSerializer.SerializeToElement(evidence.SourceDbmodBefore),
            ["source_dbmod_after"] = JsonSerializer.SerializeToElement(evidence.SourceDbmodAfter),
            ["save_performed"] = JsonSerializer.SerializeToElement(evidence.SavePerformed),
            ["components"] = JsonSerializer.SerializeToElement(components),
            ["source_handle_to_candidate_handle"] = JsonSerializer.SerializeToElement(
                evidence.Mappings.Select(mapping => new
                {
                    source_handle = StandaloneDwgComponentPolicy.NormalizeHandle(mapping.SourceHandle),
                    candidate_handle = StandaloneDwgComponentPolicy.NormalizeHandle(mapping.CandidateHandle)
                }).ToArray())
        };
        payload["result_sha256"] = JsonSerializer.SerializeToElement(CanonicalSha256(payload));
        return payload;
    }

    private static Dictionary<string, JsonElement> SerializeStandaloneExtractionFailurePayload(
        IpcRequest request,
        StandaloneDwgComponentExtractionPlan plan,
        StandaloneDwgComponentExtractionSnapshot snapshot)
    {
        var code = snapshot.Errors.Any(error => error.Contains(StandaloneDwgComponentPolicy.CleanupFailedCode, StringComparison.Ordinal))
            ? "CLEANUP_FAILED"
            : snapshot.Errors.Any(error => error.Contains(StandaloneDwgComponentPolicy.CandidateOutputNotReopenableCode, StringComparison.Ordinal))
                ? "OUTPUT_NOT_REOPENABLE"
                : snapshot.Errors.Any(error => error.Contains(StandaloneDwgComponentPolicy.SourceFreshnessMismatchCode, StringComparison.Ordinal))
                    ? "SOURCE_MUTATED"
                    : snapshot.Errors.Any(error => error.Contains(StandaloneDwgComponentPolicy.ForbiddenWriteTargetCode, StringComparison.Ordinal))
                        ? "FORBIDDEN_WRITE_TARGET"
                        : "CANDIDATE_OUTPUT_NOT_ABSENT";
        return new Dictionary<string, JsonElement>(StringComparer.Ordinal)
        {
            ["schema_version"] = JsonSerializer.SerializeToElement("standalone-dwg-component-extraction-result-1.0"),
            ["request_id"] = JsonSerializer.SerializeToElement(plan.RequestId ?? request.RequestId),
            ["run_id"] = JsonSerializer.SerializeToElement(plan.RunId),
            ["failure_code"] = JsonSerializer.SerializeToElement(code),
            ["candidate_output_path"] = JsonSerializer.SerializeToElement(plan.CandidateOutputPath),
            ["source_mutated"] = JsonSerializer.SerializeToElement(false),
            ["save_performed"] = JsonSerializer.SerializeToElement(false)
        };
    }

    private static string RequiredString(
        IReadOnlyDictionary<string, JsonElement> values,
        string name) => values[name].GetString() ?? throw new InvalidDataException($"{name} must be a string");

    private static string RequiredString(JsonElement value, string name) =>
        value.GetProperty(name).GetString() ?? throw new InvalidDataException($"{name} must be a string");

    private static string[] StringArray(IReadOnlyDictionary<string, JsonElement> values, string name) =>
        values[name].EnumerateArray().Select(item => item.GetString()!).ToArray();

    private static string[] StringArray(JsonElement value, string name) =>
        value.GetProperty(name).EnumerateArray().Select(item => item.GetString()!).ToArray();

    private static string CanonicalSha256(IReadOnlyDictionary<string, JsonElement> values)
    {
        var json = "{" + string.Join(",", values.Keys.OrderBy(key => key, StringComparer.Ordinal)
            .Select(key => JsonSerializer.Serialize(key) + ":" + CanonicalJson(values[key]))) + "}";
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(json))).ToLowerInvariant();
    }

    private static string CanonicalJson(JsonElement value) => value.ValueKind switch
    {
        JsonValueKind.Object => "{" + string.Join(",", value.EnumerateObject()
            .OrderBy(property => property.Name, StringComparer.Ordinal)
            .Select(property => JsonSerializer.Serialize(property.Name) + ":" + CanonicalJson(property.Value))) + "}",
        JsonValueKind.Array => "[" + string.Join(",", value.EnumerateArray().Select(CanonicalJson)) + "]",
        JsonValueKind.String => JsonSerializer.Serialize(value.GetString()),
        JsonValueKind.Number => value.GetRawText(),
        JsonValueKind.True => "true",
        JsonValueKind.False => "false",
        JsonValueKind.Null => "null",
        _ => throw new InvalidDataException("standalone payload contains an unsupported JSON value")
    };

    private static Dictionary<string, JsonElement> SerializeExtractionEvidence(
        ExactBaseXrefExtractionEvidence evidence) =>
        JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(
            JsonSerializer.Serialize(evidence, ContractJson.Options),
            ContractJson.Options)
        ?? throw new InvalidOperationException("exact-base extraction evidence could not be serialized");

    private static Dictionary<string, JsonElement> SerializeInspectionEvidence(
        ExactBaseXrefLiveInspection evidence) =>
        JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(
            JsonSerializer.Serialize(evidence, ContractJson.Options),
            ContractJson.Options)
        ?? throw new InvalidOperationException("exact-base inspection evidence could not be serialized");

    private static IReadOnlyList<MechanicalComponentSnapshot> NormalizeMechanicalComponents(
        IReadOnlyList<MechanicalComponentSnapshot> components) =>
        components
            .Select(component => new MechanicalComponentSnapshot(
                component.Handle,
                component.BlockName,
                component.Attributes
                    .Select(attribute => new MechanicalAttributeSnapshot(
                        NormalizeMechanicalTag(attribute.Tag),
                        attribute.Value ?? string.Empty))
                    .OrderBy(attribute => attribute.Tag, StringComparer.Ordinal)
                    .ThenBy(attribute => attribute.Value, StringComparer.Ordinal)
                    .ToArray()))
            .OrderBy(component => component.Handle, StringComparer.Ordinal)
            .ToArray();

    private static string NormalizeMechanicalTag(string? tag) =>
        (tag ?? string.Empty).Trim().ToUpperInvariant();

    private bool TryMatchActiveDocument(
        string? requestedPath,
        out string activePath,
        out string error)
    {
        activePath = NormalizePathOrNull(_context.DrawingGateway.ActiveDocumentFullPath) ?? string.Empty;
        if (activePath.Length == 0)
        {
            error = "No active document is available.";
            return false;
        }

        var normalizedRequestedPath = NormalizePathOrNull(requestedPath);
        if (normalizedRequestedPath is null
            || !StringComparer.OrdinalIgnoreCase.Equals(normalizedRequestedPath, activePath))
        {
            error = "The requested drawing_full_path does not match the active document full path.";
            return false;
        }

        error = string.Empty;
        return true;
    }

    private IpcResult Failure(
        IpcRequest request,
        IEnumerable<string> errors,
        DateTimeOffset startedAt) =>
        CreateResult(
            request.RequestId is { Length: > 0 } requestId ? requestId : "invalid-request",
            GetResultOperation(request.Operation),
            NormalizePathOrNull(request.DrawingFullPath),
            success: false,
            changed: false,
            entityHandles: Array.Empty<string>(),
            warnings: Array.Empty<string>(),
            errors,
            CreateRequestedOperationPayload(request.Operation),
            startedAt);

    private IpcResult CreateResult(
        string requestId,
        string operation,
        string? drawingFullPath,
        bool success,
        bool changed,
        IEnumerable<string> entityHandles,
        IEnumerable<string> warnings,
        IEnumerable<string> errors,
        Dictionary<string, JsonElement> payload,
        DateTimeOffset startedAt) =>
        new()
        {
            RequestId = requestId,
            Success = success,
            Operation = operation,
            DrawingFullPath = drawingFullPath,
            Changed = changed,
            EntityHandles = entityHandles.ToList(),
            Warnings = warnings.ToList(),
            Errors = errors.ToList(),
            StartedAt = startedAt,
            CompletedAt = _context.Clock(),
            Payload = payload
        };

    private static Dictionary<string, JsonElement> CreateRequestedOperationPayload(string? operation)
    {
        var payload = new Dictionary<string, JsonElement>(StringComparer.Ordinal);
        if (!string.IsNullOrWhiteSpace(operation)
            && !ContractConstants.SupportedOperations.Contains(operation))
        {
            payload["requested_operation"] = JsonSerializer.SerializeToElement(operation);
        }

        return payload;
    }

    private static string GetResultOperation(string? operation) =>
        operation is not null && ContractConstants.SupportedOperations.Contains(operation)
            ? operation
            : "health";

    private static string? NormalizePathOrNull(string? path) =>
        path is not null && ContractValidator.TryNormalizeWindowsAbsolutePath(path, out var normalized)
            ? normalized
            : null;
}
