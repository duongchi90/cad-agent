using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using CadAgent.AutoCAD2027.Ipc;

namespace CadAgent.AutoCAD2027.Drawing;

public sealed class StandaloneDwgComponentPolicyException : InvalidOperationException
{
    public StandaloneDwgComponentPolicyException(string code, string message)
        : base($"{code}: {message}")
    {
        Code = code;
    }

    public string Code { get; }
}

public sealed class StandaloneDwgComponentPolicy
{
    public const string RequestInvalidCode = "S3C_REQUEST_INVALID";
    public const string XrefOnlySourceContractCode = "S3C_XREF_ONLY_SOURCE_CONTRACT";
    public const string ExactHandlesRequiredCode = "S3C_EXACT_HANDLES_REQUIRED";
    public const string SourceHashOrDbmodDriftCode = "S3C_SOURCE_HASH_OR_DBMOD_DRIFT";
    public const string SourceReadOnlyRequiredCode = "S3C_SOURCE_READ_ONLY_REQUIRED";
    public const string SourceFreshnessMismatchCode = "S3C_SOURCE_FRESHNESS_MISMATCH";
    public const string SourceIdentityMismatchCode = "S3C_SOURCE_IDENTITY_MISMATCH";
    public const string CandidateBaseCode = "S3C_EMPTY_CANDIDATE_REQUIRED";
    public const string CandidatePathUnsafeCode = "S3C_CANDIDATE_PATH_UNSAFE";
    public const string CandidateOutputExistsCode = "S3C_CANDIDATE_OUTPUT_EXISTS";
    public const string ForbiddenWriteTargetCode = "S3C_FORBIDDEN_WRITE_TARGET";
    public const string CandidateOutputInvalidCode = "S3C_CANDIDATE_OUTPUT_INVALID";
    public const string CandidateOutputNotReopenableCode = "S3C_OUTPUT_NOT_REOPENABLE";
    public const string MappingInvalidCode = "S3C_MAPPING_INVALID";
    public const string CleanupFailedCode = "S3C_CLEANUP_FAILED";
    public const string TransformPolicyCode = "S3C_TRANSFORM_POLICY";

    private const string InspectionSchemaVersion = "standalone-dwg-component-inspection-1.0";
    private const string ExtractionSchemaVersion = "standalone-dwg-component-extraction-1.0";
    private const string EmptyNewDatabase = "EMPTY_NEW_DATABASE";
    private const string TransformPolicy = "LOCAL_TRANSLATION_ROTATION_UNIFORM_SCALE_ONLY";

    private static readonly Regex IdentifierPattern = new(
        "^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$",
        RegexOptions.CultureInvariant | RegexOptions.Compiled);
    private static readonly Regex HashPattern = new(
        "^[0-9a-f]{64}$",
        RegexOptions.CultureInvariant | RegexOptions.Compiled);
    private static readonly Regex HandlePattern = new(
        "^[0-9A-F]+$",
        RegexOptions.CultureInvariant | RegexOptions.Compiled);

    private readonly string _disposableRoot;

    public StandaloneDwgComponentPolicy(string disposableRoot)
    {
        if (!ContractValidator.TryNormalizeWindowsAbsolutePath(disposableRoot, out var normalized)
            || string.IsNullOrWhiteSpace(normalized))
        {
            throw new StandaloneDwgComponentPolicyException(
                CandidatePathUnsafeCode,
                "disposable root must be an absolute Windows path");
        }

        _disposableRoot = normalized.TrimEnd('\\');
    }

    public string DisposableRoot => _disposableRoot;

    public static string OpaqueCandidateFileId(string rawIdentity)
    {
        if (string.IsNullOrWhiteSpace(rawIdentity))
        {
            throw new ArgumentException("raw candidate identity is required", nameof(rawIdentity));
        }

        var digest = Convert.ToHexString(
            SHA256.HashData(Encoding.UTF8.GetBytes(rawIdentity)))
            .ToLowerInvariant();
        return "candidate-file-" + digest;
    }

    public void ValidateInspectionRequest(StandaloneDwgComponentInspectionRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        if (request.SchemaVersion != InspectionSchemaVersion
            || !IsIdentifier(request.RequestId)
            || !IsIdentifier(request.RunId)
            || !IsLowerSha256(request.SourceDrawingSha256)
            || !IsLowerSha256(request.SourceSetupAuditSha256)
            || request.ExpectedDbmod < 0
            || request.Approval is not null
            || request.SelectionGroups is null
            || request.SelectionGroups.Count == 0)
        {
            Fail(RequestInvalidCode, "inspection request is not a closed standalone packet");
        }

        var sourcePath = RequireDwgPath(request.SourceDrawingPath, SourceIdentityMismatchCode);
        EnsureRegularNonReparseFile(sourcePath, SourceIdentityMismatchCode);

        var groups = new HashSet<string>(StringComparer.Ordinal);
        var handles = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var group in request.SelectionGroups!)
        {
            if (!IsIdentifier(group.GroupId)
                || !IsIdentifier(group.LogicalComponentId)
                || group.SourceHandles is null
                || group.SourceHandles.Count == 0
                || group.ExpectedEntityTypes is null
                || group.ExpectedEntityTypes.Count == 0
                || group.SourceLayerExpectations is null
                || group.SourceLayerExpectations.Count == 0
                || !groups.Add(group.GroupId!))
            {
                Fail(ExactHandlesRequiredCode, "selection groups and explicit handles are required");
            }

            foreach (var rawHandle in group.SourceHandles!)
            {
                var handle = NormalizeHandle(rawHandle);
                if (!handles.Add(handle))
                {
                    Fail(ExactHandlesRequiredCode, $"source handle '{handle}' is selected more than once");
                }
            }
        }
    }

    public string NormalizeSourcePath(StandaloneDwgComponentInspectionRequest request)
    {
        ValidateInspectionRequest(request);
        return ContractValidator.NormalizeWindowsAbsolutePath(request.SourceDrawingPath!);
    }

    public void ValidateInspectionSnapshot(
        StandaloneDwgComponentInspectionRequest request,
        StandaloneDwgComponentInspectionSnapshot snapshot)
    {
        ValidateInspectionRequest(request);
        ArgumentNullException.ThrowIfNull(snapshot);
        var expectedPath = ContractValidator.NormalizeWindowsAbsolutePath(request.SourceDrawingPath!);
        if (!string.Equals(
                expectedPath,
                NormalizePath(snapshot.DrawingFullPath),
                StringComparison.OrdinalIgnoreCase))
        {
            Fail(SourceIdentityMismatchCode, "inspection path does not match the approved source");
        }

        if (snapshot.IsXrefSource)
        {
            Fail(XrefOnlySourceContractCode, "standalone source must not be treated as an Xref");
        }

        if (!snapshot.ReadOnly
            || snapshot.Changed
            || !snapshot.Eligible
            || !string.Equals(snapshot.SourceSha256Before, request.SourceDrawingSha256, StringComparison.Ordinal)
            || !string.Equals(snapshot.SourceSha256After, request.SourceDrawingSha256, StringComparison.Ordinal)
            || snapshot.SourceSha256Before != snapshot.SourceSha256After
            || snapshot.DbmodBefore != request.ExpectedDbmod
            || snapshot.DbmodAfter != request.ExpectedDbmod
            || snapshot.DbmodBefore != snapshot.DbmodAfter)
        {
            Fail(SourceHashOrDbmodDriftCode, "source hash or DBMOD changed during read-only inspection");
        }

        var expected = request.SelectionGroups
            .SelectMany(group => group.SourceHandles.Select(handle => (
                Handle: NormalizeHandle(handle),
                Group: group)))
            .ToDictionary(item => item.Handle, item => item.Group, StringComparer.OrdinalIgnoreCase);
        if (snapshot.Entities is null
            || snapshot.Entities.Count != expected.Count)
        {
            Fail(ExactHandlesRequiredCode, "inspection did not return exactly the requested handles");
        }

        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var entity in snapshot.Entities!)
        {
            var handle = NormalizeHandle(entity.SourceHandle);
            if (!seen.Add(handle))
            {
                Fail(ExactHandlesRequiredCode, "inspection returned an unapproved or duplicate handle");
            }

            if (!expected.TryGetValue(handle, out var group))
            {
                Fail(ExactHandlesRequiredCode, "inspection returned an unapproved or duplicate handle");
            }

            if (string.IsNullOrWhiteSpace(entity.EntityType)
                || !group!.ExpectedEntityTypes!.Contains(entity.EntityType, StringComparer.Ordinal)
                || string.IsNullOrWhiteSpace(entity.Layer)
                || !group.SourceLayerExpectations!.Contains(entity.Layer, StringComparer.Ordinal)
                || !HasFiniteBounds(entity.Bounds))
            {
                Fail(SourceIdentityMismatchCode, $"source handle '{handle}' did not match its approved identity");
            }
        }

        if (!seen.SetEquals(expected.Keys))
        {
            Fail(ExactHandlesRequiredCode, "inspection omitted an explicitly approved handle");
        }
    }

    public string NormalizeCandidateOutputPath(
        StandaloneDwgComponentExtractionPlan plan,
        IStandaloneDwgComponentDatabase database,
        string? sourcePath = null)
    {
        ValidateExtractionPlan(plan);
        var outputPath = RequireDwgPath(plan.CandidateOutputPath, CandidatePathUnsafeCode);
        EnsureNoReparsePoints(outputPath);
        if (!IsUnderRoot(outputPath)
            || !database.IsCandidatePathAbsent(outputPath))
        {
            Fail(
                database.IsCandidatePathAbsent(outputPath)
                    ? CandidatePathUnsafeCode
                    : CandidateOutputExistsCode,
                "candidate output must be an absent path under the disposable root");
        }

        if (sourcePath is not null
            && SamePath(outputPath, ContractValidator.NormalizeWindowsAbsolutePath(sourcePath)))
        {
            Fail(SourceIdentityMismatchCode, "candidate output aliases the source");
        }

        return outputPath;
    }

    public void ValidateExtractionPlan(StandaloneDwgComponentExtractionPlan plan)
    {
        ArgumentNullException.ThrowIfNull(plan);
        if (plan.SchemaVersion != ExtractionSchemaVersion
            || !IsIdentifier(plan.PlanId)
            || !IsIdentifier(plan.RequestId)
            || !IsIdentifier(plan.RunId)
            || !IsIdentifier(plan.InspectionId)
            || !IsLowerSha256(plan.InspectionSha256)
            || !IsLowerSha256(plan.SourceDrawingSha256)
            || plan.CandidateBaseModel != EmptyNewDatabase
            || plan.TransformPolicy != TransformPolicy
            || plan.Components is null
            || plan.Components.Count == 0
            || plan.Approval is null
            || plan.Approval.Status != "APPROVED"
            || !IsIdentifier(plan.Approval.Reference))
        {
            Fail(RequestInvalidCode, "extraction plan is not a closed approved packet");
        }

        _ = RequireDwgPath(plan.CandidateOutputPath, CandidatePathUnsafeCode);
        var groups = new HashSet<string>(StringComparer.Ordinal);
        var handles = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var component in plan.Components!)
        {
            if (!IsIdentifier(component.GroupId)
                || !IsIdentifier(component.LogicalComponentId)
                || component.SourceHandles is null
                || component.SourceHandles.Count == 0
                || !groups.Add(component.GroupId!)
                || component.Transform is null
                || component.Transform.Translation is null
                || !double.IsFinite(component.Transform.RotationDegrees)
                || component.Transform.RotationDegrees is < -360 or > 360
                || !double.IsFinite(component.Transform.UniformScale)
                || component.Transform.UniformScale <= 0
                || !IsFinite(component.Transform.Translation))
            {
                Fail(TransformPolicyCode, "only finite local transforms with positive uniform scale are allowed");
            }

            foreach (var rawHandle in component.SourceHandles!)
            {
                if (!handles.Add(NormalizeHandle(rawHandle)))
                {
                    Fail(ExactHandlesRequiredCode, "a source handle is planned more than once");
                }
            }
        }
    }

    public void ValidateExtractionSnapshot(
        StandaloneDwgComponentExtractionPlan plan,
        StandaloneDwgComponentCandidateSnapshot snapshot)
    {
        ValidateExtractionPlan(plan);
        ArgumentNullException.ThrowIfNull(snapshot);
        var expectedOutput = ContractValidator.NormalizeWindowsAbsolutePath(plan.CandidateOutputPath!);
        if (!string.Equals(
                expectedOutput,
                NormalizePath(snapshot.CandidateOutputPath),
                StringComparison.OrdinalIgnoreCase))
        {
            Fail(ForbiddenWriteTargetCode, "candidate serialization targeted a path other than the approved output");
        }

        if (!snapshot.Reopenable)
        {
            Fail(CandidateOutputNotReopenableCode, "candidate output could not be reopened and hash-checked");
        }

        if (!snapshot.CandidateCreated
            || snapshot.SourceMutated
            || !snapshot.SavePerformed
            || string.IsNullOrWhiteSpace(snapshot.CandidateOutputIdentity)
            || !IsLowerSha256(snapshot.CandidateOutputSha256)
            || !IsLowerSha256(snapshot.SourceSha256Before)
            || !IsLowerSha256(snapshot.SourceSha256After)
            || snapshot.SourceSha256Before != plan.SourceDrawingSha256
            || snapshot.SourceSha256Before != snapshot.SourceSha256After
            || snapshot.SourceDbmodBefore != snapshot.SourceDbmodAfter)
        {
            Fail(CandidateOutputInvalidCode, "candidate output is not a complete source-safe serialization");
        }

        var expectedHandles = plan.Components
            .SelectMany(component => component.SourceHandles)
            .Select(NormalizeHandle)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
        var sourceHandles = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var candidateHandles = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        if (snapshot.Mappings is null || snapshot.Mappings.Count != expectedHandles.Count)
        {
            Fail(MappingInvalidCode, "candidate mappings do not cover the approved selection");
        }

        foreach (var mapping in snapshot.Mappings!)
        {
            var source = NormalizeHandle(mapping.SourceHandle);
            var candidate = NormalizeHandle(mapping.CandidateHandle);
            if (!sourceHandles.Add(source)
                || !candidateHandles.Add(candidate)
                || !expectedHandles.Contains(source))
            {
                Fail(MappingInvalidCode, "candidate mappings must be one-to-one and approved");
            }
        }

        if (!sourceHandles.SetEquals(expectedHandles))
        {
            Fail(MappingInvalidCode, "candidate mappings omit an approved source handle");
        }
    }

    public static string ComputeSha256(string path)
    {
        using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }

    public static string NormalizeHandle(string? rawHandle)
    {
        if (string.IsNullOrWhiteSpace(rawHandle)
            || !HandlePattern.IsMatch(rawHandle))
        {
            Fail(ExactHandlesRequiredCode, "source and candidate handles must be explicit hexadecimal identifiers");
        }

        return rawHandle!.ToUpperInvariant();
    }

    private bool IsUnderRoot(string path)
    {
        var normalized = ContractValidator.NormalizeWindowsAbsolutePath(path).TrimEnd('\\');
        return normalized.StartsWith(_disposableRoot + "\\", StringComparison.OrdinalIgnoreCase);
    }

    private static string RequireDwgPath(string? path, string code)
    {
        if (!ContractValidator.TryNormalizeWindowsAbsolutePath(path, out var normalized)
            || !normalized.EndsWith(".dwg", StringComparison.OrdinalIgnoreCase))
        {
            Fail(code, "path must be an absolute .dwg path");
        }

        return normalized;
    }

    private static string NormalizePath(string? path) =>
        path is null ? string.Empty : ContractValidator.NormalizeWindowsAbsolutePath(path);

    private static bool SamePath(string left, string right) =>
        string.Equals(left, right, StringComparison.OrdinalIgnoreCase);

    private static bool IsIdentifier(string? value) =>
        value is not null && IdentifierPattern.IsMatch(value);

    private static bool IsLowerSha256(string? value) =>
        value is not null && HashPattern.IsMatch(value);

    private static bool IsFinite(StandaloneDwgComponentPoint point) =>
        double.IsFinite(point.X) && double.IsFinite(point.Y) && double.IsFinite(point.Z);

    private static bool HasFiniteBounds(StandaloneDwgComponentBounds? bounds) =>
        bounds?.Min is not null
        && bounds.Max is not null
        && IsFinite(bounds.Min)
        && IsFinite(bounds.Max);

    private static void EnsureRegularNonReparseFile(string path, string code)
    {
        if (!File.Exists(path)
            || Directory.Exists(path)
            || new FileInfo(path).Attributes.HasFlag(FileAttributes.ReparsePoint))
        {
            Fail(code, "source must be an existing regular non-reparse file");
        }
    }

    private static void EnsureNoReparsePoints(string path)
    {
        var current = new DirectoryInfo(
            File.Exists(path) ? Path.GetDirectoryName(path)! : path);
        while (current is not null)
        {
            if (current.Exists && current.Attributes.HasFlag(FileAttributes.ReparsePoint))
            {
                Fail(CandidatePathUnsafeCode, $"candidate path contains a reparse point: {current.FullName}");
            }

            current = current.Parent;
        }
    }

    private static void Fail(string code, string message) =>
        throw new StandaloneDwgComponentPolicyException(code, message);
}
