using CadAgent.AutoCAD2027.Drawing;
using Xunit;

namespace CadAgent.AutoCAD2027.Tests.Drawing;

public sealed class StandaloneDwgComponentReaderTests : IDisposable
{
    private const string SourceHash = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    private const string OutputHash = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";

    private readonly string _root;
    private readonly string _sourcePath;
    private readonly string _outputPath;
    private readonly StandaloneDwgComponentPolicy _policy;

    public StandaloneDwgComponentReaderTests()
    {
        _root = Path.Combine(Path.GetTempPath(), "cadagent-s3c-reader-" + Guid.NewGuid().ToString("N"));
        _sourcePath = Path.Combine(_root, "source", "standalone-source.dwg");
        _outputPath = Path.Combine(_root, "candidate", "standalone-output.dwg");
        Directory.CreateDirectory(Path.GetDirectoryName(_sourcePath)!);
        Directory.CreateDirectory(Path.GetDirectoryName(_outputPath)!);
        File.WriteAllText(_sourcePath, "synthetic-source");
        _policy = new StandaloneDwgComponentPolicy(Path.Combine(_root, "candidate"));
    }

    [Fact]
    public void RejectsXrefOnlySourceContract()
    {
        var database = Database();
        database.Inspection = Inspection(IsXrefSource: true);

        var result = Reader(database).Inspect(Request());

        Assert.False(result.Success);
        Assert.Contains(result.Errors, error => error.Contains(
            StandaloneDwgComponentPolicy.XrefOnlySourceContractCode,
            StringComparison.Ordinal));
        Assert.Equal(0, database.ExtractionCallCount);
    }

    [Fact]
    public void RequiresExactExplicitHandles()
    {
        var database = Database();
        database.Inspection = Inspection(entities: Array.Empty<StandaloneDwgComponentEntitySnapshot>());

        var result = Reader(database).Inspect(Request());

        Assert.False(result.Success);
        Assert.Contains(result.Errors, error => error.Contains(
            StandaloneDwgComponentPolicy.ExactHandlesRequiredCode,
            StringComparison.Ordinal));
    }

    [Fact]
    public void ContractStyleInsertAcceptsBlockReferenceAndRejectsMismatchedType()
    {
        Assert.Equal(
            "INSERT",
            StandaloneDwgComponentEntityTypeContract.FromNativeTypeName("BlockReference"));

        var accepted = Reader(Database()).Inspect(Request());

        Assert.True(accepted.Success);

        var mismatchedDatabase = Database();
        mismatchedDatabase.Inspection = Inspection(entityType: "BLOCK");

        var rejected = Reader(mismatchedDatabase).Inspect(Request());

        Assert.False(rejected.Success);
        Assert.Contains(rejected.Errors, error => error.Contains(
            StandaloneDwgComponentPolicy.SourceIdentityMismatchCode,
            StringComparison.Ordinal));
    }

    [Fact]
    public void RejectsUnverifiedSourceCustodyBeforeInspection()
    {
        var database = Database();
        database.IsSourceReadOnly = null;

        var result = Reader(database).Inspect(Request());

        Assert.False(result.Success);
        Assert.False(result.ReadOnly);
        Assert.Contains(result.Errors, error => error.Contains(
            StandaloneDwgComponentPolicy.SourceReadOnlyRequiredCode,
            StringComparison.Ordinal));
        Assert.Equal(0, database.InspectionCallCount);
    }

    [Fact]
    public void RejectsWritableSourceBeforeCandidateCreation()
    {
        var database = Database();
        database.IsSourceReadOnly = false;

        var result = Reader(database).Extract(Plan());

        Assert.False(result.Success);
        Assert.Contains(result.Errors, error => error.Contains(
            StandaloneDwgComponentPolicy.SourceReadOnlyRequiredCode,
            StringComparison.Ordinal));
        Assert.Equal(0, database.ExtractionCallCount);
    }

    [Fact]
    public void RejectsStaleSourceHashBeforeCandidateCreation()
    {
        var database = Database();
        database.SourceSha256 = new string('c', 64);

        var result = Reader(database).Extract(Plan());

        Assert.False(result.Success);
        Assert.Contains(result.Errors, error => error.Contains(
            StandaloneDwgComponentPolicy.SourceFreshnessMismatchCode,
            StringComparison.Ordinal));
        Assert.Equal(0, database.ExtractionCallCount);
    }

    [Fact]
    public void VerifiedReadOnlySourcePassesInspectionAndExtraction()
    {
        var database = Database();

        Assert.True(Reader(database).Inspect(Request()).Success);
        Assert.True(Reader(database).Extract(Plan()).Success);
    }

    [Fact]
    public void RejectsSourceHashOrDbmodDrift()
    {
        var database = Database();
        database.Inspection = Inspection(
            sourceSha256After: new string('c', 64),
            dbmodAfter: 1);

        var result = Reader(database).Inspect(Request());

        Assert.False(result.Success);
        Assert.Contains(result.Errors, error => error.Contains(
            StandaloneDwgComponentPolicy.SourceHashOrDbmodDriftCode,
            StringComparison.Ordinal));
    }

    [Fact]
    public void StartsAnEmptyCandidateDatabase()
    {
        var database = Database();
        var result = Reader(database).Extract(Plan());

        Assert.True(result.Success);
        Assert.Equal(1, database.ExtractionCallCount);
        Assert.Equal("EMPTY_NEW_DATABASE", database.LastPlan!.CandidateBaseModel);
        Assert.Null(database.LastCandidateInputPath);
    }

    [Fact]
    public void SerializesOnlyThePlannedCandidateOutput()
    {
        var database = Database();
        database.Candidate = Candidate(CandidateOutputPath: Path.Combine(_root, "candidate", "other.dwg"));

        var result = Reader(database).Extract(Plan());

        Assert.False(result.Success);
        Assert.Contains(result.Errors, error => error.Contains(
            StandaloneDwgComponentPolicy.ForbiddenWriteTargetCode,
            StringComparison.Ordinal));
    }

    [Fact]
    public void RejectsAnyOtherWriteTarget()
    {
        var database = Database();
        database.Candidate = Candidate(CandidateOutputPath: _sourcePath);

        var result = Reader(database).Extract(Plan());

        Assert.False(result.Success);
        Assert.Contains(result.Errors, error => error.Contains(
            StandaloneDwgComponentPolicy.ForbiddenWriteTargetCode,
            StringComparison.Ordinal));
    }

    [Fact]
    public void RequiresReopenableHashBoundOutput()
    {
        var database = Database();
        database.Candidate = Candidate(Reopenable: false);

        var result = Reader(database).Extract(Plan());

        Assert.False(result.Success);
        Assert.Contains(result.Errors, error => error.Contains(
            StandaloneDwgComponentPolicy.CandidateOutputNotReopenableCode,
            StringComparison.Ordinal));
    }

    [Fact]
    public void MapsEveryApprovedHandleExactlyOnce()
    {
        var database = Database();
        database.Candidate = Candidate(
            Mappings: new[]
            {
                new StandaloneDwgComponentHandleMapping { SourceHandle = "A1B2", CandidateHandle = "F001" },
                new StandaloneDwgComponentHandleMapping { SourceHandle = "A1B2", CandidateHandle = "F002" }
            });

        var result = Reader(database).Extract(Plan());

        Assert.False(result.Success);
        Assert.Contains(result.Errors, error => error.Contains(
            StandaloneDwgComponentPolicy.MappingInvalidCode,
            StringComparison.Ordinal));
    }

    [Fact]
    public void CleansOnlyWhenCandidateIdentityStillMatches()
    {
        var database = Database();
        database.Candidate = Candidate(Reopenable: false);
        database.DeleteIdentityMatches = false;

        var result = Reader(database).Extract(Plan());

        Assert.False(result.Success);
        Assert.Contains(result.Errors, error => error.Contains(
            StandaloneDwgComponentPolicy.CleanupFailedCode,
            StringComparison.Ordinal));
        Assert.Equal("candidate-identity-001", database.LastDeletedIdentity);
    }

    public void Dispose()
    {
        try
        {
            Directory.Delete(_root, recursive: true);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            // Synthetic test artifacts are disposable and have no persistence contract.
        }
    }

    private AutoCadStandaloneDwgComponentReader Reader(FakeStandaloneDatabase database) =>
        new(database, _policy);

    private FakeStandaloneDatabase Database() => new(_sourcePath)
    {
        Inspection = Inspection(),
        Candidate = Candidate()
    };

    private StandaloneDwgComponentInspectionRequest Request() => new()
    {
        RequestId = "standalone-inspection-request-001",
        RunId = "standalone-run-001",
        SourceDrawingPath = _sourcePath,
        SourceDrawingSha256 = SourceHash,
        SourceSetupAuditSha256 = new string('d', 64),
        ExpectedDbmod = 0,
        SelectionGroups = new[]
        {
            new StandaloneDwgComponentSelectionGroup
            {
                GroupId = "group-001",
                LogicalComponentId = "component-001",
                SourceHandles = new[] { "A1B2" },
                ExpectedEntityTypes = new[] { "INSERT" },
                SourceLayerExpectations = new[] { "BODY" }
            }
        }
    };

    private StandaloneDwgComponentExtractionPlan Plan() => new()
    {
        PlanId = "standalone-plan-001",
        RequestId = "standalone-extraction-request-001",
        RunId = "standalone-run-001",
        InspectionId = "standalone-inspection-001",
        InspectionSha256 = new string('e', 64),
        SourceDrawingSha256 = SourceHash,
        CandidateOutputPath = _outputPath,
        CandidateBaseModel = "EMPTY_NEW_DATABASE",
        TransformPolicy = "LOCAL_TRANSLATION_ROTATION_UNIFORM_SCALE_ONLY",
        Approval = new StandaloneDwgComponentApproval
        {
            Reference = "approval-standalone-001",
            Status = "APPROVED"
        },
        Components = new[]
        {
            new StandaloneDwgComponentPlanComponent
            {
                GroupId = "group-001",
                LogicalComponentId = "component-001",
                SourceHandles = new[] { "A1B2" },
                Transform = new StandaloneDwgComponentTransform
                {
                    RotationDegrees = 0,
                    Translation = new StandaloneDwgComponentPoint(),
                    UniformScale = 1
                }
            }
        }
    };

    private StandaloneDwgComponentInspectionSnapshot Inspection(
        bool IsXrefSource = false,
        string? sourceSha256After = null,
        int dbmodAfter = 0,
        string entityType = "INSERT",
        IReadOnlyList<StandaloneDwgComponentEntitySnapshot>? entities = null) => new()
        {
            Success = true,
            DrawingFullPath = _sourcePath,
            Changed = false,
            ReadOnly = true,
            IsXrefSource = IsXrefSource,
            Eligible = true,
            SourceSha256Before = SourceHash,
            SourceSha256After = sourceSha256After ?? SourceHash,
            DbmodBefore = 0,
            DbmodAfter = dbmodAfter,
            Entities = entities ?? new[]
            {
                new StandaloneDwgComponentEntitySnapshot
                {
                    SourceHandle = "A1B2",
                    EntityType = entityType,
                    Layer = "BODY",
                    Bounds = new StandaloneDwgComponentBounds
                    {
                        Min = new StandaloneDwgComponentPoint(),
                        Max = new StandaloneDwgComponentPoint { X = 1, Y = 1, Z = 1 }
                    }
                }
            }
        };

    private StandaloneDwgComponentCandidateSnapshot Candidate(
        string? CandidateOutputPath = null,
        bool Reopenable = true,
        IReadOnlyList<StandaloneDwgComponentHandleMapping>? Mappings = null) => new()
        {
            CandidateCreated = true,
            CandidateOutputPath = CandidateOutputPath ?? _outputPath,
            CandidateOutputIdentity = "candidate-identity-001",
            CandidateOutputSha256 = OutputHash,
            SourceMutated = false,
            SourceSha256Before = SourceHash,
            SourceSha256After = SourceHash,
            SourceDbmodBefore = 0,
            SourceDbmodAfter = 0,
            SavePerformed = true,
            Reopenable = Reopenable,
            Mappings = Mappings ?? new[]
            {
                new StandaloneDwgComponentHandleMapping
                {
                    SourceHandle = "A1B2",
                    CandidateHandle = "F001"
                }
            }
        };

    private sealed class FakeStandaloneDatabase : IStandaloneDwgComponentDatabase
    {
        private readonly string _sourcePath;

        public FakeStandaloneDatabase(string sourcePath)
        {
            _sourcePath = sourcePath;
        }

        public string? ActiveDocumentFullPath => _sourcePath;

        public bool? IsSourceReadOnly { get; set; } = true;

        public string SourceSha256 { get; set; } = SourceHash;

        public StandaloneDwgComponentInspectionSnapshot Inspection { get; set; } = new();

        public StandaloneDwgComponentCandidateSnapshot Candidate { get; set; } = new();

        public int ExtractionCallCount { get; private set; }

        public int InspectionCallCount { get; private set; }

        public int SourceSha256CallCount { get; private set; }

        public StandaloneDwgComponentExtractionPlan? LastPlan { get; private set; }

        public string? LastCandidateInputPath { get; private set; }

        public bool DeleteIdentityMatches { get; set; } = true;

        public string? LastDeletedIdentity { get; private set; }

        public StandaloneDwgComponentInspectionSnapshot ReadSelectedEntities(
            StandaloneDwgComponentInspectionRequest request)
        {
            InspectionCallCount++;
            return Inspection;
        }

        public string ComputeSourceSha256()
        {
            SourceSha256CallCount++;
            return SourceSha256;
        }

        public StandaloneDwgComponentCandidateSnapshot ExtractToNewCandidate(
            StandaloneDwgComponentExtractionPlan plan)
        {
            ExtractionCallCount++;
            LastPlan = plan;
            return Candidate;
        }

        public bool IsCandidatePathAbsent(string path) =>
            !File.Exists(path) && !Directory.Exists(path);

        public string CaptureCandidateIdentity(string path) => "candidate-identity-001";

        public bool DeleteCandidateIfIdentityMatches(string path, string identity)
        {
            LastDeletedIdentity = identity;
            return DeleteIdentityMatches;
        }
    }
}
