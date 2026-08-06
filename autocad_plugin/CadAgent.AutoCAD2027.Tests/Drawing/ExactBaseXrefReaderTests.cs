using CadAgent.AutoCAD2027.Commands;
using CadAgent.AutoCAD2027.Drawing;
using Xunit;

namespace CadAgent.AutoCAD2027.Tests.Drawing;

public sealed class ExactBaseXrefReaderTests : IDisposable
{
    private const string SourceHash = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    private const string TargetHash = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    private const string CandidateHash = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd";

    private readonly string _root;
    private readonly string _sourcePath;
    private readonly string _acceptedPath;
    private readonly string _targetPath;
    private readonly string _candidateInputPath;
    private readonly ExactBaseXrefPolicy _policy;

    public ExactBaseXrefReaderTests()
    {
        _root = Path.Combine(Path.GetTempPath(), "cadagent-s3b-reader-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_root);
        _sourcePath = Path.Combine(_root, "source", "base-vehicle.dwg");
        _acceptedPath = Path.Combine(_root, "accepted", "accepted.dwg");
        _targetPath = _acceptedPath;
        _candidateInputPath = Path.Combine(_root, "candidate", "input.dwg");
        Directory.CreateDirectory(Path.GetDirectoryName(_sourcePath)!);
        Directory.CreateDirectory(Path.GetDirectoryName(_acceptedPath)!);
        Directory.CreateDirectory(Path.GetDirectoryName(_candidateInputPath)!);
        File.WriteAllText(_sourcePath, "source");
        File.WriteAllText(_acceptedPath, "accepted");
        File.WriteAllText(_candidateInputPath, "candidate");
        _policy = new ExactBaseXrefPolicy(new ExactBaseXrefServerConfiguration(
            _root,
            _acceptedPath,
            TargetHash,
            _sourcePath,
            SourceHash,
            "rev-2026-08-05-01"));
    }

    [Fact]
    public void InspectsOnlyNamedExternalXrefAndReturnsReadOnlyResult()
    {
        var database = new FakeExactBaseXrefDatabase(_targetPath, _sourcePath, TargetHash, SourceHash);
        var result = CreateReader(database).Read(Request());

        Assert.True(result.Success);
        Assert.Equal(_targetPath, result.DrawingFullPath);
        Assert.False(result.Changed);
        Assert.Empty(result.EntityHandles);
        Assert.NotNull(result.Evidence);
        Assert.True(result.Evidence!.Eligible);
        Assert.Equal("vehicle-001", result.Evidence.IdentityObservations![0].Observed);
        Assert.Equal(1, database.NamedXrefReadCount);
        Assert.Equal(0, database.ModelSpaceScanCount);
        Assert.Equal(0, database.SaveCallCount);
    }

    [Fact]
    public void RebuildsLiveIdentityFromDatabaseInsteadOfCallerOwnedEvidence()
    {
        var database = new FakeExactBaseXrefDatabase(_targetPath, _sourcePath, TargetHash, SourceHash)
        {
            Vehicle = "different-vehicle"
        };

        var result = CreateReader(database).Read(Request());

        Assert.False(result.Success);
        Assert.Contains(result.Errors, error => error.Contains("identity", StringComparison.OrdinalIgnoreCase));
        Assert.NotNull(result.Evidence);
        Assert.Equal("different-vehicle", result.Evidence!.IdentityObservations!
            .Single(observation => observation.Field == "vehicle").Observed);
        Assert.Equal(0, database.SaveCallCount);
    }

    [Fact]
    public void FailsClosedWhenSourceHashChangesDuringInspection()
    {
        var database = new FakeExactBaseXrefDatabase(_targetPath, _sourcePath, TargetHash, SourceHash)
        {
            PreflightSourceHashAfter = new string('c', 64)
        };

        var result = CreateReader(database).Read(Request());

        Assert.False(result.Success);
        Assert.Contains(result.Errors, error => error.Contains("source", StringComparison.OrdinalIgnoreCase));
        Assert.False(result.Changed);
        Assert.Empty(result.EntityHandles);
        Assert.Equal(0, database.SaveCallCount);
    }

    [Fact]
    public void FailsClosedWhenTargetDbmodChangesDuringInspection()
    {
        var database = new FakeExactBaseXrefDatabase(_targetPath, _sourcePath, TargetHash, SourceHash)
        {
            DbmodAfter = 1
        };

        var result = CreateReader(database).Read(Request());

        Assert.False(result.Success);
        Assert.Contains(result.Errors, error => error.Contains("DBMOD", StringComparison.OrdinalIgnoreCase));
        Assert.False(result.Changed);
        Assert.Empty(result.EntityHandles);
        Assert.Equal(0, database.SaveCallCount);
    }

    [Fact]
    public void FailsClosedWhenTargetHashChangesDuringInspection()
    {
        var database = new FakeExactBaseXrefDatabase(_targetPath, _sourcePath, TargetHash, SourceHash)
        {
            TargetHashAfter = new string('c', 64)
        };

        var result = CreateReader(database).Read(Request());

        Assert.False(result.Success);
        Assert.Contains(result.Errors, error => error.Contains("target", StringComparison.OrdinalIgnoreCase));
        Assert.False(result.Changed);
        Assert.Empty(result.EntityHandles);
        Assert.Equal(0, database.SaveCallCount);
    }

    [Fact]
    public void RejectsNonExternalOrWritableXrefWithoutSaving()
    {
        var database = new FakeExactBaseXrefDatabase(_targetPath, _sourcePath, TargetHash, SourceHash)
        {
            IsExternalReference = false,
            IsReadOnly = false
        };

        var result = CreateReader(database).Read(Request());

        Assert.False(result.Success);
        Assert.Contains(result.Errors, error => error.Contains("external", StringComparison.OrdinalIgnoreCase));
        Assert.False(result.Changed);
        Assert.Empty(result.EntityHandles);
        Assert.Equal(0, database.SaveCallCount);
    }

    [Fact]
    public void ExceptionsFailClosedAndNeverSave()
    {
        var database = new FakeExactBaseXrefDatabase(_targetPath, _sourcePath, TargetHash, SourceHash)
        {
            InspectionException = new InvalidOperationException("deterministic read failure")
        };

        var result = CreateReader(database).Read(Request());

        Assert.False(result.Success);
        Assert.Contains(result.Errors, error => error.Contains("deterministic read failure", StringComparison.Ordinal));
        Assert.False(result.Changed);
        Assert.Empty(result.EntityHandles);
        Assert.Equal(0, database.SaveCallCount);
    }

    [Fact]
    public void NullGatewayReportsLiveOperationUnavailable()
    {
        var result = new NullDrawingGateway().ReadExactBaseXrefInspection(Request());

        Assert.False(result.Success);
        Assert.False(result.Changed);
        Assert.Empty(result.EntityHandles);
        Assert.Contains(result.Errors, error => error == "S3B_LIVE_UNAVAILABLE");
    }

    [Fact]
    public void ExtractionRunsFreshLivePreflightAndReturnsSortedNativeCandidateEvidence()
    {
        var database = ExtractionDatabase();

        var result = CreateReader(database).Extract(ExtractionRequest(), "xref-extraction-request-001");

        Assert.True(result.Success);
        Assert.True(result.Changed);
        Assert.Equal(new[] { "E001", "E002" }, result.EntityHandles);
        Assert.NotNull(result.Evidence);
        Assert.True(result.Evidence!.CandidateChangedDuringOperation);
        Assert.Equal(1, database.NamedXrefReadCount);
        Assert.Equal(1, database.ExtractionCallCount);
        Assert.Equal(0, database.DeleteCandidateCallCount);
        Assert.Equal(
            new[] { ("1A2B", "E001"), ("1A2C", "E002") },
            result.Evidence.SourceHandleToCandidateHandle
                .Select(mapping => (mapping.SourceHandle, mapping.CandidateHandle)));
    }

    [Fact]
    public void ExtractionDoesNotTreatPriorInspectionAsFreshAuthority()
    {
        var database = ExtractionDatabase();
        database.Vehicle = "stale-or-wrong-vehicle";

        var result = CreateReader(database).Extract(ExtractionRequest(), "xref-extraction-request-001");

        Assert.False(result.Success);
        Assert.False(result.Changed);
        Assert.Empty(result.EntityHandles);
        Assert.Equal(1, database.NamedXrefReadCount);
        Assert.Equal(0, database.ExtractionCallCount);
    }

    [Fact]
    public void ExtractionRejectsFreshComponentIdentityMismatchBeforeMutation()
    {
        var database = ExtractionDatabase();
        database.ComponentHandleOverride = "FFFF";

        var result = CreateReader(database).Extract(ExtractionRequest(), "xref-extraction-request-001");

        Assert.False(result.Success);
        Assert.False(result.Changed);
        Assert.Empty(result.EntityHandles);
        Assert.Contains(result.Errors, error => error.Contains("component", StringComparison.OrdinalIgnoreCase));
        Assert.Equal(1, database.NamedXrefReadCount);
        Assert.Equal(0, database.ExtractionCallCount);
    }

    [Fact]
    public void ExtractionCleansOnlyOperationOwnedCandidateWhenSourceChangesAfterClone()
    {
        var database = ExtractionDatabase();
        database.SourceHashAfter = new string('c', 64);
        database.ExtractionResult = new ExactBaseXrefDatabaseExtractionResult
        {
            CandidateCreated = true,
            CandidateOutputIdentity = "candidate-identity-001",
            CandidateInputSha256 = CandidateHash,
            CandidateOutputSha256 = new string('e', 64),
            SavePerformed = true,
            Components = database.ExtractedComponents
        };

        var result = CreateReader(database).Extract(ExtractionRequest(), "xref-extraction-request-001");

        Assert.False(result.Success);
        Assert.False(result.Changed);
        Assert.Empty(result.EntityHandles);
        Assert.Equal(1, database.DeleteCandidateCallCount);
        Assert.Equal("candidate-identity-001", database.LastDeletedIdentity);
    }

    [Fact]
    public void ExtractionRejectsExistingCandidateOutputBeforePreflight()
    {
        var request = ExtractionRequest();
        File.WriteAllText(request.CandidateOutputPath!, "existing");
        var database = ExtractionDatabase();

        var result = CreateReader(database).Extract(request, "xref-extraction-request-001");

        Assert.False(result.Success);
        Assert.False(result.Changed);
        Assert.Empty(result.EntityHandles);
        Assert.Contains(result.Errors, error => error.Contains("already exists", StringComparison.OrdinalIgnoreCase));
        Assert.Equal(0, database.NamedXrefReadCount);
        Assert.Equal(0, database.ExtractionCallCount);
    }

    public void Dispose()
    {
        try
        {
            Directory.Delete(_root, recursive: true);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            // The test has no persistent artifact contract.
        }
    }

    private AutoCadExactBaseXrefReader CreateReader(FakeExactBaseXrefDatabase database) =>
        new(database, _policy, () => new DateTimeOffset(2026, 8, 6, 8, 0, 1, TimeSpan.Zero));

    private FakeExactBaseXrefDatabase ExtractionDatabase()
    {
        var database = new FakeExactBaseXrefDatabase(_candidateInputPath, _sourcePath, CandidateHash, SourceHash);
        database.ExtractedComponents = new[]
        {
            new ExactBaseXrefDatabaseExtractedComponent
            {
                SourceHandle = "1A2B",
                CandidateHandle = "E001"
            },
            new ExactBaseXrefDatabaseExtractedComponent
            {
                SourceHandle = "1A2C",
                CandidateHandle = "E002"
            }
        };
        return database;
    }

    private ExactBaseXrefExtractionParameters ExtractionRequest()
    {
        var inspection = Request();
        return new ExactBaseXrefExtractionParameters
        {
            RunId = inspection.RunId,
            SourceFullPath = inspection.SourceFullPath,
            SourceRevision = inspection.SourceRevision,
            TargetRole = ExactBaseXrefOperationNames.ExtractionTargetRole,
            InspectionExpectations = inspection.InspectionExpectations,
            CandidateOutputPath = Path.Combine(_root, "candidate", "output.dwg"),
            ExtractionPlan = new ExactBaseXrefExtractionPlan
            {
                Approval = new ExactBaseXrefApproval { Reference = "approval-example-001", Status = "APPROVED" },
                BaseSource = new ExactBaseXrefPlanSource
                {
                    RelativePath = "base-vehicle.dwg",
                    Revision = inspection.SourceRevision,
                    Sha256 = SourceHash,
                    SourceId = inspection.InspectionExpectations!.Source!.SourceId
                },
                Components = inspection.InspectionExpectations.Components!
                    .Select(component => new ExactBaseXrefPlanComponent
                    {
                        ComponentType = component.ComponentType,
                        LogicalComponentId = component.LogicalComponentId,
                        Provenance = component.Provenance,
                        SourceBlock = component.SourceBlock,
                        SourceHandle = component.SourceHandle,
                        SourceLayer = component.SourceLayer,
                        Bounding = new ExactBaseXrefBounding
                        {
                            Min = new ExactBaseXrefPoint { X = 0, Y = 0, Z = 0 },
                            Max = new ExactBaseXrefPoint { X = 1, Y = 1, Z = 1 }
                        },
                        Transform = new ExactBaseXrefTransform
                        {
                            RotationDegrees = 15,
                            Translation = new ExactBaseXrefPoint { X = 10, Y = 20, Z = 0 },
                            UniformScale = 1.25
                        }
                    })
                    .ToList(),
                ImpactedViews = new List<ExactBaseXrefView>
                {
                    new() { Identity = "model-space", Name = "Model" }
                },
                InspectionId = "inspection-001",
                PlanId = "extraction-plan-001",
                Provenance = ExactBaseXrefOperationNames.ReusedFromBaseCad,
                RequestId = "xref-inspection-request-001",
                RunId = inspection.RunId,
                SchemaVersion = "exact-base-xref-extraction-plan-1.0",
                SourceRevision = inspection.SourceRevision,
                TargetDrawingSha256 = CandidateHash,
                TransformPolicy = ExactBaseXrefOperationNames.TransformPolicy
            }
        };
    }

    private ExactBaseXrefInspectionParameters Request() => new()
    {
        RunId = "run-001",
        SourceFullPath = _sourcePath,
        SourceRevision = "rev-2026-08-05-01",
        TargetRole = ExactBaseXrefOperationNames.InspectionTargetRole,
        InspectionExpectations = new ExactBaseXrefInspectionExpectations
        {
            Source = new ExactBaseXrefSourceExpectation
            {
                SourceId = "base-vehicle-001",
                Revision = "rev-2026-08-05-01",
                Sha256 = SourceHash
            },
            Identity = new ExactBaseXrefIdentityExpectation
            {
                Vehicle = "vehicle-001",
                Model = "model-x"
            },
            CriticalDimensions = new List<ExactBaseXrefDimensionExpectation>
            {
                new() { Control = "axle", Target = 100, Tolerance = 0.1, Unit = "mm" },
                new() { Control = "cabin", Target = 200, Tolerance = 0.1, Unit = "mm" },
                new() { Control = "chassis", Target = 300, Tolerance = 0.1, Unit = "mm" },
                new() { Control = "track", Target = 400, Tolerance = 0.1, Unit = "mm" },
                new() { Control = "wheelbase", Target = 500, Tolerance = 0.1, Unit = "mm" }
            },
            Xref = new ExactBaseXrefReference { Name = "BASE_XREF" },
            Components = new List<ExactBaseXrefComponentExpectation>
            {
                new()
                {
                    ComponentType = "BLOCK",
                    LogicalComponentId = "cab-001",
                    Provenance = ExactBaseXrefOperationNames.ReusedFromBaseCad,
                    SourceBlock = "CAB",
                    SourceHandle = "1A2B",
                    SourceLayer = "BODY"
                },
                new()
                {
                    ComponentType = "BLOCK",
                    LogicalComponentId = "wheel-001",
                    Provenance = ExactBaseXrefOperationNames.ReusedFromBaseCad,
                    SourceBlock = "WHEEL",
                    SourceHandle = "1A2C",
                    SourceLayer = "RUNNING_GEAR"
                }
            }
        }
    };

    private sealed class FakeExactBaseXrefDatabase : IExactBaseXrefDatabase
    {
        private readonly string _sourcePath;
        private readonly string _targetHash;

        public FakeExactBaseXrefDatabase(
            string targetPath,
            string sourcePath,
            string targetHash,
            string sourceHash)
        {
            ActiveDocumentFullPath = targetPath;
            _sourcePath = sourcePath;
            _targetHash = targetHash;
            SourceHashBefore = sourceHash;
            SourceHashAfter = sourceHash;
            PreflightSourceHashAfter = sourceHash;
            TargetHashAfter = targetHash;
        }

        public string ActiveDocumentFullPath { get; }

        public int DbmodBefore { get; init; }

        public int DbmodAfter { get; init; }

        public string Vehicle { get; set; } = "vehicle-001";

        public string Model { get; init; } = "model-x";

        public bool IsExternalReference { get; init; } = true;

        public bool IsReadOnly { get; init; } = true;

        public string SourceHashBefore { get; init; }

        public string SourceHashAfter { get; set; }

        public string PreflightSourceHashAfter { get; set; }

        public bool ExtractionCompleted { get; private set; }

        public string ComponentHandleOverride { get; set; } = string.Empty;

        public IReadOnlyList<ExactBaseXrefDatabaseExtractedComponent> ExtractedComponents { get; set; } =
            Array.Empty<ExactBaseXrefDatabaseExtractedComponent>();

        public ExactBaseXrefDatabaseExtractionResult? ExtractionResult { get; set; }

        public int ExtractionCallCount { get; private set; }

        public int DeleteCandidateCallCount { get; private set; }

        public string? LastDeletedIdentity { get; private set; }

        public string TargetHashAfter { get; init; }

        public int NamedXrefReadCount { get; private set; }

        public int ModelSpaceScanCount { get; private set; }

        public int SaveCallCount { get; private set; }

        public Exception? InspectionException { get; init; }

        public int ReadDbmod() => NamedXrefReadCount == 0 ? DbmodBefore : DbmodAfter;

        public string ComputeSha256(string path)
        {
            if (string.Equals(path, _sourcePath, StringComparison.OrdinalIgnoreCase))
            {
                if (NamedXrefReadCount == 0)
                {
                    return SourceHashBefore;
                }

                return ExtractionCompleted ? SourceHashAfter : PreflightSourceHashAfter;
            }

            if (path.EndsWith("output.dwg", StringComparison.OrdinalIgnoreCase))
            {
                return "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee";
            }

            return NamedXrefReadCount == 0 ? _targetHash : TargetHashAfter;
        }

        public ExactBaseXrefDatabaseExtractionResult ExtractApprovedComponents(
            ExactBaseXrefExtractionParameters request,
            IReadOnlyList<ExactBaseXrefPlanComponent> approvedComponents,
            ExactBaseXrefLiveInspection preflight)
        {
            ExtractionCallCount++;
            ExtractionCompleted = true;
            return ExtractionResult ?? new ExactBaseXrefDatabaseExtractionResult
            {
                CandidateCreated = true,
                CandidateOutputIdentity = "candidate-identity-001",
                CandidateInputSha256 = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
                CandidateOutputSha256 = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
                SavePerformed = true,
                Components = ExtractedComponents
            };
        }

        public bool IsCandidatePathAbsent(string path) =>
            !File.Exists(path) && !Directory.Exists(path);

        public string CaptureCandidateIdentity(string path) => "candidate-identity-001";

        public bool DeleteCandidateIfIdentityMatches(string path, string identity)
        {
            DeleteCandidateCallCount++;
            LastDeletedIdentity = identity;
            return true;
        }

        public ExactBaseXrefDatabaseCapture ReadNamedExternalXref(
            ExactBaseXrefInspectionParameters request)
        {
            NamedXrefReadCount++;
            if (InspectionException is not null)
            {
                throw InspectionException;
            }

            return new ExactBaseXrefDatabaseCapture
            {
                XrefName = request.InspectionExpectations!.Xref!.Name!,
                IsExternalReference = IsExternalReference,
                IsReadOnly = IsReadOnly,
                Vehicle = Vehicle,
                Model = Model,
                CriticalDimensions = request.InspectionExpectations.CriticalDimensions!
                    .Select(dimension => new ExactBaseXrefDatabaseDimension
                    {
                        Control = dimension.Control!,
                        Observed = dimension.Target,
                        Unit = dimension.Unit!
                    })
                    .ToArray(),
                Components = request.InspectionExpectations.Components!
                    .Select(component => new ExactBaseXrefDatabaseComponent
                    {
                        ComponentType = component.ComponentType!,
                        SourceBlock = component.SourceBlock!,
                        SourceHandle = string.IsNullOrWhiteSpace(ComponentHandleOverride)
                            ? component.SourceHandle!
                            : ComponentHandleOverride,
                        SourceLayer = component.SourceLayer!,
                        Bounding = new ExactBaseXrefBounding
                        {
                            Min = new ExactBaseXrefPoint { X = 0, Y = 0, Z = 0 },
                            Max = new ExactBaseXrefPoint { X = 1, Y = 1, Z = 1 }
                        }
                    })
                    .ToArray()
            };
        }

        public void Save()
        {
            SaveCallCount++;
        }
    }
}
