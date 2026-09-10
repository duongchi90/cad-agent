using System.Globalization;
using System.Security.Cryptography;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using CadAgent.AutoCAD2027.Ipc;
using AcadApplication = Autodesk.AutoCAD.ApplicationServices.Application;

namespace CadAgent.AutoCAD2027.Drawing;

public sealed class AutoCadStandaloneDwgComponentReader
{
    private readonly IStandaloneDwgComponentDatabase _database;
    private readonly StandaloneDwgComponentPolicy _policy;

    public AutoCadStandaloneDwgComponentReader(
        IStandaloneDwgComponentDatabase database,
        StandaloneDwgComponentPolicy policy)
    {
        _database = database ?? throw new ArgumentNullException(nameof(database));
        _policy = policy ?? throw new ArgumentNullException(nameof(policy));
    }

    public StandaloneDwgComponentInspectionSnapshot Inspect(
        StandaloneDwgComponentInspectionRequest request)
    {
        try
        {
            _policy.ValidateInspectionRequest(request);
            EnsureActiveSource(request.SourceDrawingPath);
            EnsureSourceReadOnly();
            var snapshot = _database.ReadSelectedEntities(request);
            if (!snapshot.Success)
            {
                return snapshot;
            }

            _policy.ValidateInspectionSnapshot(request, snapshot);
            return snapshot;
        }
        catch (Exception exception)
        {
            return StandaloneDwgComponentInspectionSnapshot.Failure(
                _database.ActiveDocumentFullPath,
                new[] { FormatError(exception) });
        }
    }

    public StandaloneDwgComponentExtractionSnapshot Extract(
        StandaloneDwgComponentExtractionPlan plan)
    {
        StandaloneDwgComponentCandidateSnapshot? snapshot = null;
        string? outputPath = null;
        var errors = new List<string>();
        try
        {
            _policy.ValidateExtractionPlan(plan);
            EnsureSourceReadOnly();
            EnsureSourceFresh(plan.SourceDrawingSha256);
            outputPath = _policy.NormalizeCandidateOutputPath(
                plan,
                _database,
                _database.ActiveDocumentFullPath);
            EnsureActiveSourceIsNotOutput(outputPath);
            snapshot = _database.ExtractToNewCandidate(plan);
            _policy.ValidateExtractionSnapshot(plan, snapshot);
            return new StandaloneDwgComponentExtractionSnapshot
            {
                Success = true,
                Changed = true,
                EntityHandles = snapshot.Mappings
                    .Select(mapping => StandaloneDwgComponentPolicy.NormalizeHandle(mapping.CandidateHandle))
                    .OrderBy(handle => handle, StringComparer.Ordinal)
                    .ToArray(),
                Evidence = snapshot,
                Warnings = Array.Empty<string>(),
                Errors = Array.Empty<string>()
            };
        }
        catch (Exception exception)
        {
            errors.Add(FormatError(exception));
            if (snapshot?.CandidateCreated == true
                && !string.IsNullOrWhiteSpace(snapshot.CandidateOutputIdentity)
                && !string.IsNullOrWhiteSpace(outputPath))
            {
                try
                {
                    if (!_database.DeleteCandidateIfIdentityMatches(
                            outputPath,
                            snapshot.CandidateOutputIdentity))
                    {
                        errors.Add(
                            $"{StandaloneDwgComponentPolicy.CleanupFailedCode}: candidate identity recheck refused cleanup");
                    }
                }
                catch (Exception cleanupException)
                {
                    errors.Add(
                        $"{StandaloneDwgComponentPolicy.CleanupFailedCode}: {cleanupException.Message}");
                }
            }

            return StandaloneDwgComponentExtractionSnapshot.Failure(errors, snapshot);
        }
    }

    private void EnsureActiveSource(string? requestedSourcePath)
    {
        var requested = ContractValidator.NormalizeWindowsAbsolutePath(
            requestedSourcePath ?? throw new InvalidOperationException(
                $"{StandaloneDwgComponentPolicy.SourceIdentityMismatchCode}: source path is missing"));
        var active = ContractValidator.NormalizeWindowsAbsolutePath(
            _database.ActiveDocumentFullPath ?? throw new InvalidOperationException(
                $"{StandaloneDwgComponentPolicy.SourceIdentityMismatchCode}: active source path is missing"));
        if (!string.Equals(requested, active, StringComparison.OrdinalIgnoreCase))
        {
            throw new StandaloneDwgComponentPolicyException(
                StandaloneDwgComponentPolicy.SourceIdentityMismatchCode,
                "active document is not the approved standalone source");
        }
    }

    private void EnsureActiveSourceIsNotOutput(string outputPath)
    {
        var active = ContractValidator.NormalizeWindowsAbsolutePath(
            _database.ActiveDocumentFullPath ?? throw new InvalidOperationException(
                $"{StandaloneDwgComponentPolicy.SourceIdentityMismatchCode}: active source path is missing"));
        if (string.Equals(active, outputPath, StringComparison.OrdinalIgnoreCase))
        {
            throw new StandaloneDwgComponentPolicyException(
                StandaloneDwgComponentPolicy.ForbiddenWriteTargetCode,
                "candidate serialization cannot target the source document");
        }
    }

    private void EnsureSourceReadOnly()
    {
        if (_database.IsSourceReadOnly != true)
        {
            throw new StandaloneDwgComponentPolicyException(
                StandaloneDwgComponentPolicy.SourceReadOnlyRequiredCode,
                "source read-only custody was not positively verified");
        }
    }

    private void EnsureSourceFresh(string? expectedSourceSha256)
    {
        var actualSourceSha256 = _database.ComputeSourceSha256();
        if (!string.Equals(actualSourceSha256, expectedSourceSha256, StringComparison.Ordinal))
        {
            throw new StandaloneDwgComponentPolicyException(
                StandaloneDwgComponentPolicy.SourceFreshnessMismatchCode,
                "source hash does not match the approved extraction plan before candidate creation");
        }
    }

    private static string FormatError(Exception exception) => exception switch
    {
        StandaloneDwgComponentPolicyException policyException =>
            $"{policyException.Code}: {policyException.Message}",
        _ => exception.Message
    };
}

public sealed class AutoCadStandaloneDwgComponentDatabase : IStandaloneDwgComponentDatabase
{
    private readonly Document _document;

    public AutoCadStandaloneDwgComponentDatabase(Document document)
    {
        _document = document ?? throw new ArgumentNullException(nameof(document));
    }

    public string? ActiveDocumentFullPath => _document.Database?.Filename;

    public bool? IsSourceReadOnly
    {
        get
        {
            try
            {
                return _document.IsReadOnly;
            }
            catch
            {
                return null;
            }
        }
    }

    public string ComputeSourceSha256()
    {
        RequireReadOnlySource();
        var sourcePath = ContractValidator.NormalizeWindowsAbsolutePath(
            _document.Database?.Filename
                ?? throw new InvalidOperationException("source drawing has no path"));
        return StandaloneDwgComponentPolicy.ComputeSha256(sourcePath);
    }

    internal static string ContractEntityType(Entity entity) =>
        entity is BlockReference
            ? StandaloneDwgComponentEntityTypeContract.Insert
            : StandaloneDwgComponentEntityTypeContract.FromNativeTypeName(entity.GetType().Name);

    public StandaloneDwgComponentInspectionSnapshot ReadSelectedEntities(
        StandaloneDwgComponentInspectionRequest request)
    {
        var sourceReadOnlyBefore = RequireReadOnlySource();
        var database = _document.Database
            ?? throw new InvalidOperationException("the active AutoCAD document has no database");
        var sourcePath = ContractValidator.NormalizeWindowsAbsolutePath(
            request.SourceDrawingPath ?? throw new InvalidOperationException("source path is missing"));
        var sourceBefore = StandaloneDwgComponentPolicy.ComputeSha256(sourcePath);
        var dbmodBefore = ReadDbmod();
        var entities = new List<StandaloneDwgComponentEntitySnapshot>();

        using (var transaction = database.TransactionManager.StartOpenCloseTransaction())
        {
            foreach (var handleText in request.SelectionGroups.SelectMany(group => group.SourceHandles))
            {
                var handle = StandaloneDwgComponentPolicy.NormalizeHandle(handleText);
                var objectId = database.GetObjectId(
                    false,
                    new Handle(Convert.ToInt64(handle, 16)),
                    0);
                if (objectId.IsNull || objectId.IsErased)
                {
                    throw new InvalidOperationException($"source handle '{handle}' was not found");
                }

                if (transaction.GetObject(objectId, OpenMode.ForRead, false) is not Entity entity)
                {
                    throw new InvalidOperationException($"source handle '{handle}' is not an entity");
                }

                Extents3d extents;
                try
                {
                    extents = entity.GeometricExtents;
                }
                catch (Exception exception)
                {
                    throw new InvalidOperationException(
                        $"source handle '{handle}' has no readable bounds",
                        exception);
                }

                entities.Add(new StandaloneDwgComponentEntitySnapshot
                {
                    SourceHandle = handle,
                    EntityType = ContractEntityType(entity),
                    Layer = entity.Layer,
                    Bounds = Bounds(extents)
                });
            }
        }

        var sourceAfter = StandaloneDwgComponentPolicy.ComputeSha256(sourcePath);
        var dbmodAfter = ReadDbmod();
        var sourceReadOnlyAfter = RequireReadOnlySource();
        return new StandaloneDwgComponentInspectionSnapshot
        {
            Success = true,
            DrawingFullPath = sourcePath,
            Changed = sourceBefore != sourceAfter || dbmodBefore != dbmodAfter,
            ReadOnly = sourceReadOnlyBefore && sourceReadOnlyAfter,
            IsXrefSource = false,
            Eligible = sourceReadOnlyBefore
                && sourceReadOnlyAfter
                && sourceBefore == sourceAfter
                && dbmodBefore == dbmodAfter,
            SourceSha256Before = sourceBefore,
            SourceSha256After = sourceAfter,
            DbmodBefore = dbmodBefore,
            DbmodAfter = dbmodAfter,
            Entities = entities,
            Warnings = Array.Empty<string>(),
            Errors = Array.Empty<string>()
        };
    }

    public StandaloneDwgComponentCandidateSnapshot ExtractToNewCandidate(
        StandaloneDwgComponentExtractionPlan plan)
    {
        RequireReadOnlySource();
        var database = _document.Database
            ?? throw new InvalidOperationException("the active AutoCAD document has no database");
        var sourcePath = ContractValidator.NormalizeWindowsAbsolutePath(
            database.Filename ?? throw new InvalidOperationException("source drawing has no path"));
        var sourceBefore = StandaloneDwgComponentPolicy.ComputeSha256(sourcePath);
        if (!string.Equals(sourceBefore, plan.SourceDrawingSha256, StringComparison.Ordinal))
        {
            throw new StandaloneDwgComponentPolicyException(
                StandaloneDwgComponentPolicy.SourceFreshnessMismatchCode,
                "source hash does not match the approved extraction plan before candidate creation");
        }

        var dbmodBefore = ReadDbmod();
        var outputPath = ContractValidator.NormalizeWindowsAbsolutePath(
            plan.CandidateOutputPath ?? throw new InvalidOperationException("candidate output path is missing"));
        if (!IsCandidatePathAbsent(outputPath))
        {
            throw new StandaloneDwgComponentPolicyException(
                StandaloneDwgComponentPolicy.CandidateOutputExistsCode,
                "candidate output already exists");
        }

        var sourceIds = new ObjectIdCollection();
        var sourceHandles = new List<string>();
        using (var sourceTransaction = database.TransactionManager.StartOpenCloseTransaction())
        {
            foreach (var handleText in plan.Components.SelectMany(component => component.SourceHandles))
            {
                var handle = StandaloneDwgComponentPolicy.NormalizeHandle(handleText);
                var objectId = database.GetObjectId(false, new Handle(Convert.ToInt64(handle, 16)), 0);
                if (objectId.IsNull || objectId.IsErased)
                {
                    throw new InvalidOperationException($"source handle '{handle}' was not found");
                }

                if (sourceTransaction.GetObject(objectId, OpenMode.ForRead, false) is not Entity)
                {
                    throw new InvalidOperationException($"source handle '{handle}' is not an entity");
                }

                sourceIds.Add(objectId);
                sourceHandles.Add(handle);
            }
        }

        var candidateCreated = false;
        string? candidateIdentity = null;
        try
        {
            using var candidate = new Database(true, true);
            var idMapping = new IdMapping();
            database.WblockCloneObjects(
                sourceIds,
                candidate.CurrentSpaceId,
                idMapping,
                DuplicateRecordCloning.Ignore,
                false);

            var mappings = new List<StandaloneDwgComponentHandleMapping>();
            using (var candidateTransaction = candidate.TransactionManager.StartOpenCloseTransaction())
            {
                foreach (var sourceHandle in sourceHandles)
                {
                    var sourceId = database.GetObjectId(false, new Handle(Convert.ToInt64(sourceHandle, 16)), 0);
                    if (!idMapping.Contains(sourceId))
                    {
                        throw new InvalidOperationException(
                            $"candidate clone did not return a mapping for source '{sourceHandle}'");
                    }

                    var destinationId = idMapping[sourceId].Value;
                    if (candidateTransaction.GetObject(destinationId, OpenMode.ForWrite, false) is not Entity destination)
                    {
                        throw new InvalidOperationException(
                            $"candidate clone destination for source '{sourceHandle}' is not an entity");
                    }

                    var planComponent = plan.Components.First(component =>
                        component.SourceHandles.Any(handle =>
                            string.Equals(
                                StandaloneDwgComponentPolicy.NormalizeHandle(handle),
                                sourceHandle,
                                StringComparison.OrdinalIgnoreCase)));
                    destination.TransformBy(CreateLocalTransform(planComponent.Transform));
                    mappings.Add(new StandaloneDwgComponentHandleMapping
                    {
                        SourceHandle = sourceHandle,
                        CandidateHandle = destination.Handle.ToString().ToUpperInvariant()
                    });
                }

                candidateTransaction.Commit();
            }

            candidate.SaveAs(outputPath, DwgVersion.Current);
            candidateCreated = true;
            candidateIdentity = CaptureCandidateIdentity(outputPath);
            var outputHash = StandaloneDwgComponentPolicy.ComputeSha256(outputPath);
            var reopenable = ReopenAndHash(outputPath, outputHash);
            var sourceAfter = StandaloneDwgComponentPolicy.ComputeSha256(sourcePath);
            var dbmodAfter = ReadDbmod();
            RequireReadOnlySource();
            return new StandaloneDwgComponentCandidateSnapshot
            {
                CandidateCreated = true,
                CandidateOutputPath = outputPath,
                CandidateOutputIdentity = candidateIdentity,
                CandidateOutputSha256 = outputHash,
                SourceMutated = sourceBefore != sourceAfter || dbmodBefore != dbmodAfter,
                SourceSha256Before = sourceBefore,
                SourceSha256After = sourceAfter,
                SourceDbmodBefore = dbmodBefore,
                SourceDbmodAfter = dbmodAfter,
                SavePerformed = true,
                Reopenable = reopenable,
                Mappings = mappings
            };
        }
        catch (Exception exception)
        {
            if (candidateCreated && candidateIdentity is null)
            {
                throw BuildRetainedCandidateCleanupFailure(outputPath, exception);
            }

            if (candidateCreated && candidateIdentity is not null
                && !DeleteCandidateIfIdentityMatches(outputPath, candidateIdentity))
            {
                throw new StandaloneDwgComponentPolicyException(
                    StandaloneDwgComponentPolicy.CleanupFailedCode,
                    "candidate cleanup failed after extraction error");
            }

            throw;
        }
    }

    public bool IsCandidatePathAbsent(string path) =>
        !File.Exists(path) && !Directory.Exists(path);

    internal static StandaloneDwgComponentPolicyException BuildRetainedCandidateCleanupFailure(
        string outputPath,
        Exception identityCaptureException) =>
        new(
            StandaloneDwgComponentPolicy.CleanupFailedCode,
            $"CANDIDATE_RETAINED_UNVERIFIED: candidate output was serialized but its identity could not be captured; cleanup was not attempted without a usable identity; candidate_path='{outputPath}'; candidate_identity=UNAVAILABLE; cause={identityCaptureException.Message}");

    public string CaptureCandidateIdentity(string path)
    {
        EnsureNoReparsePoints(path);
        var info = new FileInfo(path);
        if (!info.Exists)
        {
            throw new FileNotFoundException("candidate output was not found after serialization", path);
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

    private bool RequireReadOnlySource()
    {
        if (IsSourceReadOnly != true)
        {
            throw new StandaloneDwgComponentPolicyException(
                StandaloneDwgComponentPolicy.SourceReadOnlyRequiredCode,
                "source document is not positively verified as read-only");
        }

        return true;
    }

    private static StandaloneDwgComponentBounds Bounds(Extents3d extents) => new()
    {
        Min = new StandaloneDwgComponentPoint
        {
            X = extents.MinPoint.X,
            Y = extents.MinPoint.Y,
            Z = extents.MinPoint.Z
        },
        Max = new StandaloneDwgComponentPoint
        {
            X = extents.MaxPoint.X,
            Y = extents.MaxPoint.Y,
            Z = extents.MaxPoint.Z
        }
    };

    private static Matrix3d CreateLocalTransform(StandaloneDwgComponentTransform? transform)
    {
        if (transform?.Translation is null
            || !double.IsFinite(transform.RotationDegrees)
            || transform.RotationDegrees is < -360 or > 360
            || !double.IsFinite(transform.UniformScale)
            || transform.UniformScale <= 0
            || !double.IsFinite(transform.Translation.X)
            || !double.IsFinite(transform.Translation.Y)
            || !double.IsFinite(transform.Translation.Z))
        {
            throw new StandaloneDwgComponentPolicyException(
                StandaloneDwgComponentPolicy.TransformPolicyCode,
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

    private static bool ReopenAndHash(string path, string expectedHash)
    {
        using var reopened = new Database(false, true);
        reopened.ReadDwgFile(path, FileOpenMode.OpenForReadAndAllShare, false, string.Empty);
        reopened.CloseInput(true);
        return string.Equals(
            StandaloneDwgComponentPolicy.ComputeSha256(path),
            expectedHash,
            StringComparison.Ordinal);
    }

    private static int ReadDbmod() => Convert.ToInt32(
        AcadApplication.GetSystemVariable("DBMOD"),
        CultureInfo.InvariantCulture);

    private static void EnsureNoReparsePoints(string path)
    {
        var current = new DirectoryInfo(
            File.Exists(path) ? Path.GetDirectoryName(path)! : path);
        while (current is not null)
        {
            if (current.Exists && current.Attributes.HasFlag(FileAttributes.ReparsePoint))
            {
                throw new StandaloneDwgComponentPolicyException(
                    StandaloneDwgComponentPolicy.CandidatePathUnsafeCode,
                    $"candidate path contains a reparse point: {current.FullName}");
            }

            current = current.Parent;
        }
    }
}
