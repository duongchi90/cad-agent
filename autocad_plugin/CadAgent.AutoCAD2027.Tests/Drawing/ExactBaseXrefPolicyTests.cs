using System.Text.Json;
using CadAgent.AutoCAD2027.Drawing;
using CadAgent.AutoCAD2027.Ipc;
using Xunit;

namespace CadAgent.AutoCAD2027.Tests.Drawing;

public sealed class ExactBaseXrefPolicyTests : IDisposable
{
    private readonly string _root;
    private readonly string _sourcePath;
    private readonly string _acceptedPath;
    private readonly string _candidateInputPath;
    private readonly string _candidateOutputPath;
    private readonly ExactBaseXrefPolicy _policy;

    public ExactBaseXrefPolicyTests()
    {
        _root = Path.Combine(Path.GetTempPath(), "cadagent-s3b-policy-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_root);
        _sourcePath = Path.Combine(_root, "source", "base-vehicle.dwg");
        _acceptedPath = Path.Combine(_root, "accepted", "accepted.dwg");
        _candidateInputPath = Path.Combine(_root, "candidate", "input.dwg");
        _candidateOutputPath = Path.Combine(_root, "candidate", "output.dwg");
        Directory.CreateDirectory(Path.GetDirectoryName(_sourcePath)!);
        Directory.CreateDirectory(Path.GetDirectoryName(_acceptedPath)!);
        Directory.CreateDirectory(Path.GetDirectoryName(_candidateInputPath)!);
        File.WriteAllText(_sourcePath, "source");
        File.WriteAllText(_acceptedPath, "accepted");
        File.WriteAllText(_candidateInputPath, "candidate");
        _policy = new ExactBaseXrefPolicy(new ExactBaseXrefServerConfiguration(
            _root,
            _acceptedPath,
            new string('b', 64),
            _sourcePath,
            new string('a', 64),
            "rev-2026-08-05-01"));
    }

    [Fact]
    public void AcceptsExactSourceIdentityAndReadOnlyInspectionExpectations()
    {
        var request = InspectionRequest();

        var parameters = _policy.ValidateInspectionRequest(request);

        Assert.Equal("run-001", parameters.RunId);
        Assert.Equal(_sourcePath, parameters.SourceFullPath);
        Assert.Equal("INSPECTION_HOST", parameters.TargetRole);
        Assert.Equal("vehicle-001", parameters.InspectionExpectations.Identity.Vehicle);
        Assert.All(
            parameters.InspectionExpectations.Components,
            component => Assert.Equal("REUSED_FROM_BASE_CAD", component.Provenance));
    }

    [Fact]
    public void LoadsAllSixS3BValuesFromServerOwnedConfiguration()
    {
        var values = new Dictionary<string, string?>(StringComparer.Ordinal)
        {
            [ExactBaseXrefPolicy.DisposableRootEnvironmentVariable] = _root,
            [ExactBaseXrefPolicy.AcceptedDwgPathEnvironmentVariable] = _acceptedPath,
            [ExactBaseXrefPolicy.AcceptedDwgSha256EnvironmentVariable] = new string('b', 64),
            [ExactBaseXrefPolicy.ExactBaseSourcePathEnvironmentVariable] = _sourcePath,
            [ExactBaseXrefPolicy.ExactBaseSourceSha256EnvironmentVariable] = new string('a', 64),
            [ExactBaseXrefPolicy.ExactBaseSourceRevisionEnvironmentVariable] = "rev-2026-08-05-01"
        };

        var policy = ExactBaseXrefPolicy.FromEnvironment(
            name => values.TryGetValue(name, out var value) ? value : null);

        Assert.True(policy.IsConfigured);
        Assert.Equal(_root, policy.Configuration.DisposableRoot);
        Assert.Equal(_acceptedPath, policy.Configuration.AcceptedDwgPath);
        Assert.Equal(_sourcePath, policy.Configuration.ExactBaseSourcePath);
        Assert.Equal("rev-2026-08-05-01", policy.Configuration.ExactBaseSourceRevision);
    }

    [Fact]
    public void AcceptsOnlyLiveEvidenceWithReadOnlyPassGates()
    {
        var request = _policy.ValidateInspectionRequest(InspectionRequest());
        var expectations = request.InspectionExpectations!;
        var evidence = new ExactBaseXrefLiveInspection
        {
            BaseSource = new ExactBaseXrefPlanSource
            {
                RelativePath = "approved/base-vehicle.dwg",
                Revision = "rev-2026-08-05-01",
                Sha256 = new string('a', 64),
                SourceId = "base-vehicle-001"
            },
            SchemaVersion = "exact-base-xref-inspection-1.0",
            CaptureTimestamp = new DateTimeOffset(2026, 8, 6, 8, 0, 1, TimeSpan.Zero),
            Changed = false,
            DbmodBefore = 0,
            DbmodAfter = 0,
            Eligible = true,
            Components = expectations.Components!.Select(component => new ExactBaseXrefLiveComponent
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
                }
            }).ToList(),
            Conflicts = new List<string>(),
            CriticalDimensions = expectations.CriticalDimensions!.Select(dimension => new ExactBaseXrefLiveDimension
            {
                Control = dimension.Control,
                Target = dimension.Target,
                Tolerance = dimension.Tolerance,
                Unit = dimension.Unit,
                Observed = dimension.Target,
                Status = "PASS"
            }).ToList(),
            IdentityObservations = new List<ExactBaseXrefIdentityObservation>
            {
                new() { Field = "vehicle", Observed = "vehicle-001", Target = "vehicle-001", Status = "PASS" },
                new() { Field = "model", Observed = "model-x", Target = "model-x", Status = "PASS" }
            },
            InspectionId = "inspection-001",
            RequestId = "xref-inspection-request-001",
            RunId = "run-001",
            TargetDrawingSha256 = new string('b', 64),
            Warnings = new List<string>(),
            Xref = new ExactBaseXrefLiveXref { Name = "BASE_XREF", ReadOnly = true, Status = "INSPECTED" }
        };

        _policy.ValidateLiveInspection(evidence, request, new string('b', 64));
    }

    [Theory]
    [InlineData("wrong-revision", "source revision")]
    [InlineData("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "source hash")]
    public void RejectsSourceRevisionOrHashMismatch(string replacement, string expected)
    {
        var request = InspectionRequest();
        var expectations = request.Parameters!["inspection_expectations"];
        using var document = JsonDocument.Parse(expectations.GetRawText());
        var source = document.RootElement.GetProperty("source");
        var sourceObject = new Dictionary<string, JsonElement>(StringComparer.Ordinal)
        {
            ["source_id"] = source.GetProperty("source_id"),
            ["revision"] = source.GetProperty("revision"),
            ["sha256"] = source.GetProperty("sha256")
        };
        sourceObject[expected.Contains("revision", StringComparison.Ordinal)
            ? "revision"
            : "sha256"] = JsonSerializer.SerializeToElement(replacement);
        var updated = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(expectations.GetRawText())!;
        updated["source"] = JsonSerializer.SerializeToElement(sourceObject);
        var parameters = request.Parameters.ToDictionary(item => item.Key, item => item.Value, StringComparer.Ordinal);
        parameters["inspection_expectations"] = JsonSerializer.SerializeToElement(updated);

        var error = Assert.Throws<ExactBaseXrefPolicyException>(() =>
            _policy.ValidateInspectionRequest(request with { Parameters = parameters }));

        Assert.Contains("S3B_SOURCE", error.Code, StringComparison.Ordinal);
    }

    [Fact]
    public void RequiresCanonicalApprovalEqualityAndApprovedStatus()
    {
        var request = ExtractionRequest();
        var parameters = request.Parameters!.ToDictionary(item => item.Key, item => item.Value, StringComparer.Ordinal);
        var plan = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(
            request.Parameters["extraction_plan"].GetRawText())!;
        plan["approval"] = JsonSerializer.SerializeToElement(new
        {
            reference = "different-approval",
            status = "APPROVED"
        });
        parameters["extraction_plan"] = JsonSerializer.SerializeToElement(plan);

        var error = Assert.Throws<ExactBaseXrefPolicyException>(() =>
            _policy.ValidateExtractionRequest(request with { Parameters = parameters }));

        Assert.Equal(ExactBaseXrefPolicy.ApprovalMismatchCode, error.Code);
    }

    [Fact]
    public void RejectsCandidateOutputThatAlreadyExistsOrEscapesRoot()
    {
        File.WriteAllText(_candidateOutputPath, "existing");
        var existingOutput = Assert.Throws<ExactBaseXrefPolicyException>(() =>
            _policy.ValidateExtractionRequest(ExtractionRequest(_candidateOutputPath)));
        Assert.Equal(ExactBaseXrefPolicy.CandidateOutputExistsCode, existingOutput.Code);

        var outside = Path.Combine(Path.GetTempPath(), "cadagent-s3b-outside-" + Guid.NewGuid() + ".dwg");
        var escaped = Assert.Throws<ExactBaseXrefPolicyException>(() =>
            _policy.ValidateExtractionRequest(ExtractionRequest(outside)));
        Assert.Equal(ExactBaseXrefPolicy.CandidatePathUnsafeCode, escaped.Code);
    }

    [Theory]
    [InlineData(0.0)]
    [InlineData(-1.0)]
    public void RejectsNonPositiveUniformScale(double scale)
    {
        var request = ExtractionRequest();
        var plan = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(
            request.Parameters!["extraction_plan"].GetRawText())!;
        var components = plan["components"].EnumerateArray().ToArray();
        var first = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(components[0].GetRawText())!;
        var transform = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(
            first["transform"].GetRawText())!;
        transform["uniform_scale"] = JsonSerializer.SerializeToElement(scale);
        first["transform"] = JsonSerializer.SerializeToElement(transform);
        plan["components"] = JsonSerializer.SerializeToElement(new[]
        {
            JsonSerializer.SerializeToElement(first),
            components[1]
        });
        var parameters = request.Parameters.ToDictionary(item => item.Key, item => item.Value, StringComparer.Ordinal);
        parameters["extraction_plan"] = JsonSerializer.SerializeToElement(plan);

        var error = Assert.Throws<ExactBaseXrefPolicyException>(() =>
            _policy.ValidateExtractionRequest(request with { Parameters = parameters }));

        Assert.Equal(ExactBaseXrefPolicy.TransformPolicyCode, error.Code);
    }

    [Fact]
    public void NeverTreatsPriorRunAsFreshLivePreflight()
    {
        var error = Assert.Throws<ExactBaseXrefPolicyException>(() =>
            _policy.RequireFreshLivePreflight("run-001"));

        Assert.Equal(ExactBaseXrefPolicy.LivePreflightRequiredCode, error.Code);
    }

    [Fact]
    public void RejectsReparsePointCandidateWhenSupportedByHost()
    {
        var link = Path.Combine(_root, "candidate-link");
        try
        {
            Directory.CreateSymbolicLink(link, Path.Combine(_root, "candidate"));
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or PlatformNotSupportedException)
        {
            return;
        }

        var output = Path.Combine(link, "new-output.dwg");
        var error = Assert.Throws<ExactBaseXrefPolicyException>(() =>
            _policy.ValidateExtractionRequest(ExtractionRequest(output)));

        Assert.Equal(ExactBaseXrefPolicy.ReparsePointCode, error.Code);
    }

    private IpcRequest InspectionRequest() => new()
    {
        RequestId = "xref-inspection-request-001",
        SchemaVersion = ContractConstants.SchemaVersion,
        Operation = ExactBaseXrefOperationNames.Inspection,
        DrawingFullPath = _acceptedPath,
        DrawingSha256 = new string('b', 64),
        Parameters = Parameters(
            ("run_id", JsonSerializer.SerializeToElement("run-001")),
            ("source_full_path", JsonSerializer.SerializeToElement(_sourcePath)),
            ("source_revision", JsonSerializer.SerializeToElement("rev-2026-08-05-01")),
            ("inspection_expectations", InspectionExpectations()),
            ("target_role", JsonSerializer.SerializeToElement("INSPECTION_HOST"))),
        Approval = null
    };

    private IpcRequest ExtractionRequest(string? outputPath = null) => new()
    {
        RequestId = "xref-extraction-request-001",
        SchemaVersion = ContractConstants.SchemaVersion,
        Operation = ExactBaseXrefOperationNames.Extraction,
        DrawingFullPath = _candidateInputPath,
        DrawingSha256 = new string('b', 64),
        Parameters = Parameters(
            ("run_id", JsonSerializer.SerializeToElement("run-001")),
            ("source_full_path", JsonSerializer.SerializeToElement(_sourcePath)),
            ("source_revision", JsonSerializer.SerializeToElement("rev-2026-08-05-01")),
            ("inspection_expectations", InspectionExpectations()),
            ("extraction_plan", ExtractionPlan()),
            ("target_role", JsonSerializer.SerializeToElement("DISPOSABLE_CANDIDATE")),
            ("candidate_output_path", JsonSerializer.SerializeToElement(outputPath ?? _candidateOutputPath))),
        Approval = JsonSerializer.SerializeToElement(new
        {
            reference = "approval-example-001",
            status = "APPROVED"
        })
    };

    private JsonElement InspectionExpectations() => JsonSerializer.SerializeToElement(new
    {
        source = new
        {
            source_id = "base-vehicle-001",
            revision = "rev-2026-08-05-01",
            sha256 = new string('a', 64)
        },
        identity = new { vehicle = "vehicle-001", model = "model-x" },
        critical_dimensions = new[]
        {
            new { control = "wheelbase", target = 2750.0, tolerance = 1.0, unit = "mm" },
            new { control = "track", target = 1600.0, tolerance = 1.0, unit = "mm" },
            new { control = "chassis", target = 4200.0, tolerance = 2.0, unit = "mm" },
            new { control = "cabin", target = 1850.0, tolerance = 2.0, unit = "mm" },
            new { control = "axle", target = 1200.0, tolerance = 1.0, unit = "mm" }
        },
        xref = new { name = "BASE_XREF" },
        components = new[]
        {
            new
            {
                component_type = "BLOCK",
                logical_component_id = "chassis-main",
                provenance = "REUSED_FROM_BASE_CAD",
                source_block = "CHASSIS_MAIN",
                source_handle = "A1B2",
                source_layer = "BODY"
            },
            new
            {
                component_type = "BLOCK",
                logical_component_id = "cabin-main",
                provenance = "REUSED_FROM_BASE_CAD",
                source_block = "CABIN_MAIN",
                source_handle = "C3D4",
                source_layer = "BODY"
            }
        }
    });

    private JsonElement ExtractionPlan() => JsonSerializer.SerializeToElement(new
    {
        approval = new { reference = "approval-example-001", status = "APPROVED" },
        base_source = new
        {
            relative_path = "approved/base-vehicle.dwg",
            revision = "rev-2026-08-05-01",
            sha256 = new string('a', 64),
            source_id = "base-vehicle-001"
        },
        components = new[]
        {
            PlanComponent("chassis-main", "A1B2", "CHASSIS_MAIN", 0.0),
            PlanComponent("cabin-main", "C3D4", "CABIN_MAIN", 2.5)
        },
        impacted_views = new[]
        {
            new { identity = "model-space", name = "Model" },
            new { identity = "layout-001", name = "Layout1" }
        },
        inspection_id = "inspection-001",
        plan_id = "extraction-plan-001",
        provenance = "REUSED_FROM_BASE_CAD",
        request_id = "xref-inspection-request-001",
        run_id = "run-001",
        schema_version = "exact-base-xref-extraction-plan-1.0",
        source_revision = "rev-2026-08-05-01",
        target_drawing_sha256 = new string('b', 64),
        transform_policy = "LOCAL_TRANSLATION_ROTATION_UNIFORM_SCALE_ONLY"
    });

    private static object PlanComponent(
        string logicalId,
        string handle,
        string block,
        double rotation) => new
    {
        bounding = new
        {
            min = new { x = 0.0, y = -1.0, z = 0.0 },
            max = new { x = 1.0, y = 1.0, z = 1.0 }
        },
        component_type = "BLOCK",
        logical_component_id = logicalId,
        provenance = "REUSED_FROM_BASE_CAD",
        source_block = block,
        source_handle = handle,
        source_layer = "BODY",
        transform = new
        {
            rotation_degrees = rotation,
            translation = new { x = 0.0, y = 0.0, z = 0.0 },
            uniform_scale = 1.0
        }
    };

    private static Dictionary<string, JsonElement> Parameters(
        params (string Name, JsonElement Value)[] values) =>
        values.ToDictionary(value => value.Name, value => value.Value, StringComparer.Ordinal);

    public void Dispose()
    {
        if (Directory.Exists(_root))
        {
            Directory.Delete(_root, recursive: true);
        }
    }
}
