using System.Globalization;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using CadAgent.AutoCAD2027.Ipc;
using AcadApplication = Autodesk.AutoCAD.ApplicationServices.Application;

namespace CadAgent.AutoCAD2027.Drawing;

public interface IExactBaseXrefDatabase
{
    string? ActiveDocumentFullPath { get; }

    int ReadDbmod();

    string ComputeSha256(string path);

    ExactBaseXrefDatabaseCapture ReadNamedExternalXref(
        ExactBaseXrefInspectionParameters request);

    ExactBaseXrefDatabaseExtractionResult ExtractApprovedComponents(
        ExactBaseXrefExtractionParameters request,
        IReadOnlyList<ExactBaseXrefPlanComponent> approvedComponents,
        ExactBaseXrefLiveInspection preflight) =>
        throw new InvalidOperationException(
            "This database gateway does not provide exact-base Xref extraction.");

    bool IsCandidatePathAbsent(string path) =>
        !File.Exists(path) && !Directory.Exists(path);

    string CaptureCandidateIdentity(string path) =>
        throw new InvalidOperationException("Candidate identity capture is unavailable.");

    bool DeleteCandidateIfIdentityMatches(string path, string identity) => false;
}

public sealed class ExactBaseXrefDatabaseCapture
{
    public string? XrefName { get; init; }

    public bool IsExternalReference { get; init; }

    public bool IsReadOnly { get; init; }

    public string? Vehicle { get; init; }

    public string? Model { get; init; }

    public IReadOnlyList<ExactBaseXrefDatabaseDimension> CriticalDimensions { get; init; } =
        Array.Empty<ExactBaseXrefDatabaseDimension>();

    public IReadOnlyList<ExactBaseXrefDatabaseComponent> Components { get; init; } =
        Array.Empty<ExactBaseXrefDatabaseComponent>();
}

public sealed class ExactBaseXrefDatabaseDimension
{
    public string? Control { get; init; }

    public double Observed { get; init; }

    public string? Unit { get; init; }
}

public sealed class ExactBaseXrefDatabaseComponent
{
    public string? ComponentType { get; init; }

    public string? SourceBlock { get; init; }

    public string? SourceHandle { get; init; }

    public string? SourceLayer { get; init; }

    public ExactBaseXrefBounding? Bounding { get; init; }
}

public sealed class ExactBaseXrefInspectionSnapshot
{
    public bool Success { get; init; }

    public string? DrawingFullPath { get; init; }

    public bool Changed { get; init; }

    public IReadOnlyList<string> EntityHandles { get; init; } = Array.Empty<string>();

    public ExactBaseXrefLiveInspection? Evidence { get; init; }

    public IReadOnlyList<string> Warnings { get; init; } = Array.Empty<string>();

    public IReadOnlyList<string> Errors { get; init; } = Array.Empty<string>();

    public Func<string, ExactBaseXrefExtractionSnapshot>? ExtractionOperation { get; init; }

    public static ExactBaseXrefInspectionSnapshot Unavailable(string error) => new()
    {
        Success = false,
        Changed = false,
        EntityHandles = Array.Empty<string>(),
        Errors = new[] { error }
    };
}

public sealed class ExactBaseXrefDatabaseExtractionResult
{
    public bool CandidateCreated { get; init; }

    public string? CandidateOutputIdentity { get; init; }

    public string? CandidateInputSha256 { get; init; }

    public string? CandidateOutputSha256 { get; init; }

    public bool SavePerformed { get; init; }

    public IReadOnlyList<ExactBaseXrefDatabaseExtractedComponent> Components { get; init; } =
        Array.Empty<ExactBaseXrefDatabaseExtractedComponent>();
}

public sealed class ExactBaseXrefDatabaseExtractedComponent
{
    public string? SourceHandle { get; init; }

    public string? CandidateHandle { get; init; }
}

public sealed class ExactBaseXrefExtractionSnapshot
{
    public bool Success { get; init; }

    public string? DrawingFullPath { get; init; }

    public bool Changed { get; init; }

    public IReadOnlyList<string> EntityHandles { get; init; } = Array.Empty<string>();

    public ExactBaseXrefExtractionEvidence? Evidence { get; init; }

    public IReadOnlyList<string> Warnings { get; init; } = Array.Empty<string>();

    public IReadOnlyList<string> Errors { get; init; } = Array.Empty<string>();

    public static ExactBaseXrefExtractionSnapshot Failure(
        string? drawingFullPath,
        IEnumerable<string> errors) => new()
        {
            Success = false,
            DrawingFullPath = drawingFullPath,
            Changed = false,
            EntityHandles = Array.Empty<string>(),
            Warnings = Array.Empty<string>(),
            Errors = errors.ToArray()
        };
}

public sealed class ExactBaseXrefExtractionEvidence
{
    [JsonPropertyName("accepted_target_overwrite")]
    public bool AcceptedTargetOverwrite { get; init; }

    [JsonPropertyName("candidate_changed_during_operation")]
    public bool CandidateChangedDuringOperation { get; init; }

    [JsonPropertyName("candidate_input_path")]
    public string? CandidateInputPath { get; init; }

    [JsonPropertyName("candidate_input_sha256")]
    public string? CandidateInputSha256 { get; init; }

    [JsonPropertyName("candidate_output_path")]
    public string? CandidateOutputPath { get; init; }

    [JsonPropertyName("candidate_output_sha256")]
    public string? CandidateOutputSha256 { get; init; }

    [JsonPropertyName("components")]
    public IReadOnlyList<ExactBaseXrefExtractionComponentEvidence> Components { get; init; } =
        Array.Empty<ExactBaseXrefExtractionComponentEvidence>();

    [JsonPropertyName("live_preflight")]
    public ExactBaseXrefLivePreflightEvidence? LivePreflight { get; init; }

    [JsonPropertyName("plan_id")]
    public string? PlanId { get; init; }

    [JsonPropertyName("request_id")]
    public string? RequestId { get; init; }

    [JsonPropertyName("run_id")]
    public string? RunId { get; init; }

    [JsonPropertyName("save_performed")]
    public bool SavePerformed { get; init; }

    [JsonPropertyName("schema_version")]
    public string SchemaVersion { get; init; } = "exact-base-xref-extraction-result-1.0";

    [JsonPropertyName("source_handle_to_candidate_handle")]
    public IReadOnlyList<ExactBaseXrefHandleMapping> SourceHandleToCandidateHandle { get; init; } =
        Array.Empty<ExactBaseXrefHandleMapping>();

    [JsonPropertyName("source_mutated")]
    public bool SourceMutated { get; init; }

    [JsonPropertyName("source_revision")]
    public string? SourceRevision { get; init; }

    [JsonPropertyName("source_saved")]
    public bool SourceSaved { get; init; }

    [JsonPropertyName("source_sha256_after")]
    public string? SourceSha256After { get; init; }

    [JsonPropertyName("source_sha256_before")]
    public string? SourceSha256Before { get; init; }

    [JsonPropertyName("warnings")]
    public IReadOnlyList<string> Warnings { get; init; } = Array.Empty<string>();
}

public sealed class ExactBaseXrefExtractionComponentEvidence
{
    [JsonPropertyName("candidate_handle")]
    public string? CandidateHandle { get; init; }

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

    [JsonPropertyName("source_revision")]
    public string? SourceRevision { get; init; }

    [JsonPropertyName("source_sha256")]
    public string? SourceSha256 { get; init; }

    [JsonPropertyName("transform")]
    public ExactBaseXrefTransform? Transform { get; init; }
}

public sealed class ExactBaseXrefHandleMapping
{
    [JsonPropertyName("source_handle")]
    public string? SourceHandle { get; init; }

    [JsonPropertyName("candidate_handle")]
    public string? CandidateHandle { get; init; }
}

public sealed class ExactBaseXrefLivePreflightEvidence
{
    [JsonPropertyName("dbmod_after")]
    public int DbmodAfter { get; init; }

    [JsonPropertyName("dbmod_before")]
    public int DbmodBefore { get; init; }

    [JsonPropertyName("eligible")]
    public bool Eligible { get; init; }

    [JsonPropertyName("evidence_sha256")]
    public string? EvidenceSha256 { get; init; }

    [JsonPropertyName("inspection_id")]
    public string? InspectionId { get; init; }

    [JsonPropertyName("source_sha256")]
    public string? SourceSha256 { get; init; }

    [JsonPropertyName("target_drawing_sha256")]
    public string? TargetDrawingSha256 { get; init; }

    [JsonPropertyName("xref")]
    public ExactBaseXrefLiveXref? Xref { get; init; }
}

public sealed class AutoCadExactBaseXrefReader
{
    private const string LiveSchemaVersion = "exact-base-xref-inspection-1.0";
    private const string Pass = "PASS";
    private const string Fail = "FAIL";

    private readonly IExactBaseXrefDatabase _database;
    private readonly ExactBaseXrefPolicy _policy;
    private readonly Func<DateTimeOffset> _clock;

    public AutoCadExactBaseXrefReader(
        IExactBaseXrefDatabase database,
        ExactBaseXrefPolicy policy,
        Func<DateTimeOffset>? clock = null)
    {
        _database = database ?? throw new ArgumentNullException(nameof(database));
        _policy = policy ?? throw new ArgumentNullException(nameof(policy));
        _clock = clock ?? (() => DateTimeOffset.UtcNow);
    }

    public ExactBaseXrefInspectionSnapshot Read(
        ExactBaseXrefInspectionParameters request)
    {
        if (request is ExactBaseXrefExtractionParameters extraction)
        {
            return new ExactBaseXrefInspectionSnapshot
            {
                ExtractionOperation = requestId => Extract(extraction, requestId),
                Changed = false,
                EntityHandles = Array.Empty<string>(),
                Warnings = Array.Empty<string>(),
                Errors = Array.Empty<string>()
            };
        }

        return ReadInternal(request, requireAcceptedTarget: true, expectedTargetHash: null);
    }

    public ExactBaseXrefInspectionSnapshot ReadExtractionPreflight(
        ExactBaseXrefExtractionParameters request)
    {
        ArgumentNullException.ThrowIfNull(request);
        var expectedTargetHash = request.ExtractionPlan?.TargetDrawingSha256
            ?? throw new ExactBaseXrefPolicyException(
                ExactBaseXrefPolicy.RequestInvalidCode,
                "extraction plan target hash is required for live preflight");
        return ReadInternal(request, requireAcceptedTarget: false, expectedTargetHash);
    }

    public ExactBaseXrefExtractionSnapshot Extract(
        ExactBaseXrefExtractionParameters request,
        string requestId)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentException.ThrowIfNullOrWhiteSpace(requestId);

        string? activePath = null;
        string? sourcePath = null;
        string? sourceHashBefore = null;
        ExactBaseXrefDatabaseExtractionResult? extraction = null;
        try
        {
            activePath = CanonicalActivePath(_database.ActiveDocumentFullPath);
            var outputPath = ContractValidator.NormalizeWindowsAbsolutePath(
                request.CandidateOutputPath
                ?? throw new ExactBaseXrefPolicyException(
                    ExactBaseXrefPolicy.RequestInvalidCode,
                    "candidate output path is required"));
            if (!_database.IsCandidatePathAbsent(outputPath))
            {
                return ExactBaseXrefExtractionSnapshot.Failure(
                    activePath,
                    new[] { $"{ExactBaseXrefPolicy.CandidateOutputExistsCode}: candidate output already exists" });
            }

            sourcePath = _policy.Configuration.ExactBaseSourcePath
                ?? throw new ExactBaseXrefPolicyException(
                    ExactBaseXrefPolicy.ConfigurationRequiredCode,
                    "exact-base source path is missing");
            sourceHashBefore = _database.ComputeSha256(sourcePath);
            var inputHashBefore = _database.ComputeSha256(activePath);
            var preflight = ReadExtractionPreflight(request);
            if (!preflight.Success || preflight.Evidence is null)
            {
                return ExactBaseXrefExtractionSnapshot.Failure(activePath, preflight.Errors);
            }

            var plan = request.ExtractionPlan
                ?? throw new ExactBaseXrefPolicyException(
                    ExactBaseXrefPolicy.RequestInvalidCode,
                    "extraction plan is required");
            var planErrors = ValidatePlanAgainstFreshPreflight(plan, preflight.Evidence, request);
            if (planErrors.Count != 0)
            {
                return ExactBaseXrefExtractionSnapshot.Failure(activePath, planErrors);
            }

            // No prior inspection or run_id is used here. This is the only database
            // call after the fresh live preflight and immediately precedes mutation.
            extraction = _database.ExtractApprovedComponents(
                request,
                plan.Components!,
                preflight.Evidence);
            if (extraction is null || !extraction.CandidateCreated || !extraction.SavePerformed)
            {
                return ExactBaseXrefExtractionSnapshot.Failure(
                    activePath,
                    new[] { "S3B_CANDIDATE_SAVE_REQUIRED: candidate extraction did not create and save a new output" });
            }

            var sourceHashAfter = _database.ComputeSha256(sourcePath);
            var inputHashAfter = _database.ComputeSha256(activePath);
            var candidateOutputHash = _database.ComputeSha256(outputPath);
            var errors = new List<string>();
            if (!IsSha256(sourceHashBefore)
                || !IsSha256(sourceHashAfter)
                || !string.Equals(sourceHashBefore, sourceHashAfter, StringComparison.Ordinal)
                || !string.Equals(sourceHashBefore, _policy.Configuration.ExactBaseSourceSha256, StringComparison.Ordinal))
            {
                errors.Add("S3B_SOURCE_HASH_MISMATCH: source hash changed during extraction or did not match server configuration");
            }

            if (!IsSha256(inputHashBefore)
                || !IsSha256(inputHashAfter)
                || !string.Equals(inputHashBefore, inputHashAfter, StringComparison.Ordinal))
            {
                errors.Add("S3B_CANDIDATE_INPUT_CHANGED: active candidate input changed during extraction");
            }

            if (!IsSha256(candidateOutputHash))
            {
                errors.Add("S3B_CANDIDATE_OUTPUT_HASH_INVALID: candidate output hash could not be verified as a lowercase SHA-256");
            }

            var componentEvidence = BuildExtractionComponents(
                plan,
                extraction.Components,
                sourceHashBefore,
                request.SourceRevision,
                errors);
            if (errors.Count != 0)
            {
                CleanupOwnedCandidate(outputPath, extraction, errors);
                return ExactBaseXrefExtractionSnapshot.Failure(activePath, errors);
            }

            var candidateHandles = componentEvidence
                .Select(component => component.CandidateHandle!)
                .OrderBy(handle => handle, StringComparer.Ordinal)
                .ToArray();
            var mappings = componentEvidence
                .Select(component => new ExactBaseXrefHandleMapping
                {
                    SourceHandle = component.SourceHandle,
                    CandidateHandle = component.CandidateHandle
                })
                .OrderBy(mapping => mapping.SourceHandle, StringComparer.OrdinalIgnoreCase)
                .ToArray();
            var evidence = new ExactBaseXrefExtractionEvidence
            {
                AcceptedTargetOverwrite = false,
                CandidateChangedDuringOperation = true,
                CandidateInputPath = activePath,
                CandidateInputSha256 = inputHashAfter,
                CandidateOutputPath = outputPath,
                CandidateOutputSha256 = candidateOutputHash,
                Components = componentEvidence,
                LivePreflight = BuildLivePreflightEvidence(preflight.Evidence),
                PlanId = plan.PlanId,
                RequestId = requestId,
                RunId = request.RunId,
                SavePerformed = true,
                SourceHandleToCandidateHandle = mappings,
                SourceMutated = false,
                SourceRevision = request.SourceRevision,
                SourceSaved = false,
                SourceSha256After = sourceHashAfter,
                SourceSha256Before = sourceHashBefore,
                Warnings = Array.Empty<string>()
            };
            return new ExactBaseXrefExtractionSnapshot
            {
                Success = true,
                DrawingFullPath = activePath,
                Changed = true,
                EntityHandles = candidateHandles,
                Evidence = evidence,
                Warnings = Array.Empty<string>(),
                Errors = Array.Empty<string>()
            };
        }
        catch (Exception exception)
        {
            var errors = new List<string> { exception.Message };
            if (sourcePath is not null && sourceHashBefore is not null)
            {
                try
                {
                    var sourceHashAfter = _database.ComputeSha256(sourcePath);
                    if (!IsSha256(sourceHashAfter)
                        || !string.Equals(sourceHashBefore, sourceHashAfter, StringComparison.Ordinal))
                    {
                        errors.Add("S3B_SOURCE_HASH_MISMATCH: source hash could not be proven stable after extraction failure");
                    }
                }
                catch (Exception sourceException)
                {
                    errors.Add($"S3B_SOURCE_HASH_UNAVAILABLE: source hash could not be rechecked after extraction failure: {sourceException.Message}");
                }
            }

            if (extraction is not null
                && request.CandidateOutputPath is string rawOutputPath
                && ContractValidator.TryNormalizeWindowsAbsolutePath(rawOutputPath, out var cleanupPath))
            {
                CleanupOwnedCandidate(cleanupPath, extraction, errors);
            }

            return ExactBaseXrefExtractionSnapshot.Failure(
                activePath,
                errors);
        }
    }

    private ExactBaseXrefInspectionSnapshot ReadInternal(
        ExactBaseXrefInspectionParameters request,
        bool requireAcceptedTarget,
        string? expectedTargetHash)
    {
        ArgumentNullException.ThrowIfNull(request);

        string? activePath = null;
        try
        {
            activePath = CanonicalActivePath(_database.ActiveDocumentFullPath);
            var configuration = _policy.Configuration;
            var errors = new List<string>();
            if (!_policy.IsConfigured)
            {
                errors.AddRange(_policy.ConfigurationErrors);
            }

            if (requireAcceptedTarget && !SamePath(activePath, configuration.AcceptedDwgPath))
            {
                errors.Add("S3B_ACTIVE_DOCUMENT_MISMATCH: active drawing is not the server-owned accepted DWG");
            }

            var sourcePath = configuration.ExactBaseSourcePath
                ?? throw new ExactBaseXrefPolicyException(
                    ExactBaseXrefPolicy.ConfigurationRequiredCode,
                    "exact-base source path is missing");
            var sourceHashBefore = _database.ComputeSha256(sourcePath);
            var targetHashBefore = _database.ComputeSha256(activePath);
            var dbmodBefore = _database.ReadDbmod();
            var capture = _database.ReadNamedExternalXref(request)
                ?? throw new InvalidOperationException("the AutoCAD Xref reader returned no capture");
            var sourceHashAfter = _database.ComputeSha256(sourcePath);
            var targetHashAfter = _database.ComputeSha256(activePath);
            var dbmodAfter = _database.ReadDbmod();

            if (!string.Equals(sourceHashBefore, sourceHashAfter, StringComparison.Ordinal)
                || !string.Equals(sourceHashBefore, configuration.ExactBaseSourceSha256, StringComparison.Ordinal))
            {
                errors.Add("S3B_SOURCE_HASH_MISMATCH: source hash was not stable or did not match server configuration");
            }

            if (!string.Equals(targetHashBefore, targetHashAfter, StringComparison.Ordinal))
            {
                errors.Add("S3B_TARGET_HASH_CHANGED: target DWG hash changed during read-only inspection");
            }

            if (dbmodBefore != dbmodAfter)
            {
                errors.Add($"S3B_DBMOD_CHANGED: target DBMOD changed from {dbmodBefore} to {dbmodAfter}");
            }

            if (expectedTargetHash is not null
                && !string.Equals(targetHashBefore, expectedTargetHash, StringComparison.Ordinal))
            {
                errors.Add("S3B_TARGET_HASH_MISMATCH: live target hash did not match the extraction request");
            }

            if (requireAcceptedTarget
                && !string.Equals(targetHashBefore, configuration.AcceptedDwgSha256, StringComparison.Ordinal))
            {
                errors.Add("S3B_TARGET_HASH_MISMATCH: target DWG hash did not match server configuration");
            }

            var evidence = BuildEvidence(
                request,
                capture,
                targetHashBefore,
                dbmodBefore,
                dbmodAfter,
                sourceHashBefore,
                sourceHashAfter,
                errors);

            if (evidence.Eligible)
            {
                try
                {
                    _policy.ValidateLiveInspection(evidence, request, targetHashBefore);
                }
                catch (ExactBaseXrefPolicyException exception)
                {
                    errors.Add(exception.Message);
                }
            }

            return new ExactBaseXrefInspectionSnapshot
            {
                Success = errors.Count == 0 && evidence.Eligible,
                DrawingFullPath = activePath,
                Changed = false,
                EntityHandles = Array.Empty<string>(),
                Evidence = evidence,
                Warnings = Array.Empty<string>(),
                Errors = errors.ToArray()
            };
        }
        catch (Exception exception)
        {
            return new ExactBaseXrefInspectionSnapshot
            {
                Success = false,
                DrawingFullPath = activePath,
                Changed = false,
                EntityHandles = Array.Empty<string>(),
                Warnings = Array.Empty<string>(),
                Errors = new[] { exception.Message }
            };
        }
    }

    private static IReadOnlyList<string> ValidatePlanAgainstFreshPreflight(
        ExactBaseXrefExtractionPlan plan,
        ExactBaseXrefLiveInspection preflight,
        ExactBaseXrefExtractionParameters request)
    {
        var errors = new List<string>();
        var planComponents = plan.Components ?? new List<ExactBaseXrefPlanComponent>();
        var liveComponents = preflight.Components ?? new List<ExactBaseXrefLiveComponent>();
        if (!preflight.Eligible)
        {
            errors.Add("S3B_LIVE_PREFLIGHT_REQUIRED: fresh live preflight is not eligible");
        }

        if (planComponents.Count == 0 || planComponents.Count != liveComponents.Count)
        {
            errors.Add("S3B_COMPONENT_SET_MISMATCH: extraction plan must cover the complete fresh inspection set");
        }

        var liveByLogicalId = liveComponents
            .Where(component => !string.IsNullOrWhiteSpace(component.LogicalComponentId))
            .GroupBy(component => component.LogicalComponentId!, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.Single(), StringComparer.Ordinal);
        foreach (var planComponent in planComponents)
        {
            if (planComponent.ComponentType != "BLOCK"
                || planComponent.Provenance != ExactBaseXrefOperationNames.ReusedFromBaseCad
                || planComponent.LogicalComponentId is null
                || !liveByLogicalId.TryGetValue(planComponent.LogicalComponentId, out var liveComponent)
                || liveComponent.ComponentType != "BLOCK"
                || liveComponent.ComponentType != planComponent.ComponentType
                || liveComponent.SourceBlock != planComponent.SourceBlock
                || liveComponent.SourceHandle != planComponent.SourceHandle
                || liveComponent.SourceLayer != planComponent.SourceLayer
                || liveComponent.Provenance != planComponent.Provenance)
            {
                errors.Add("S3B_COMPONENT_IDENTITY_MISMATCH: extraction plan component did not match fresh live inspection");
                continue;
            }

            var transform = planComponent.Transform;
            if (transform is null
                || !double.IsFinite(transform.RotationDegrees)
                || transform.RotationDegrees is < -360 or > 360
                || transform.Translation is null
                || !IsFinitePoint(transform.Translation)
                || !double.IsFinite(transform.UniformScale)
                || transform.UniformScale <= 0)
            {
                errors.Add("S3B_TRANSFORM_POLICY: extraction transform is not local translation, rotation, and positive uniform scale");
            }
        }

        if (planComponents.Select(component => component.SourceHandle)
            .Where(handle => handle is not null)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Count() != planComponents.Count)
        {
            errors.Add("S3B_COMPONENT_IDENTITY_MISMATCH: extraction plan source handles must be unique");
        }

        if (!string.Equals(plan.RunId, request.RunId, StringComparison.Ordinal)
            || !string.Equals(plan.SourceRevision, request.SourceRevision, StringComparison.Ordinal))
        {
            errors.Add("S3B_PLAN_IDENTITY_MISMATCH: extraction plan identity is stale");
        }

        return errors;
    }

    private static IReadOnlyList<ExactBaseXrefExtractionComponentEvidence> BuildExtractionComponents(
        ExactBaseXrefExtractionPlan plan,
        IReadOnlyList<ExactBaseXrefDatabaseExtractedComponent> extracted,
        string sourceHash,
        string? sourceRevision,
        ICollection<string> errors)
    {
        var planByHandle = (plan.Components ?? new List<ExactBaseXrefPlanComponent>())
            .Where(component => component.SourceHandle is not null)
            .ToDictionary(component => component.SourceHandle!, StringComparer.OrdinalIgnoreCase);
        var seenSources = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var seenCandidates = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var result = new List<ExactBaseXrefExtractionComponentEvidence>();
        foreach (var actual in extracted)
        {
            if (actual.SourceHandle is null
                || actual.CandidateHandle is null
                || !IsHexHandle(actual.CandidateHandle)
                || !seenSources.Add(actual.SourceHandle)
                || !seenCandidates.Add(actual.CandidateHandle)
                || !planByHandle.TryGetValue(actual.SourceHandle, out var planComponent))
            {
                errors.Add("S3B_CANDIDATE_MAPPING_INVALID: native candidate mapping is incomplete or not approved");
                continue;
            }

            result.Add(new ExactBaseXrefExtractionComponentEvidence
            {
                CandidateHandle = actual.CandidateHandle,
                LogicalComponentId = planComponent.LogicalComponentId,
                Provenance = planComponent.Provenance,
                SourceBlock = planComponent.SourceBlock,
                SourceHandle = actual.SourceHandle,
                SourceLayer = planComponent.SourceLayer,
                SourceRevision = sourceRevision,
                SourceSha256 = sourceHash,
                Transform = planComponent.Transform
            });
        }

        if (result.Count != planByHandle.Count)
        {
            errors.Add("S3B_CANDIDATE_MAPPING_INCOMPLETE: every approved source component must map to one native candidate handle");
        }

        return result;
    }

    private void CleanupOwnedCandidate(
        string outputPath,
        ExactBaseXrefDatabaseExtractionResult extraction,
        ICollection<string> errors)
    {
        if (!extraction.CandidateCreated || string.IsNullOrWhiteSpace(extraction.CandidateOutputIdentity))
        {
            return;
        }

        try
        {
            if (!_database.DeleteCandidateIfIdentityMatches(
                    outputPath,
                    extraction.CandidateOutputIdentity))
            {
                errors.Add("S3B_CANDIDATE_CLEANUP_FAILED: candidate identity recheck refused cleanup");
            }
        }
        catch (Exception exception)
        {
            errors.Add($"S3B_CANDIDATE_CLEANUP_FAILED: candidate cleanup failed closed: {exception.Message}");
        }
    }

    private static ExactBaseXrefLivePreflightEvidence BuildLivePreflightEvidence(
        ExactBaseXrefLiveInspection evidence)
    {
        var evidenceHash = Convert.ToHexString(
                SHA256.HashData(JsonSerializer.SerializeToUtf8Bytes(evidence)))
            .ToLowerInvariant();
        return new ExactBaseXrefLivePreflightEvidence
        {
            DbmodAfter = evidence.DbmodAfter,
            DbmodBefore = evidence.DbmodBefore,
            Eligible = evidence.Eligible,
            EvidenceSha256 = evidenceHash,
            InspectionId = evidence.InspectionId,
            SourceSha256 = evidence.BaseSource?.Sha256,
            TargetDrawingSha256 = evidence.TargetDrawingSha256,
            Xref = evidence.Xref
        };
    }

    private static bool IsFinitePoint(ExactBaseXrefPoint point) =>
        double.IsFinite(point.X) && double.IsFinite(point.Y) && double.IsFinite(point.Z);

    private static bool IsHexHandle(string value) =>
        value.Length is > 0 and <= 64
        && value.All(character => char.IsAsciiHexDigit(character));

    private static bool IsSha256(string? value) =>
        value is { Length: 64 }
        && value.All(character => character is >= '0' and <= '9' or >= 'a' and <= 'f');

    private ExactBaseXrefLiveInspection BuildEvidence(
        ExactBaseXrefInspectionParameters request,
        ExactBaseXrefDatabaseCapture capture,
        string targetHash,
        int dbmodBefore,
        int dbmodAfter,
        string sourceHashBefore,
        string sourceHashAfter,
        ICollection<string> errors)
    {
        var expectations = request.InspectionExpectations
            ?? throw new ExactBaseXrefPolicyException(
                ExactBaseXrefPolicy.RequestInvalidCode,
                "inspection expectations are required");
        var identity = new List<ExactBaseXrefIdentityObservation>
        {
            Identity("vehicle", capture.Vehicle, expectations.Identity?.Vehicle),
            Identity("model", capture.Model, expectations.Identity?.Model)
        };
        if (identity.Any(observation => observation.Status != Pass))
        {
            errors.Add("S3B_SOURCE_IDENTITY_MISMATCH: live vehicle/model identity did not match expectations");
        }
        var dimensions = BuildDimensions(expectations, capture, errors);
        var components = BuildComponents(expectations, capture, errors);
        var xrefMatches = string.Equals(
            capture.XrefName,
            expectations.Xref?.Name,
            StringComparison.Ordinal);
        var xrefValid = capture.IsExternalReference && capture.IsReadOnly && xrefMatches;
        if (!xrefValid)
        {
            errors.Add("S3B_XREF_NOT_READ_ONLY: named source must be an external read-only reference");
        }

        var changed = !string.Equals(sourceHashBefore, sourceHashAfter, StringComparison.Ordinal)
            || dbmodBefore != dbmodAfter;
        var eligible = errors.Count == 0
            && changed == false
            && identity.All(observation => observation.Status == Pass)
            && dimensions.All(dimension => dimension.Status == Pass)
            && xrefValid
            && components.Count == (expectations.Components?.Count ?? 0);

        return new ExactBaseXrefLiveInspection
        {
            BaseSource = new ExactBaseXrefPlanSource
            {
                RelativePath = Path.GetFileName(_policy.Configuration.ExactBaseSourcePath),
                Revision = _policy.Configuration.ExactBaseSourceRevision,
                Sha256 = sourceHashBefore,
                SourceId = expectations.Source?.SourceId
            },
            SchemaVersion = LiveSchemaVersion,
            CaptureTimestamp = EnsureUtc(_clock()),
            Changed = changed,
            DbmodBefore = dbmodBefore,
            DbmodAfter = dbmodAfter,
            Eligible = eligible,
            Components = components,
            Conflicts = errors.ToList(),
            CriticalDimensions = dimensions,
            IdentityObservations = identity,
            InspectionId = "inspection-" + Guid.NewGuid().ToString("N"),
            RequestId = "reader-" + Guid.NewGuid().ToString("N"),
            RunId = request.RunId,
            TargetDrawingSha256 = targetHash,
            Warnings = new List<string>(),
            Xref = new ExactBaseXrefLiveXref
            {
                Name = capture.XrefName,
                ReadOnly = capture.IsReadOnly,
                Status = xrefValid ? "INSPECTED" : Fail
            }
        };
    }

    private static ExactBaseXrefIdentityObservation Identity(
        string field,
        string? observed,
        string? target) => new()
        {
            Field = field,
            Observed = observed,
            Target = target,
            Status = string.Equals(observed, target, StringComparison.Ordinal) ? Pass : Fail
        };

    private static List<ExactBaseXrefLiveDimension> BuildDimensions(
        ExactBaseXrefInspectionExpectations expectations,
        ExactBaseXrefDatabaseCapture capture,
        ICollection<string> errors)
    {
        var observed = capture.CriticalDimensions
            .Where(dimension => !string.IsNullOrWhiteSpace(dimension.Control))
            .GroupBy(dimension => dimension.Control!, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.ToArray(), StringComparer.Ordinal);
        var result = new List<ExactBaseXrefLiveDimension>();
        foreach (var expected in expectations.CriticalDimensions ?? new List<ExactBaseXrefDimensionExpectation>())
        {
            if (expected.Control is null
                || !observed.TryGetValue(expected.Control, out var values)
                || values.Length != 1)
            {
                errors.Add($"S3B_DIMENSION_MISSING: live dimension '{expected.Control}' was not read exactly once");
                continue;
            }

            var actual = values[0];
            var pass = string.Equals(actual.Unit, expected.Unit, StringComparison.Ordinal)
                && Math.Abs(actual.Observed - expected.Target) <= expected.Tolerance;
            if (!pass)
            {
                errors.Add($"S3B_CRITICAL_DIMENSION_MISMATCH: live dimension '{expected.Control}' failed");
            }

            result.Add(new ExactBaseXrefLiveDimension
            {
                Control = expected.Control,
                Target = expected.Target,
                Tolerance = expected.Tolerance,
                Unit = actual.Unit,
                Observed = actual.Observed,
                Status = pass ? Pass : Fail
            });
        }

        return result;
    }

    private static List<ExactBaseXrefLiveComponent> BuildComponents(
        ExactBaseXrefInspectionExpectations expectations,
        ExactBaseXrefDatabaseCapture capture,
        ICollection<string> errors)
    {
        var expectedByHandle = (expectations.Components ?? new List<ExactBaseXrefComponentExpectation>())
            .Where(component => !string.IsNullOrWhiteSpace(component.SourceHandle))
            .ToDictionary(component => component.SourceHandle!, StringComparer.OrdinalIgnoreCase);
        var result = new List<ExactBaseXrefLiveComponent>();
        var seenHandles = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var actual in capture.Components)
        {
            if (actual.SourceHandle is null
                || !seenHandles.Add(actual.SourceHandle)
                || !expectedByHandle.TryGetValue(actual.SourceHandle, out var expected))
            {
                errors.Add("S3B_COMPONENT_IDENTITY_MISMATCH: live component was not an approved named source component");
                continue;
            }

            var matches = string.Equals(actual.ComponentType, expected.ComponentType, StringComparison.Ordinal)
                && string.Equals(actual.SourceBlock, expected.SourceBlock, StringComparison.Ordinal)
                && string.Equals(actual.SourceLayer, expected.SourceLayer, StringComparison.Ordinal)
                && actual.Bounding is not null;
            if (!matches)
            {
                errors.Add($"S3B_COMPONENT_IDENTITY_MISMATCH: source handle '{actual.SourceHandle}' did not match the approved component");
            }

            result.Add(new ExactBaseXrefLiveComponent
            {
                ComponentType = actual.ComponentType,
                LogicalComponentId = expected.LogicalComponentId,
                Provenance = expected.Provenance,
                SourceBlock = actual.SourceBlock,
                SourceHandle = actual.SourceHandle,
                SourceLayer = actual.SourceLayer,
                Bounding = actual.Bounding
            });
        }

        if (result.Count != expectedByHandle.Count)
        {
            errors.Add("S3B_COMPONENT_SET_MISMATCH: live inspection did not return exactly the approved named components");
        }

        return result;
    }

    private static string CanonicalActivePath(string? path) =>
        ContractValidator.NormalizeWindowsAbsolutePath(
            path ?? throw new InvalidOperationException("the active AutoCAD drawing has no full path"));

    private static bool SamePath(string? left, string? right) =>
        left is not null
        && right is not null
        && StringComparer.OrdinalIgnoreCase.Equals(
            ContractValidator.NormalizeWindowsAbsolutePath(left),
            ContractValidator.NormalizeWindowsAbsolutePath(right));

    private static DateTimeOffset EnsureUtc(DateTimeOffset value) =>
        value.Offset == TimeSpan.Zero ? value : value.ToUniversalTime();
}

public sealed class AutoCadExactBaseXrefDatabase : IExactBaseXrefDatabase
{
    private readonly Document _document;

    public AutoCadExactBaseXrefDatabase(Document document)
    {
        _document = document ?? throw new ArgumentNullException(nameof(document));
    }

    public string? ActiveDocumentFullPath => _document.Database?.Filename;

    public int ReadDbmod() => Convert.ToInt32(
        AcadApplication.GetSystemVariable("DBMOD"),
        CultureInfo.InvariantCulture);

    public string ComputeSha256(string path)
    {
        using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }

    public ExactBaseXrefDatabaseCapture ReadNamedExternalXref(
        ExactBaseXrefInspectionParameters request)
    {
        var database = _document.Database
            ?? throw new InvalidOperationException("the active AutoCAD document has no database");
        var xrefName = request.InspectionExpectations?.Xref?.Name
            ?? throw new InvalidOperationException("the approved Xref name is missing");
        var expectedHandles = (request.InspectionExpectations.Components ?? new List<ExactBaseXrefComponentExpectation>())
            .Select(component => component.SourceHandle)
            .Where(handle => handle is not null)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);

        using var transaction = database.TransactionManager.StartOpenCloseTransaction();
        var blockTable = (BlockTable)transaction.GetObject(database.BlockTableId, OpenMode.ForRead);
        if (!blockTable.Has(xrefName))
        {
            throw new InvalidOperationException($"approved Xref '{xrefName}' was not found");
        }

        var xref = (BlockTableRecord)transaction.GetObject(blockTable[xrefName], OpenMode.ForRead);
        var components = new List<ExactBaseXrefDatabaseComponent>();
        foreach (ObjectId objectId in xref)
        {
            if (transaction.GetObject(objectId, OpenMode.ForRead, false) is not Entity entity)
            {
                continue;
            }

            var handle = entity.Handle.ToString().ToUpperInvariant();
            if (!expectedHandles.Contains(handle))
            {
                continue;
            }

            Extents3d extents;
            try
            {
                extents = entity.GeometricExtents;
            }
            catch (Exception exception)
            {
                throw new InvalidOperationException(
                    $"source component '{handle}' has no readable geometric bounds",
                    exception);
            }

            components.Add(new ExactBaseXrefDatabaseComponent
            {
                ComponentType = entity is BlockReference ? "BLOCK" : entity.GetType().Name.ToUpperInvariant(),
                SourceBlock = entity is BlockReference blockReference
                    ? blockReference.Name
                    : entity.GetType().Name.ToUpperInvariant(),
                SourceHandle = handle,
                SourceLayer = entity.Layer,
                Bounding = new ExactBaseXrefBounding
                {
                    Min = new ExactBaseXrefPoint
                    {
                        X = extents.MinPoint.X,
                        Y = extents.MinPoint.Y,
                        Z = extents.MinPoint.Z
                    },
                    Max = new ExactBaseXrefPoint
                    {
                        X = extents.MaxPoint.X,
                        Y = extents.MaxPoint.Y,
                        Z = extents.MaxPoint.Z
                    }
                }
            });
        }

        var properties = ReadCustomProperties(database);
        return new ExactBaseXrefDatabaseCapture
        {
            XrefName = xref.Name,
            IsExternalReference = xref.IsFromExternalReference,
            IsReadOnly = !xref.IsWriteEnabled,
            Vehicle = RequiredProperty(properties, "CAD_AGENT_VEHICLE"),
            Model = RequiredProperty(properties, "CAD_AGENT_MODEL"),
            CriticalDimensions = (request.InspectionExpectations.CriticalDimensions ?? new List<ExactBaseXrefDimensionExpectation>())
                .Select(dimension => new ExactBaseXrefDatabaseDimension
                {
                    Control = dimension.Control,
                    Observed = RequiredDoubleProperty(properties, "CAD_AGENT_DIMENSION_" + dimension.Control),
                    Unit = RequiredProperty(properties, "CAD_AGENT_DIMENSION_" + dimension.Control + "_UNIT")
                })
                .ToArray(),
            Components = components
        };
    }

    public ExactBaseXrefDatabaseExtractionResult ExtractApprovedComponents(
        ExactBaseXrefExtractionParameters request,
        IReadOnlyList<ExactBaseXrefPlanComponent> approvedComponents,
        ExactBaseXrefLiveInspection preflight)
    {
        var database = _document.Database
            ?? throw new InvalidOperationException("the active AutoCAD document has no database");
        var outputPath = ContractValidator.NormalizeWindowsAbsolutePath(
            request.CandidateOutputPath
            ?? throw new InvalidOperationException("candidate output path is missing"));
        if (!IsCandidatePathAbsent(outputPath))
        {
            throw new ExactBaseXrefPolicyException(
                ExactBaseXrefPolicy.CandidateOutputExistsCode,
                "candidate output already exists");
        }

        EnsureNoReparsePoints(Path.GetDirectoryName(outputPath)!);
        var created = false;
        string? identity = null;
        try
        {
            if (approvedComponents.Any(component =>
                    component.ComponentType != "BLOCK"
                    || component.Provenance != ExactBaseXrefOperationNames.ReusedFromBaseCad))
            {
                throw new ExactBaseXrefPolicyException(
                    ExactBaseXrefPolicy.SourceIdentityMismatchCode,
                    "only inspected BLOCK components reused from base CAD may be extracted");
            }

            var expectedByHandle = approvedComponents
                .Where(component => component.SourceHandle is not null)
                .ToDictionary(component => component.SourceHandle!, StringComparer.OrdinalIgnoreCase);
            var sourceIds = new ObjectIdCollection();
            var sourceComponents = new Dictionary<ObjectId, ExactBaseXrefPlanComponent>();
            using (var sourceTransaction = database.TransactionManager.StartOpenCloseTransaction())
            {
                var blockTable = (BlockTable)sourceTransaction.GetObject(
                    database.BlockTableId,
                    OpenMode.ForRead);
                var xrefName = request.InspectionExpectations?.Xref?.Name
                    ?? throw new InvalidOperationException("approved Xref name is missing");
                if (!blockTable.Has(xrefName))
                {
                    throw new InvalidOperationException($"approved Xref '{xrefName}' was not found");
                }

                var xref = (BlockTableRecord)sourceTransaction.GetObject(
                    blockTable[xrefName],
                    OpenMode.ForRead);
                if (!xref.IsFromExternalReference || xref.IsWriteEnabled)
                {
                    throw new ExactBaseXrefPolicyException(
                        ExactBaseXrefPolicy.SourceIdentityMismatchCode,
                        "the source Xref is not an external read-only reference");
                }

                foreach (ObjectId objectId in xref)
                {
                    if (sourceTransaction.GetObject(objectId, OpenMode.ForRead, false)
                        is not BlockReference blockReference)
                    {
                        continue;
                    }

                    var handle = blockReference.Handle.ToString().ToUpperInvariant();
                    if (!expectedByHandle.TryGetValue(handle, out var component))
                    {
                        continue;
                    }

                    if (!string.Equals(blockReference.Layer, component.SourceLayer, StringComparison.Ordinal)
                        || !string.Equals(blockReference.Name, component.SourceBlock, StringComparison.Ordinal))
                    {
                        throw new ExactBaseXrefPolicyException(
                            ExactBaseXrefPolicy.SourceIdentityMismatchCode,
                            $"source component '{handle}' did not match approved block/layer identity");
                    }

                    sourceIds.Add(objectId);
                    sourceComponents[objectId] = component;
                }
            }

            if (sourceComponents.Count != expectedByHandle.Count)
            {
                throw new ExactBaseXrefPolicyException(
                    ExactBaseXrefPolicy.SourceIdentityMismatchCode,
                    "not every approved source component was found in the inspected Xref");
            }

            using var candidate = new Database(true, true);
            var idMapping = new IdMapping();
            database.WblockCloneObjects(
                sourceIds,
                candidate.CurrentSpaceId,
                idMapping,
                DuplicateRecordCloning.Ignore,
                deferTranslation: false);

            var extracted = new List<ExactBaseXrefDatabaseExtractedComponent>();
            using (var candidateTransaction = candidate.TransactionManager.StartOpenCloseTransaction())
            {
                foreach (var source in sourceComponents)
                {
                    if (!idMapping.Contains(source.Key))
                    {
                        throw new InvalidOperationException(
                            $"native clone did not return a candidate mapping for source '{source.Value.SourceHandle}'");
                    }

                    var destinationId = idMapping[source.Key].Value;
                    if (candidateTransaction.GetObject(destinationId, OpenMode.ForWrite, false)
                        is not Entity destination)
                    {
                        throw new InvalidOperationException(
                            $"native clone destination for source '{source.Value.SourceHandle}' is not an entity");
                    }

                    destination.TransformBy(CreateLocalTransform(source.Value.Transform));
                    extracted.Add(new ExactBaseXrefDatabaseExtractedComponent
                    {
                        SourceHandle = source.Value.SourceHandle,
                        CandidateHandle = destination.Handle.ToString().ToUpperInvariant()
                    });
                }

                candidateTransaction.Commit();
            }

            candidate.SaveAs(outputPath, DwgVersion.Current);
            created = true;
            identity = CaptureCandidateIdentity(outputPath);
            return new ExactBaseXrefDatabaseExtractionResult
            {
                CandidateCreated = true,
                CandidateOutputIdentity = identity,
                CandidateInputSha256 = ComputeSha256(database.Filename),
                CandidateOutputSha256 = ComputeSha256(outputPath),
                SavePerformed = true,
                Components = extracted
            };
        }
        catch
        {
            if (created && identity is not null)
            {
                _ = DeleteCandidateIfIdentityMatches(outputPath, identity);
            }

            throw;
        }
    }

    public bool IsCandidatePathAbsent(string path) =>
        !File.Exists(path) && !Directory.Exists(path);

    public string CaptureCandidateIdentity(string path)
    {
        EnsureNoReparsePoints(path);
        var info = new FileInfo(path);
        if (!info.Exists)
        {
            throw new FileNotFoundException("candidate output was not found after save", path);
        }

        return string.Join(
            "|",
            info.FullName,
            info.Length.ToString(CultureInfo.InvariantCulture),
            info.CreationTimeUtc.Ticks.ToString(CultureInfo.InvariantCulture),
            info.LastWriteTimeUtc.Ticks.ToString(CultureInfo.InvariantCulture));
    }

    public bool DeleteCandidateIfIdentityMatches(string path, string identity)
    {
        if (!File.Exists(path) || Directory.Exists(path))
        {
            return true;
        }

        try
        {
            EnsureNoReparsePoints(path);
            if (!string.Equals(CaptureCandidateIdentity(path), identity, StringComparison.Ordinal))
            {
                return false;
            }

            File.Delete(path);
            return !File.Exists(path);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return false;
        }
    }

    private static Matrix3d CreateLocalTransform(ExactBaseXrefTransform? transform)
    {
        if (transform is null
            || transform.Translation is null
            || !double.IsFinite(transform.RotationDegrees)
            || transform.RotationDegrees is < -360 or > 360
            || !double.IsFinite(transform.UniformScale)
            || transform.UniformScale <= 0
            || !double.IsFinite(transform.Translation.X)
            || !double.IsFinite(transform.Translation.Y)
            || !double.IsFinite(transform.Translation.Z))
        {
            throw new ExactBaseXrefPolicyException(
                ExactBaseXrefPolicy.TransformPolicyCode,
                "only finite local translation, rotation, and positive uniform scale are allowed");
        }

        var translation = new Vector3d(
            transform.Translation.X,
            transform.Translation.Y,
            transform.Translation.Z);
        var rotation = Matrix3d.Rotation(
            transform.RotationDegrees * Math.PI / 180.0,
            Vector3d.ZAxis,
            Point3d.Origin);
        var scale = Matrix3d.Scaling(transform.UniformScale, Point3d.Origin);
        return scale.PostMultiplyBy(rotation)
            .PostMultiplyBy(Matrix3d.Displacement(translation));
    }

    private static void EnsureNoReparsePoints(string path)
    {
        var fullPath = ContractValidator.NormalizeWindowsAbsolutePath(path);
        var current = new DirectoryInfo(
            File.Exists(fullPath) ? Path.GetDirectoryName(fullPath)! : fullPath);
        while (current is not null)
        {
            if (current.Exists && current.Attributes.HasFlag(FileAttributes.ReparsePoint))
            {
                throw new ExactBaseXrefPolicyException(
                    ExactBaseXrefPolicy.ReparsePointCode,
                    $"candidate path contains a reparse point: {current.FullName}");
            }

            current = current.Parent;
        }
    }

    private static IReadOnlyDictionary<string, string> ReadCustomProperties(Database database)
    {
        var properties = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var customProperties = database.SummaryInfo.CustomProperties;
        while (customProperties.MoveNext())
        {
            var key = Convert.ToString(customProperties.Key, CultureInfo.InvariantCulture);
            if (!string.IsNullOrWhiteSpace(key))
            {
                properties[key] = Convert.ToString(customProperties.Value, CultureInfo.InvariantCulture) ?? string.Empty;
            }
        }

        return properties;
    }

    private static string RequiredProperty(IReadOnlyDictionary<string, string> properties, string key) =>
        properties.TryGetValue(key, out var value) && !string.IsNullOrWhiteSpace(value)
            ? value
            : throw new InvalidOperationException($"live AutoCAD property '{key}' is missing");

    private static double RequiredDoubleProperty(IReadOnlyDictionary<string, string> properties, string key) =>
        double.TryParse(
            RequiredProperty(properties, key),
            NumberStyles.Float,
            CultureInfo.InvariantCulture,
            out var value)
            && double.IsFinite(value)
                ? value
                : throw new InvalidOperationException($"live AutoCAD property '{key}' is not a finite number");
}
