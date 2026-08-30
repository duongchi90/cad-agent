using System.Text.Json;
using System.Security.Cryptography;
using CadAgent.AutoCAD2027.Commands;
using CadAgent.AutoCAD2027.Drawing;
using CadAgent.AutoCAD2027.DrawingSetup;
using CadAgent.AutoCAD2027.Ipc;
using CadAgent.AutoCAD2027.Mechanical;
using CadAgent.AutoCAD2027.Review;
using CadAgent.AutoCAD2027.Tests.DrawingSetup;
using Xunit;

namespace CadAgent.AutoCAD2027.Tests.Ipc;

public sealed class OperationDispatcherTests
{
    [Fact]
    public void ExactBaseXrefInspectionRoutesFreshReadOnlySnapshotToResult()
    {
        var fixture = InspectionDispatcherFixture();
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = fixture.TargetPath,
            ExactBaseXrefInspection = InspectionSnapshot(fixture.TargetPath)
        };
        var dispatcher = CreateDispatcher(gateway, exactBaseXrefPolicy: fixture.Policy);

        try
        {
            var result = dispatcher.Dispatch(fixture.Request);

            Assert.True(result.Success);
            Assert.Equal("exact_base_xref_inspection", result.Operation);
            Assert.False(result.Changed);
            Assert.Empty(result.EntityHandles!);
            Assert.Equal(fixture.TargetPath, result.DrawingFullPath);
            Assert.Empty(result.Errors!);
            Assert.Equal(1, gateway.ReadExactBaseXrefInspectionCallCount);
            Assert.Equal("exact-base-xref-inspection-1.0", result.Payload!["schema_version"].GetString());
            Assert.False(result.Payload["changed"].GetBoolean());
            Assert.True(result.Payload["eligible"].GetBoolean());
        }
        finally
        {
            Directory.Delete(fixture.Root, recursive: true);
        }
    }

    [Fact]
    public void ExactBaseXrefInspectionGatewayFailureReturnsClosedFailure()
    {
        var fixture = InspectionDispatcherFixture();
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = fixture.TargetPath,
            ExactBaseXrefInspection = ExactBaseXrefInspectionSnapshot.Unavailable(
                "S3B_LIVE_UNAVAILABLE")
        };

        try
        {
            var result = CreateDispatcher(gateway, exactBaseXrefPolicy: fixture.Policy)
                .Dispatch(fixture.Request);

            Assert.False(result.Success);
            Assert.False(result.Changed);
            Assert.Empty(result.EntityHandles!);
            Assert.Empty(result.Payload!);
            Assert.Contains("S3B_LIVE_UNAVAILABLE", result.Errors!);
            Assert.Equal(1, gateway.ReadExactBaseXrefInspectionCallCount);
        }
        finally
        {
            Directory.Delete(fixture.Root, recursive: true);
        }
    }

    [Fact]
    public void ExactBaseXrefExtractionNeverUsesRunIdAsFreshPreflight()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\temp\candidate-input.dwg"
        };
        var dispatcher = CreateDispatcher(gateway);

        var result = dispatcher.Dispatch(ExactBaseXrefExtractionRequest());

        Assert.False(result.Success);
        Assert.Equal("exact_base_xref_extraction", result.Operation);
        Assert.False(result.Changed);
        Assert.Empty(result.EntityHandles!);
        Assert.Contains(result.Errors!, error => error.Contains("S3B_", StringComparison.Ordinal));
        Assert.Equal(0, gateway.ReadEntitiesCallCount);
    }

    [Fact]
    public void ExactBaseXrefExtractionRoutesFreshCandidateSnapshotToResult()
    {
        var fixture = ExtractionDispatcherFixture();
        try
        {
            var gateway = new StubDrawingGateway
            {
                ActiveDocumentFullPath = fixture.InputPath,
                ExactBaseXrefExtraction = new ExactBaseXrefExtractionSnapshot
                {
                    Success = true,
                    DrawingFullPath = fixture.InputPath,
                    Changed = true,
                    EntityHandles = new[] { "E001" },
                    Evidence = new ExactBaseXrefExtractionEvidence
                    {
                        AcceptedTargetOverwrite = false,
                        CandidateChangedDuringOperation = true,
                        CandidateInputPath = fixture.InputPath,
                        CandidateInputSha256 = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
                        CandidateOutputPath = fixture.OutputPath,
                        CandidateOutputSha256 = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
                        Components = new[]
                        {
                            new ExactBaseXrefExtractionComponentEvidence
                            {
                                CandidateHandle = "E001",
                                LogicalComponentId = "chassis-main",
                                Provenance = ExactBaseXrefOperationNames.ReusedFromBaseCad,
                                SourceBlock = "CHASSIS_MAIN",
                                SourceHandle = "A1B2",
                                SourceLayer = "BODY",
                                SourceRevision = "rev-2026-08-05-01",
                                SourceSha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                                Transform = new ExactBaseXrefTransform
                                {
                                    RotationDegrees = 0,
                                    Translation = new ExactBaseXrefPoint { X = 0, Y = 0, Z = 0 },
                                    UniformScale = 1
                                }
                            }
                        },
                        LivePreflight = new ExactBaseXrefLivePreflightEvidence
                        {
                            DbmodBefore = 0,
                            DbmodAfter = 0,
                            Eligible = true,
                            EvidenceSha256 = "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
                            InspectionId = "inspection-001",
                            SourceSha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                            TargetDrawingSha256 = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
                            Xref = new ExactBaseXrefLiveXref
                            {
                                Name = "BASE_XREF",
                                ReadOnly = true,
                                Status = "INSPECTED"
                            }
                        },
                        PlanId = "extraction-plan-001",
                        RequestId = "xref-extraction-request-001",
                        RunId = "run-001",
                        SavePerformed = true,
                        SourceHandleToCandidateHandle = new[]
                        {
                            new ExactBaseXrefHandleMapping { SourceHandle = "A1B2", CandidateHandle = "E001" }
                        },
                        SourceRevision = "rev-2026-08-05-01",
                        SourceSha256Before = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                        SourceSha256After = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                    }
                }
            };
            var dispatcher = CreateDispatcher(gateway, exactBaseXrefPolicy: fixture.Policy);

            var result = dispatcher.Dispatch(fixture.Request);

            Assert.True(result.Success);
            Assert.True(result.Changed);
            Assert.Equal(new[] { "E001" }, result.EntityHandles);
            Assert.Equal(1, gateway.ExtractExactBaseXrefCallCount);
            Assert.False(result.Payload!["accepted_target_overwrite"].GetBoolean());
            Assert.False(result.Payload["source_mutated"].GetBoolean());
            Assert.Equal("exact-base-xref-extraction-result-1.0", result.Payload["schema_version"].GetString());
        }
        finally
        {
            Directory.Delete(fixture.Root, recursive: true);
        }
    }

    [Fact]
    public void HealthReturnsTheActiveDocumentAndPreservesRequestId()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\drawings\sample.dwg"
        };
        var dispatcher = CreateDispatcher(gateway);

        var result = dispatcher.Dispatch(Request("health", "health-request", null, Parameters()));

        Assert.True(result.Success);
        Assert.Equal("health-request", result.RequestId);
        Assert.Equal("health", result.Operation);
        Assert.Equal(@"C:\drawings\sample.dwg", result.DrawingFullPath);
        Assert.False(result.Changed);
        Assert.Empty(result.Errors!);
        Assert.Equal("1.0.0", result.Payload!["plugin_version"].GetString());
        Assert.True(result.Payload["ipc_readable"].GetBoolean());
        Assert.True(result.Payload["ipc_writable"].GetBoolean());
    }

    [Fact]
    public void HealthReturnsTheExactExecutingPluginBinaryIdentity()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\drawings\sample.dwg"
        };
        var dispatcherAssemblyPath = typeof(OperationDispatcher).Assembly.Location;
        var expectedSha256 = Convert.ToHexString(
            SHA256.HashData(File.ReadAllBytes(dispatcherAssemblyPath)))
            .ToLowerInvariant();

        var result = CreateDispatcher(gateway).Dispatch(
            Request("health", "health-identity-request", null, Parameters()));

        Assert.True(result.Success);
        Assert.Equal(
            Path.GetFullPath(dispatcherAssemblyPath),
            result.Payload!["plugin_binary_path"].GetString());
        Assert.Equal(expectedSha256, result.Payload["plugin_binary_sha256"].GetString());
    }

    [Fact]
    public void HealthDoesNotAcceptCallerSuppliedPluginHash()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\drawings\sample.dwg"
        };
        var callerSuppliedHash = new string('0', 64);

        var result = CreateDispatcher(gateway).Dispatch(
            Request(
                "health",
                "health-spoof-request",
                null,
                Parameters((
                    "plugin_binary_sha256",
                    JsonSerializer.SerializeToElement(callerSuppliedHash)))));

        Assert.False(result.Success);
        Assert.Contains(
            result.Errors!,
            error => error.Contains("health parameters must be an empty object", StringComparison.Ordinal));
        Assert.False(result.Payload!.ContainsKey("plugin_binary_sha256"));
    }

    [Fact]
    public void LoadedPluginIdentityRejectsMissingBinary()
    {
        var missingPath = Path.Combine(
            Path.GetTempPath(),
            "cadagent-missing-plugin-" + Guid.NewGuid().ToString("N") + ".dll");

        var exception = Assert.Throws<InvalidOperationException>(
            () => LoadedPluginIdentity.CaptureBinary(missingPath));

        Assert.Contains("does not exist", exception.Message, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void ReviewPreservesRequestAndOperationIds()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\drawings\sample.dwg",
            Entities = new[] { Entity("A1", "LINE") }
        };
        var dispatcher = CreateDispatcher(gateway);

        var result = dispatcher.Dispatch(Request(
            "review",
            "review-request",
            @"C:\drawings\sample.dwg",
            Parameters(("handles", JsonSerializer.SerializeToElement(new[] { "A1" })))));

        Assert.True(result.Success);
        Assert.Equal("review-request", result.RequestId);
        Assert.Equal("review", result.Operation);
        Assert.Equal(new[] { "A1" }, result.EntityHandles);
    }

    [Fact]
    public void ReviewRejectsAFullPathDocumentMismatchBeforeReadingEntities()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\other\sample.dwg",
            Entities = new[] { Entity("A1", "LINE") }
        };
        var dispatcher = CreateDispatcher(gateway);

        var result = dispatcher.Dispatch(Request(
            "review",
            "mismatch-request",
            @"C:\drawings\sample.dwg",
            Parameters(("handles", JsonSerializer.SerializeToElement(new[] { "A1" })))));

        Assert.False(result.Success);
        Assert.Contains(result.Errors!, error => error.Contains("full path", StringComparison.OrdinalIgnoreCase));
        Assert.Equal(0, gateway.ReadEntitiesCallCount);
    }

    [Fact]
    public void MechanicalBomReturnsSortedReadOnlyComponents()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\temp\bom.dxf"
        };
        var mechanical = new FakeMechanicalAdapter(
            new[]
            {
                Component(
                    "A0",
                    "SECOND"),
                Component(
                    "2F",
                    "FIRST",
                    Attribute("tag ", "B"),
                    Attribute(" TAG", "A"),
                    Attribute("QTY", "2"))
            });
        var dispatcher = CreateDispatcher(gateway, mechanicalAdapter: mechanical);

        var result = dispatcher.Dispatch(Request(
            "mechanical_bom",
            "bom-request",
            @"C:\temp\bom.dxf",
            Parameters()));

        Assert.True(result.Success);
        Assert.Equal("mechanical_bom", result.Operation);
        Assert.False(result.Changed);
        Assert.Equal(new[] { "2F", "A0" }, result.EntityHandles);
        Assert.Equal(2, result.Payload!["component_count"].GetInt32());

        var components = result.Payload["components"].EnumerateArray().ToArray();
        Assert.Equal(new[] { "2F", "A0" }, components.Select(component => component.GetProperty("handle").GetString()));
        Assert.Equal("FIRST", components[0].GetProperty("block_name").GetString());
        Assert.Equal(
            new[] { "QTY:2", "TAG:A", "TAG:B" },
            components[0]
                .GetProperty("attributes")
                .EnumerateArray()
                .Select(attribute => $"{attribute.GetProperty("tag").GetString()}:{attribute.GetProperty("value").GetString()}"));
        Assert.Empty(components[1].GetProperty("attributes").EnumerateArray());
        Assert.Equal(1, mechanical.ExecuteCallCount);
    }

    [Fact]
    public void MechanicalBomRejectsAFullPathDocumentMismatchBeforeReadingMechanicalGateway()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\other\bom.dxf"
        };
        var mechanical = new FakeMechanicalAdapter(Array.Empty<MechanicalComponentSnapshot>());
        var dispatcher = CreateDispatcher(gateway, mechanicalAdapter: mechanical);

        var result = dispatcher.Dispatch(Request(
            "mechanical_bom",
            "mismatch-bom-request",
            @"C:\temp\bom.dxf",
            Parameters()));

        Assert.False(result.Success);
        Assert.Contains(result.Errors!, error => error.Contains("full path", StringComparison.OrdinalIgnoreCase));
        Assert.Equal(0, mechanical.ExecuteCallCount);
    }

    [Fact]
    public void DrawingSetupAuditReturnsAReadOnlySnapshotForTheExactActivePath()
    {
        var path = @"C:\temp\setup-lite.dwg";
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = path,
            DrawingSetup = DrawingSetupFixtures.VerifiedSnapshot(path)
        };

        var result = CreateDispatcher(gateway).Dispatch(Request(
            "drawing_setup_audit",
            "setup-lite-001",
            path,
            Parameters()));

        Assert.True(result.Success);
        Assert.Equal("drawing_setup_audit", result.Operation);
        Assert.Equal(path, result.DrawingFullPath);
        Assert.False(result.Changed);
        Assert.Empty(result.EntityHandles!);
        Assert.Empty(result.Warnings!);
        Assert.Empty(result.Errors!);
        Assert.False(result.Payload!["changed"].GetBoolean());
        Assert.Equal(1, gateway.ReadDrawingSetupCallCount);
    }

    [Fact]
    public void DrawingSetupAuditRejectsParametersBeforeReadingTheDrawing()
    {
        var path = @"C:\temp\setup-lite.dwg";
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = path,
            DrawingSetup = DrawingSetupFixtures.VerifiedSnapshot(path)
        };

        var result = CreateDispatcher(gateway).Dispatch(Request(
            "drawing_setup_audit",
            "setup-lite-parameters",
            path,
            Parameters(("mutate", JsonSerializer.SerializeToElement(true)))));

        Assert.False(result.Success);
        Assert.Contains(result.Errors!, error => error.Contains("empty", StringComparison.OrdinalIgnoreCase));
        Assert.Equal(0, gateway.ReadDrawingSetupCallCount);
    }

    [Fact]
    public void DrawingSetupAuditRejectsSameNameUnderAnotherDirectoryBeforeReadingTheDrawing()
    {
        var activePath = @"C:\approved\setup-lite.dwg";
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = activePath,
            DrawingSetup = DrawingSetupFixtures.VerifiedSnapshot(activePath)
        };

        var result = CreateDispatcher(gateway).Dispatch(Request(
            "drawing_setup_audit",
            "setup-lite-mismatch",
            @"C:\other\setup-lite.dwg",
            Parameters()));

        Assert.False(result.Success);
        Assert.Contains(result.Errors!, error => error.Contains("full path", StringComparison.OrdinalIgnoreCase));
        Assert.Equal(0, gateway.ReadDrawingSetupCallCount);
    }

    [Fact]
    public void VisualEvidenceExportMapsTheReadOnlyGatewayAndPayloadWithoutMutationAuthority()
    {
        const string drawingHash = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
        const string mutationHash = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
        const string manifestHash = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc";
        const string sessionHash = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd";
        var path = @"C:\drawings\sample.dwg";
        var region = JsonDocument.Parse(
            "{\"model_bbox_mm\":[0,0,2400,2200],\"pixel_size\":[1600,1200],\"background\":\"WHITE\",\"include_layers\":[\"CABIN\"],\"exclude_layers\":[]}").RootElement;
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = path,
            VisualEvidence = new VisualEvidenceSnapshot(
                path,
                path,
                "RUN-001",
                "EVIDENCE-001",
                "SIDE-CABIN",
                drawingHash,
                drawingHash,
                0,
                0,
                mutationHash,
                manifestHash,
                VisualEvidenceProjection.CanonicalRegionConfigSha256(region),
                sessionHash,
                sessionHash,
                true,
                new DateTimeOffset(2026, 8, 4, 12, 0, 0, TimeSpan.Zero),
                new[]
                {
                    new EvidenceArtifactDescriptor("render:cad-render.png", "render", "artifacts/visual-request/cad-render.png", drawingHash, 2, "image/png", 1600, 1200),
                    new EvidenceArtifactDescriptor("entity-map:entities.json", "entity-map", "artifacts/visual-request/entities.json", mutationHash, 2, "application/json"),
                    new EvidenceArtifactDescriptor("measurements:measurements.json", "measurements", "artifacts/visual-request/measurements.json", manifestHash, 2, "application/json")
                },
                false,
                Array.Empty<string>())
        };
        var result = CreateDispatcher(gateway).Dispatch(new IpcRequest
        {
            RequestId = "visual-request",
            SchemaVersion = ContractConstants.SchemaVersion,
            Operation = "visual_evidence_export",
            DrawingFullPath = path,
            DrawingSha256 = drawingHash,
            Parameters = Parameters(
                ("run_id", JsonSerializer.SerializeToElement("RUN-001")),
                ("evidence_id", JsonSerializer.SerializeToElement("EVIDENCE-001")),
                ("region_id", JsonSerializer.SerializeToElement("SIDE-CABIN")),
                ("latest_mutation_sha256", JsonSerializer.SerializeToElement(mutationHash)),
                ("visual_run_manifest_sha256", JsonSerializer.SerializeToElement(manifestHash)),
                ("artifact_policy_version", JsonSerializer.SerializeToElement(VisualEvidenceArtifactPolicy.Version)),
                ("artifact_directory", JsonSerializer.SerializeToElement("artifacts/visual-request")),
                ("region", region),
                ("measurements", JsonSerializer.SerializeToElement(Array.Empty<object>())),
                ("datum_bindings", JsonSerializer.SerializeToElement(Array.Empty<object>()))
                ),
            Approval = null
        });

        Assert.True(result.Success);
        Assert.Equal("visual_evidence_export", result.Operation);
        Assert.False(result.Changed);
        Assert.Empty(result.EntityHandles!);
        Assert.Equal(mutationHash, result.Payload!["latest_mutation_sha256"].GetString());
        Assert.Equal(1, gateway.ReadVisualEvidenceCallCount);
    }

    [Fact]
    public void NativeRenderEvidenceDelegatesThroughTheExistingDrawingGateway()
    {
        var path = @"C:\drawings\sample.dwg";
        var requestId = "render-request-001";
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = path,
            NativeRenderEvidence = NativeRenderSnapshot(path, requestId)
        };

        var result = CreateDispatcher(gateway).Dispatch(Request(
            "native_render_evidence",
            requestId,
            path,
            NativeRenderParameters(),
            new string('a', 64)));

        Assert.True(result.Success);
        Assert.Equal("native_render_evidence", result.Operation);
        Assert.False(result.Changed);
        Assert.Empty(result.EntityHandles!);
        Assert.Empty(result.Errors!);
        Assert.Equal("AUTOCAD_NATIVE", result.Payload!["renderer"].GetString());
        Assert.Equal(
            "native-render/render-request-001/artifact.png",
            result.Payload["artifact"].GetProperty("relative_path").GetString());
        Assert.True(ContractValidator.ValidateResult(result).IsValid);
        Assert.Equal(0, gateway.ReadEntitiesCallCount);
        Assert.Equal(0, gateway.ReadDrawingSetupCallCount);
        Assert.Equal(0, gateway.ReadVisualEvidenceCallCount);
        Assert.Equal(1, gateway.ReadNativeRenderEvidenceCallCount);
    }

    [Fact]
    public void NativeRenderEvidenceGatewayFailureReturnsAnEmptyPayload()
    {
        var path = @"C:\drawings\sample.dwg";
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = path,
            NativeRenderException = new InvalidOperationException("NATIVE_RENDER_DEVICE_UNAVAILABLE")
        };

        var result = CreateDispatcher(gateway).Dispatch(Request(
            "native_render_evidence",
            "render-request-failure",
            path,
            NativeRenderParameters(),
            new string('a', 64)));

        Assert.False(result.Success);
        Assert.False(result.Changed);
        Assert.Empty(result.EntityHandles!);
        Assert.Empty(result.Payload!);
        Assert.Contains("NATIVE_RENDER_DEVICE_UNAVAILABLE", result.Errors!);
        Assert.Equal(1, gateway.ReadNativeRenderEvidenceCallCount);
    }

    [Theory]
    [InlineData("background")]
    [InlineData("dpi")]
    [InlineData("fit_to_paper")]
    [InlineData("paper_size")]
    [InlineData("plot_style")]
    public void NativeRenderEvidenceRejectsReturnedRenderOptionsThatDoNotMatchTheRequest(
        string mismatchedField)
    {
        var path = @"C:\drawings\sample.dwg";
        var requestId = "render-request-001";
        var mismatchedOptions = new NativeRenderOptions(
            mismatchedField == "background" ? "black" : "white",
            mismatchedField == "dpi" ? 600 : 300,
            mismatchedField == "fit_to_paper" ? false : true,
            mismatchedField == "paper_size" ? "A3" : "A4",
            mismatchedField == "plot_style" ? "acad.ctb" : "monochrome.ctb");
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = path,
            NativeRenderEvidence = NativeRenderSnapshot(path, requestId) with
            {
                RenderOptions = mismatchedOptions
            }
        };

        var result = CreateDispatcher(gateway).Dispatch(Request(
            "native_render_evidence",
            requestId,
            path,
            NativeRenderParameters(),
            new string('a', 64)));

        AssertNativeRenderBoundaryFailure(result);
    }

    [Fact]
    public void NativeRenderEvidenceRejectsAnArtifactPathOutsideTheRequestOwner()
    {
        var path = @"C:\drawings\sample.dwg";
        var requestId = "render-request-001";
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = path,
            NativeRenderEvidence = NativeRenderSnapshot(path, requestId) with
            {
                Artifact = NativeRenderSnapshot(path, requestId).Artifact with
                {
                    RelativePath = "native-render/another-request/artifact.png"
                }
            }
        };

        var result = CreateDispatcher(gateway).Dispatch(Request(
            "native_render_evidence",
            requestId,
            path,
            NativeRenderParameters(),
            new string('a', 64)));

        AssertNativeRenderBoundaryFailure(result);
    }

    [Fact]
    public void MechanicalBomUsesUnavailableDefaultNoOpAdapter()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\temp\bom.dxf"
        };
        var dispatcher = CreateDispatcher(gateway);

        var result = dispatcher.Dispatch(Request(
            "mechanical_bom",
            "no-op-bom-request",
            @"C:\temp\bom.dxf",
            Parameters()));

        Assert.False(result.Success);
        Assert.Contains(result.Errors!, error => error.Contains("not supported", StringComparison.OrdinalIgnoreCase));
        Assert.Empty(result.EntityHandles!);
    }

    [Fact]
    public void MechanicalBomInvalidParametersBlockAdapterAndGatewayExecution()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\temp\bom.dxf"
        };
        var mechanicalGateway = new RecordingMechanicalGateway(
            new[] { Component("2F", "COMP_FRAME") });
        var mechanical = new ManagedMechanicalAdapter(mechanicalGateway);
        var dispatcher = CreateDispatcher(gateway, mechanicalAdapter: mechanical);

        var result = dispatcher.Dispatch(Request(
            "mechanical_bom",
            "invalid-bom-request",
            @"C:\temp\bom.dxf",
            Parameters(("filter", JsonSerializer.SerializeToElement("COMP_FRAME")))));

        Assert.False(result.Success);
        Assert.Contains(result.Errors!, error => error.Contains("empty", StringComparison.OrdinalIgnoreCase));
        Assert.Equal(0, mechanicalGateway.ReadCallCount);
    }

    [Fact]
    public void MechanicalBomPropagatesGatewayWarningsThroughTheT02Boundary()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\temp\bom.dxf"
        };
        var mechanicalWarnings = new List<string>();
        var mechanicalGateway = new WarningingMechanicalGateway(
            mechanicalWarnings,
            new[] { Component("2F", "COMP_FRAME") });
        var mechanical = new ManagedMechanicalAdapter(mechanicalGateway);
        var dispatcher = CreateDispatcher(
            gateway,
            mechanicalAdapter: mechanical,
            mechanicalWarnings: mechanicalWarnings);

        var result = dispatcher.Dispatch(Request(
            "mechanical_bom",
            "warning-bom-request",
            @"C:\temp\bom.dxf",
            Parameters()));

        Assert.True(result.Success);
        Assert.Contains(result.Warnings!, warning => warning.Contains("direct attribute", StringComparison.OrdinalIgnoreCase));
        Assert.Empty(result.Errors!);
    }

    [Fact]
    public void MechanicalBomPropagatesAdapterWarningsAndErrors()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\temp\bom.dxf"
        };
        var mechanical = new FakeMechanicalAdapter(
            Array.Empty<MechanicalComponentSnapshot>(),
            status: "failure",
            warnings: new[] { "mechanical warning" },
            errors: new[] { "mechanical error" });
        var dispatcher = CreateDispatcher(gateway, mechanicalAdapter: mechanical);

        var result = dispatcher.Dispatch(Request(
            "mechanical_bom",
            "warning-error-bom-request",
            @"C:\temp\bom.dxf",
            Parameters()));

        Assert.False(result.Success);
        Assert.Contains("mechanical warning", result.Warnings!);
        Assert.Contains("mechanical error", result.Errors!);
    }

    [Fact]
    public void MechanicalBomTransactionFailureBecomesFailureResult()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\temp\bom.dxf"
        };
        var mechanicalGateway = new ThrowingMechanicalGateway(
            new InvalidOperationException("mechanical transaction failed"));
        var mechanical = new ManagedMechanicalAdapter(mechanicalGateway);
        var dispatcher = CreateDispatcher(gateway, mechanicalAdapter: mechanical);

        var result = dispatcher.Dispatch(Request(
            "mechanical_bom",
            "transaction-bom-request",
            @"C:\temp\bom.dxf",
            Parameters()));

        Assert.False(result.Success);
        Assert.Contains("mechanical transaction failed", result.Errors!);
        Assert.Empty(result.EntityHandles!);
    }

    [Fact]
    public void CloseDisposableRequiresTheNonSavingDisposableGuardBeforeClosing()
    {
        var closeCalls = 0;
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\drawings\sample.dwg"
        };
        var dispatcher = CreateDispatcher(gateway, () => closeCalls++);

        var result = dispatcher.Dispatch(Request(
            "close_disposable",
            "close-request",
            @"C:\drawings\sample.dwg",
            Parameters(
                ("disposable", JsonSerializer.SerializeToElement(false)),
                ("save_changes", JsonSerializer.SerializeToElement(false)))));

        Assert.False(result.Success);
        Assert.Contains(result.Errors!, error => error.Contains("disposable", StringComparison.OrdinalIgnoreCase));
        Assert.Equal(0, closeCalls);
    }

    [Fact]
    public void UnsupportedMutationIsRejectedBeforeTheDrawingBoundary()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\drawings\sample.dwg"
        };
        var dispatcher = CreateDispatcher(gateway);

        var result = dispatcher.Dispatch(Request(
            "repair",
            "repair-request",
            @"C:\drawings\sample.dwg",
            Parameters()));

        Assert.False(result.Success);
        Assert.Contains(result.Errors!, error => error.Contains("not supported", StringComparison.OrdinalIgnoreCase));
        Assert.Equal(0, gateway.ReadEntitiesCallCount);
        Assert.Equal("repair", result.Payload!["requested_operation"].GetString());
    }

    [Fact]
    public void ExceptionsBecomeFailureResultsWithTheOriginalRequestId()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\drawings\sample.dwg",
            ExceptionToThrow = new InvalidOperationException("transaction exploded")
        };
        var dispatcher = CreateDispatcher(gateway);

        var result = dispatcher.Dispatch(Request(
            "review",
            "exception-request",
            @"C:\drawings\sample.dwg",
            Parameters(("handles", JsonSerializer.SerializeToElement(new[] { "A1" })))));

        Assert.False(result.Success);
        Assert.Equal("exception-request", result.RequestId);
        Assert.Equal("review", result.Operation);
        Assert.Contains(result.Errors!, error => error.Contains("transaction exploded", StringComparison.Ordinal));
    }

    private static OperationDispatcher CreateDispatcher(
        StubDrawingGateway gateway,
        Action? closeWithoutSaving = null,
        IMechanicalAdapter? mechanicalAdapter = null,
        ICollection<string>? mechanicalWarnings = null,
        ExactBaseXrefPolicy? exactBaseXrefPolicy = null) =>
        new(new CommandContext(
            new JsonFileStore(Path.Combine(Path.GetTempPath(), "cadagent-t06-tests", Guid.NewGuid().ToString("N"))),
            gateway,
            closeWithoutSaving ?? (() => { }),
            clock: () => new DateTimeOffset(2026, 8, 1, 12, 0, 0, TimeSpan.Zero),
            mechanicalAdapter: mechanicalAdapter,
            mechanicalWarnings: mechanicalWarnings,
            exactBaseXrefPolicy: exactBaseXrefPolicy));

    private static (IpcRequest Request, ExactBaseXrefPolicy Policy, string Root, string TargetPath)
        InspectionDispatcherFixture()
    {
        var root = Path.Combine(Path.GetTempPath(), "cadagent-s3b-inspection-dispatcher-" + Guid.NewGuid().ToString("N"));
        var sourcePath = Path.Combine(root, "source", "base-vehicle.dwg");
        var acceptedPath = Path.Combine(root, "accepted", "accepted.dwg");
        Directory.CreateDirectory(Path.GetDirectoryName(sourcePath)!);
        Directory.CreateDirectory(Path.GetDirectoryName(acceptedPath)!);
        File.WriteAllText(sourcePath, "source");
        File.WriteAllText(acceptedPath, "accepted");

        return (
            ExactBaseXrefInspectionRequest(acceptedPath, sourcePath),
            new ExactBaseXrefPolicy(new ExactBaseXrefServerConfiguration(
                root,
                acceptedPath,
                new string('b', 64),
                sourcePath,
                new string('a', 64),
                "rev-2026-08-05-01")),
            root,
            acceptedPath);
    }

    private static ExactBaseXrefInspectionSnapshot InspectionSnapshot(string drawingFullPath) => new()
    {
        Success = true,
        DrawingFullPath = drawingFullPath,
        Changed = false,
        EntityHandles = Array.Empty<string>(),
        Evidence = new ExactBaseXrefLiveInspection
        {
            BaseSource = new ExactBaseXrefPlanSource
            {
                RelativePath = "approved/base-vehicle.dwg",
                Revision = "rev-2026-08-05-01",
                Sha256 = new string('a', 64),
                SourceId = "base-vehicle-001"
            },
            SchemaVersion = "exact-base-xref-inspection-1.0",
            CaptureTimestamp = new DateTimeOffset(2026, 8, 1, 12, 0, 0, TimeSpan.Zero),
            Changed = false,
            DbmodBefore = 0,
            DbmodAfter = 0,
            Eligible = true,
            Components = new List<ExactBaseXrefLiveComponent>
            {
                new()
                {
                    ComponentType = "BLOCK",
                    LogicalComponentId = "chassis-main",
                    Provenance = ExactBaseXrefOperationNames.ReusedFromBaseCad,
                    SourceBlock = "CHASSIS_MAIN",
                    SourceHandle = "A1B2",
                    SourceLayer = "BODY",
                    Bounding = new ExactBaseXrefBounding
                    {
                        Min = new ExactBaseXrefPoint { X = 0, Y = 0, Z = 0 },
                        Max = new ExactBaseXrefPoint { X = 1, Y = 1, Z = 1 }
                    }
                }
            },
            Conflicts = new List<string>(),
            CriticalDimensions = new List<ExactBaseXrefLiveDimension>
            {
                new() { Control = "wheelbase", Observed = 2750, Status = "PASS", Target = 2750, Tolerance = 1, Unit = "mm" },
                new() { Control = "track", Observed = 1600, Status = "PASS", Target = 1600, Tolerance = 1, Unit = "mm" },
                new() { Control = "chassis", Observed = 4200, Status = "PASS", Target = 4200, Tolerance = 2, Unit = "mm" },
                new() { Control = "cabin", Observed = 1850, Status = "PASS", Target = 1850, Tolerance = 2, Unit = "mm" },
                new() { Control = "axle", Observed = 1200, Status = "PASS", Target = 1200, Tolerance = 1, Unit = "mm" }
            },
            IdentityObservations = new List<ExactBaseXrefIdentityObservation>
            {
                new() { Field = "vehicle", Observed = "vehicle-001", Status = "PASS", Target = "vehicle-001" },
                new() { Field = "model", Observed = "model-x", Status = "PASS", Target = "model-x" }
            },
            InspectionId = "inspection-001",
            RequestId = "xref-inspection-request-001",
            RunId = "run-001",
            TargetDrawingSha256 = new string('b', 64),
            Warnings = new List<string>(),
            Xref = new ExactBaseXrefLiveXref
            {
                Name = "BASE_XREF",
                ReadOnly = true,
                Status = "INSPECTED"
            }
        },
        Warnings = Array.Empty<string>(),
        Errors = Array.Empty<string>()
    };

    private static (IpcRequest Request, ExactBaseXrefPolicy Policy, string Root, string InputPath, string OutputPath)
        ExtractionDispatcherFixture()
    {
        var root = Path.Combine(Path.GetTempPath(), "cadagent-s3b-dispatcher-" + Guid.NewGuid().ToString("N"));
        var sourcePath = Path.Combine(root, "source", "base-vehicle.dwg");
        var acceptedPath = Path.Combine(root, "accepted", "accepted.dwg");
        var inputPath = Path.Combine(root, "candidate", "input.dwg");
        var outputPath = Path.Combine(root, "candidate", "output.dwg");
        Directory.CreateDirectory(Path.GetDirectoryName(sourcePath)!);
        Directory.CreateDirectory(Path.GetDirectoryName(acceptedPath)!);
        Directory.CreateDirectory(Path.GetDirectoryName(inputPath)!);
        File.WriteAllText(sourcePath, "source");
        File.WriteAllText(acceptedPath, "accepted");
        File.WriteAllText(inputPath, "candidate");

        var dimensions = new[]
        {
            new { control = "wheelbase", target = 2750.0, tolerance = 1.0, unit = "mm" },
            new { control = "track", target = 1600.0, tolerance = 1.0, unit = "mm" },
            new { control = "chassis", target = 4200.0, tolerance = 2.0, unit = "mm" },
            new { control = "cabin", target = 1850.0, tolerance = 2.0, unit = "mm" },
            new { control = "axle", target = 1200.0, tolerance = 1.0, unit = "mm" }
        };
        var component = new
        {
            component_type = "BLOCK",
            logical_component_id = "chassis-main",
            provenance = "REUSED_FROM_BASE_CAD",
            source_block = "CHASSIS_MAIN",
            source_handle = "A1B2",
            source_layer = "BODY"
        };
        var planComponent = new
        {
            component_type = component.component_type,
            logical_component_id = component.logical_component_id,
            provenance = component.provenance,
            source_block = component.source_block,
            source_handle = component.source_handle,
            source_layer = component.source_layer,
            bounding = new
            {
                min = new { x = 0.0, y = 0.0, z = 0.0 },
                max = new { x = 1.0, y = 1.0, z = 1.0 }
            },
            transform = new
            {
                rotation_degrees = 0.0,
                translation = new { x = 0.0, y = 0.0, z = 0.0 },
                uniform_scale = 1.0
            }
        };
        var expectations = new
        {
            source = new { source_id = "base-vehicle-001", revision = "rev-2026-08-05-01", sha256 = "a".PadLeft(64, 'a') },
            identity = new { vehicle = "vehicle-001", model = "model-x" },
            critical_dimensions = dimensions,
            xref = new { name = "BASE_XREF" },
            components = new[] { component }
        };
        var approval = new { reference = "approval-example-001", status = "APPROVED" };
        var plan = new
        {
            approval,
            base_source = new
            {
                relative_path = "approved/base-vehicle.dwg",
                revision = "rev-2026-08-05-01",
                sha256 = "a".PadLeft(64, 'a'),
                source_id = "base-vehicle-001"
            },
            components = new[] { planComponent },
            impacted_views = new[] { new { identity = "model-space", name = "Model" } },
            inspection_id = "inspection-001",
            plan_id = "extraction-plan-001",
            provenance = "REUSED_FROM_BASE_CAD",
            request_id = "xref-inspection-request-001",
            run_id = "run-001",
            schema_version = "exact-base-xref-extraction-plan-1.0",
            source_revision = "rev-2026-08-05-01",
            target_drawing_sha256 = "d".PadLeft(64, 'd'),
            transform_policy = ExactBaseXrefOperationNames.TransformPolicy
        };
        var request = new IpcRequest
        {
            RequestId = "xref-extraction-request-001",
            SchemaVersion = ContractConstants.SchemaVersion,
            Operation = ExactBaseXrefOperationNames.Extraction,
            DrawingFullPath = inputPath,
            DrawingSha256 = "d".PadLeft(64, 'd'),
            Parameters = new Dictionary<string, JsonElement>(StringComparer.Ordinal)
            {
                ["run_id"] = JsonSerializer.SerializeToElement("run-001"),
                ["source_full_path"] = JsonSerializer.SerializeToElement(sourcePath),
                ["source_revision"] = JsonSerializer.SerializeToElement("rev-2026-08-05-01"),
                ["inspection_expectations"] = JsonSerializer.SerializeToElement(expectations),
                ["extraction_plan"] = JsonSerializer.SerializeToElement(plan),
                ["target_role"] = JsonSerializer.SerializeToElement("DISPOSABLE_CANDIDATE"),
                ["candidate_output_path"] = JsonSerializer.SerializeToElement(outputPath)
            },
            Approval = JsonSerializer.SerializeToElement(approval)
        };
        return (
            request,
            new ExactBaseXrefPolicy(new ExactBaseXrefServerConfiguration(
                root,
                acceptedPath,
                "b".PadLeft(64, 'b'),
                sourcePath,
                "a".PadLeft(64, 'a'),
                "rev-2026-08-05-01")),
            root,
            inputPath,
            outputPath);
    }

    private static IpcRequest ExactBaseXrefInspectionRequest(
        string? drawingFullPath = null,
        string? sourceFullPath = null) => new()
    {
        RequestId = "xref-inspection-request-001",
        SchemaVersion = ContractConstants.SchemaVersion,
        Operation = ExactBaseXrefOperationNames.Inspection,
        DrawingFullPath = drawingFullPath ?? @"C:\drawings\inspection-host.dwg",
        DrawingSha256 = new string('b', 64),
        Parameters = new Dictionary<string, JsonElement>(StringComparer.Ordinal)
        {
            ["run_id"] = JsonSerializer.SerializeToElement("run-001"),
            ["source_full_path"] = JsonSerializer.SerializeToElement(
                sourceFullPath ?? @"C:\approved\base-vehicle.dwg"),
            ["source_revision"] = JsonSerializer.SerializeToElement("rev-2026-08-05-01"),
            ["inspection_expectations"] = JsonSerializer.SerializeToElement(new
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
                    }
                }
            }),
            ["target_role"] = JsonSerializer.SerializeToElement("INSPECTION_HOST")
        },
        Approval = null
    };

    private static IpcRequest ExactBaseXrefExtractionRequest() => new()
    {
        RequestId = "xref-extraction-request-001",
        SchemaVersion = ContractConstants.SchemaVersion,
        Operation = ExactBaseXrefOperationNames.Extraction,
        DrawingFullPath = @"C:\temp\candidate-input.dwg",
        DrawingSha256 = new string('b', 64),
        Parameters = new Dictionary<string, JsonElement>(StringComparer.Ordinal)
        {
            ["run_id"] = JsonSerializer.SerializeToElement("run-001"),
            ["source_full_path"] = JsonSerializer.SerializeToElement(@"C:\approved\base-vehicle.dwg"),
            ["source_revision"] = JsonSerializer.SerializeToElement("rev-2026-08-05-01"),
            ["inspection_expectations"] = JsonSerializer.SerializeToElement(new
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
                    }
                }
            }),
            ["extraction_plan"] = JsonSerializer.SerializeToElement(new
            {
                approval = new { reference = "approval-example-001", status = "APPROVED" },
                base_source = new
                {
                    relative_path = "approved/base-vehicle.dwg",
                    revision = "rev-2026-08-05-01",
                    sha256 = new string('a', 64),
                    source_id = "base-vehicle-001"
                },
                components = Array.Empty<object>(),
                impacted_views = new[] { new { identity = "model-space", name = "Model" } },
                inspection_id = "inspection-001",
                plan_id = "extraction-plan-001",
                provenance = "REUSED_FROM_BASE_CAD",
                request_id = "xref-inspection-request-001",
                run_id = "run-001",
                schema_version = "exact-base-xref-extraction-plan-1.0",
                source_revision = "rev-2026-08-05-01",
                target_drawing_sha256 = new string('b', 64),
                transform_policy = "LOCAL_TRANSLATION_ROTATION_UNIFORM_SCALE_ONLY"
            }),
            ["target_role"] = JsonSerializer.SerializeToElement("DISPOSABLE_CANDIDATE"),
            ["candidate_output_path"] = JsonSerializer.SerializeToElement(@"C:\temp\candidate-output.dwg")
        },
        Approval = JsonSerializer.SerializeToElement(new
        {
            reference = "approval-example-001",
            status = "APPROVED"
        })
    };

    private static void AssertNativeRenderBoundaryFailure(IpcResult result)
    {
        Assert.False(result.Success);
        Assert.False(result.Changed);
        Assert.Empty(result.EntityHandles!);
        Assert.Empty(result.Payload!);
        Assert.Contains(
            result.Errors!,
            error => error.Contains("native render evidence", StringComparison.OrdinalIgnoreCase));
    }

    private static IpcRequest Request(
        string operation,
        string requestId,
        string? drawingFullPath,
        Dictionary<string, JsonElement> parameters,
        string? drawingSha256 = null) =>
        new()
        {
            RequestId = requestId,
            SchemaVersion = ContractConstants.SchemaVersion,
            Operation = operation,
            DrawingFullPath = drawingFullPath,
            DrawingSha256 = drawingSha256,
            Parameters = parameters,
            Approval = null
        };

    private static Dictionary<string, JsonElement> Parameters(
        params (string Name, JsonElement Value)[] values) =>
        values.ToDictionary(value => value.Name, value => value.Value, StringComparer.Ordinal);

    private static Dictionary<string, JsonElement> NativeRenderParameters() =>
        new(StringComparer.Ordinal)
        {
            ["run_id"] = JsonSerializer.SerializeToElement("run-001"),
            ["latest_mutation_sha256"] = JsonSerializer.SerializeToElement(new string('b', 64)),
            ["visual_run_manifest_sha256"] = JsonSerializer.SerializeToElement(new string('c', 64)),
            ["layout"] = JsonSerializer.SerializeToElement(new { identity = "layout-001", name = "Layout1" }),
            ["artifact_kind"] = JsonSerializer.SerializeToElement("PNG"),
            ["render_options"] = JsonSerializer.SerializeToElement(new
            {
                background = "white",
                dpi = 300,
                fit_to_paper = true,
                paper_size = "A4",
                plot_style = "monochrome.ctb"
            }),
            ["requested_at"] = JsonSerializer.SerializeToElement("2026-08-05T08:00:00Z")
        };

    private static NativeRenderEvidenceSnapshot NativeRenderSnapshot(
        string path,
        string requestId) =>
        new(
            requestId,
            "run-001",
            new string('a', 64),
            new string('b', 64),
            new string('c', 64),
            new("layout-001", "Layout1"),
            "PNG",
            new("white", 300, true, "A4", "monochrome.ctb"),
            new(
                "native-render/render-request-001/artifact.png",
                new string('d', 64),
                2480,
                3508,
                null),
            new DateTimeOffset(2026, 8, 5, 8, 0, 3, TimeSpan.Zero),
            0,
            0,
            Array.Empty<string>());

    private static EntitySnapshot Entity(string handle, string type) =>
        new(handle, type, "0", new Dictionary<string, JsonElement>(StringComparer.Ordinal));

    private static MechanicalComponentSnapshot Component(
        string handle,
        string blockName,
        params MechanicalAttributeSnapshot[] attributes) =>
        new(handle, blockName, attributes);

    private static MechanicalAttributeSnapshot Attribute(string tag, string value) =>
        new(tag, value);

    private sealed class StubDrawingGateway : IDrawingGateway
    {
        public string? ActiveDocumentFullPath { get; init; }

        public IReadOnlyList<EntitySnapshot> Entities { get; init; } = Array.Empty<EntitySnapshot>();

        public DrawingSetupSnapshot? DrawingSetup { get; init; }

        public Exception? ExceptionToThrow { get; init; }

        public VisualEvidenceSnapshot? VisualEvidence { get; init; }

        public NativeRenderEvidenceSnapshot? NativeRenderEvidence { get; init; }

        public ExactBaseXrefInspectionSnapshot? ExactBaseXrefInspection { get; init; }

        public ExactBaseXrefExtractionSnapshot? ExactBaseXrefExtraction { get; init; }

        public Exception? NativeRenderException { get; init; }

        public int ReadEntitiesCallCount { get; private set; }

        public int ReadDrawingSetupCallCount { get; private set; }

        public int ReadVisualEvidenceCallCount { get; private set; }

        public int ReadNativeRenderEvidenceCallCount { get; private set; }

        public int ReadExactBaseXrefInspectionCallCount { get; private set; }

        public int ExtractExactBaseXrefCallCount { get; private set; }

        public IReadOnlyList<EntitySnapshot> ReadEntities(IReadOnlyCollection<string> handles)
        {
            ReadEntitiesCallCount++;
            if (ExceptionToThrow is not null)
            {
                throw ExceptionToThrow;
            }

            return Entities;
        }

        public DrawingSetupSnapshot ReadDrawingSetup()
        {
            ReadDrawingSetupCallCount++;
            return DrawingSetup
                ?? throw new InvalidOperationException("No drawing setup fixture was configured.");
        }

        public VisualEvidenceSnapshot ReadVisualEvidence(VisualEvidenceRequest request)
        {
            ReadVisualEvidenceCallCount++;
            return VisualEvidence ?? throw new NotSupportedException();
        }

        public NativeRenderEvidenceSnapshot ReadNativeRenderEvidence(NativeRenderRequest request)
        {
            ReadNativeRenderEvidenceCallCount++;
            if (NativeRenderException is not null)
            {
                throw NativeRenderException;
            }

            return NativeRenderEvidence ?? throw new NotSupportedException();
        }

        public ExactBaseXrefInspectionSnapshot ReadExactBaseXrefInspection(
            ExactBaseXrefInspectionParameters request)
        {
            ReadExactBaseXrefInspectionCallCount++;
            return ExactBaseXrefInspection
                ?? ExactBaseXrefInspectionSnapshot.Unavailable(
                    "No inspection fixture was configured.");
        }

        public ExactBaseXrefExtractionSnapshot ExtractExactBaseXref(
            ExactBaseXrefExtractionParameters request,
            string requestId)
        {
            ExtractExactBaseXrefCallCount++;
            return ExactBaseXrefExtraction
                ?? ExactBaseXrefExtractionSnapshot.Failure(
                    ActiveDocumentFullPath,
                    new[] { "No extraction fixture was configured." });
        }
    }

    private sealed class FakeMechanicalAdapter : IMechanicalAdapter
    {
        private readonly IReadOnlyList<MechanicalComponentSnapshot> _components;
        private readonly string _status;
        private readonly IReadOnlyList<string> _warnings;
        private readonly IReadOnlyList<string> _errors;

        public FakeMechanicalAdapter(
            IReadOnlyList<MechanicalComponentSnapshot> components,
            string status = "success",
            IReadOnlyList<string>? warnings = null,
            IReadOnlyList<string>? errors = null)
        {
            _components = components;
            _status = status;
            _warnings = warnings ?? Array.Empty<string>();
            _errors = errors ?? Array.Empty<string>();
        }

        public int ExecuteCallCount { get; private set; }

        public bool IsAvailable => true;

        public MechanicalCapabilityResult GetCapabilities() =>
            new(new[] { "mechanical_bom" });

        public MechanicalOperationResult Execute(MechanicalOperationRequest request)
        {
            ExecuteCallCount++;
            return new(
                _status,
                request.OperationName,
                false,
                _warnings,
                _errors,
                _components);
        }
    }

    private sealed class RecordingMechanicalGateway : IMechanicalDrawingGateway
    {
        private readonly IReadOnlyList<MechanicalComponentSnapshot> _components;

        public RecordingMechanicalGateway(IReadOnlyList<MechanicalComponentSnapshot> components)
        {
            _components = components;
        }

        public int ReadCallCount { get; private set; }

        public IReadOnlyList<MechanicalComponentSnapshot> ReadMechanicalComponents()
        {
            ReadCallCount++;
            return _components;
        }
    }

    private sealed class WarningingMechanicalGateway : IMechanicalDrawingGateway
    {
        private readonly ICollection<string> _warnings;
        private readonly IReadOnlyList<MechanicalComponentSnapshot> _components;

        public WarningingMechanicalGateway(
            ICollection<string> warnings,
            IReadOnlyList<MechanicalComponentSnapshot> components)
        {
            _warnings = warnings;
            _components = components;
        }

        public IReadOnlyList<MechanicalComponentSnapshot> ReadMechanicalComponents()
        {
            _warnings.Add("Skipped unreadable direct attribute on insert 2F.");
            return _components;
        }
    }

    private sealed class ThrowingMechanicalGateway : IMechanicalDrawingGateway
    {
        private readonly Exception _exception;

        public ThrowingMechanicalGateway(Exception exception)
        {
            _exception = exception;
        }

        public IReadOnlyList<MechanicalComponentSnapshot> ReadMechanicalComponents() =>
            throw _exception;
    }
}
