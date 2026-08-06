using System.Globalization;
using System.Security.Cryptography;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
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

    public static ExactBaseXrefInspectionSnapshot Unavailable(string error) => new()
    {
        Success = false,
        Changed = false,
        EntityHandles = Array.Empty<string>(),
        Errors = new[] { error }
    };
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

            if (!SamePath(activePath, configuration.AcceptedDwgPath))
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

            if (!string.Equals(targetHashBefore, configuration.AcceptedDwgSha256, StringComparison.Ordinal))
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
