using System.Text.Json;
using System.Text.RegularExpressions;
using CadAgent.AutoCAD2027.Ipc;
using Xunit;

namespace CadAgent.AutoCAD2027.Tests.Ipc;

public sealed class ContractTests
{
    [Fact]
    public void RejectsUnsupportedSchemaVersion()
    {
        var request = ValidRequest() with { SchemaVersion = "9.9" };

        var validation = ContractValidator.ValidateRequest(request);

        Assert.False(validation.IsValid);
        Assert.Contains(validation.Errors, error => error.Contains("schema_version", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void RejectsEmptyRequestId()
    {
        var request = ValidRequest() with { RequestId = " " };

        var validation = ContractValidator.ValidateRequest(request);

        Assert.False(validation.IsValid);
        Assert.Contains(validation.Errors, error => error.Contains("request_id", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void RejectsRelativeDrawingPath()
    {
        var request = ValidRequest() with { DrawingFullPath = "drawings\\sample.dwg" };

        var validation = ContractValidator.ValidateRequest(request);

        Assert.False(validation.IsValid);
        Assert.Contains(validation.Errors, error => error.Contains("drawing_full_path", StringComparison.OrdinalIgnoreCase));
    }

    [Theory]
    [InlineData(@"C:\temp\x.dxf", true)]
    [InlineData(@"C:/temp/x.dxf", true)]
    [InlineData(@"\\server\share\x.dxf", true)]
    [InlineData(@"\temp\x.dxf", false)]
    public void RequestAndResultSchemasMatchOnlyWindowsAbsolutePathForms(
        string path,
        bool expected)
    {
        foreach (var schemaRelativePath in new[]
        {
            "request.schema.json",
            "result.schema.json"
        })
        {
            using var schema = JsonDocument.Parse(
                File.ReadAllText(RepositoryFile($"contracts/autocad-ipc/{schemaRelativePath}")));
            var pattern = schema.RootElement
                .GetProperty("properties")
                .GetProperty("drawing_full_path")
                .GetProperty("pattern")
                .GetString();

            Assert.NotNull(pattern);
            Assert.Equal(expected, Regex.IsMatch(path, pattern!));
        }
    }

    [Fact]
    public void RejectsUnsupportedOperation()
    {
        var request = ValidRequest() with { Operation = "repair" };

        var validation = ContractValidator.ValidateRequest(request);

        Assert.False(validation.IsValid);
        Assert.Contains(validation.Errors, error => error.Contains("operation", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void AcceptsMechanicalBomOnlyWithEmptyParameters()
    {
        var request = ValidRequest("mechanical_bom");

        var validation = ContractValidator.ValidateRequest(request);

        Assert.True(validation.IsValid);
    }

    [Fact]
    public void RejectsMechanicalBomWithUnsupportedParameters()
    {
        var request = ValidRequest("mechanical_bom") with
        {
            Parameters = new Dictionary<string, JsonElement>
            {
                ["filter"] = JsonSerializer.SerializeToElement("COMP_FRAME")
            }
        };

        var validation = ContractValidator.ValidateRequest(request);

        Assert.False(validation.IsValid);
        Assert.Contains(
            validation.Errors,
            error => error.Contains("mechanical_bom", StringComparison.OrdinalIgnoreCase)
                && error.Contains("empty", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void AcceptsDrawingSetupAuditOnlyWithEmptyParameters()
    {
        var valid = ValidRequest("drawing_setup_audit");
        var invalid = valid with
        {
            Parameters = new Dictionary<string, JsonElement>
            {
                ["mutate"] = JsonSerializer.SerializeToElement(true)
            }
        };

        Assert.True(ContractValidator.ValidateRequest(valid).IsValid);
        var validation = ContractValidator.ValidateRequest(invalid);
        Assert.False(validation.IsValid);
        Assert.Contains(
            validation.Errors,
            error => error.Contains("drawing_setup_audit", StringComparison.OrdinalIgnoreCase)
                && error.Contains("empty", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void AllowsNullDrawingPathOnlyForHealth()
    {
        var health = ValidRequest() with { DrawingFullPath = null };
        var review = ValidRequest("review") with { DrawingFullPath = null };

        Assert.True(ContractValidator.ValidateRequest(health).IsValid);
        Assert.False(ContractValidator.ValidateRequest(review).IsValid);
    }

    [Fact]
    public void RejectsInvalidDisposableParameters()
    {
        var parameters = new Dictionary<string, JsonElement>
        {
            ["disposable"] = JsonSerializer.SerializeToElement(false),
            ["save_changes"] = JsonSerializer.SerializeToElement(true)
        };
        var request = ValidRequest("close_disposable") with { Parameters = parameters };

        var validation = ContractValidator.ValidateRequest(request);

        Assert.False(validation.IsValid);
        Assert.Contains(validation.Errors, error => error.Contains("disposable", StringComparison.OrdinalIgnoreCase));
        Assert.Contains(validation.Errors, error => error.Contains("save_changes", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void RoundTripsRequestAndResultJson()
    {
        var request = ValidRequest("review") with
        {
            Parameters = new Dictionary<string, JsonElement>
            {
                ["handles"] = JsonSerializer.SerializeToElement(new[] { "AB12", "CD34" })
            },
            DrawingSha256 = new string('a', 64)
        };
        var result = new IpcResult
        {
            RequestId = request.RequestId,
            Success = true,
            Operation = request.Operation,
            DrawingFullPath = request.DrawingFullPath,
            Changed = false,
            EntityHandles = new List<string> { "AB12" },
            Warnings = new List<string>(),
            Errors = new List<string>(),
            StartedAt = DateTimeOffset.Parse("2026-08-01T00:00:00Z"),
            CompletedAt = DateTimeOffset.Parse("2026-08-01T00:00:01Z"),
            Payload = new Dictionary<string, JsonElement>
            {
                ["count"] = JsonSerializer.SerializeToElement(1)
            }
        };

        var requestCopy = ContractJson.DeserializeRequest(ContractJson.Serialize(request));
        var resultCopy = ContractJson.DeserializeResult(ContractJson.Serialize(result));

        Assert.Equal(request.RequestId, requestCopy.RequestId);
        Assert.Equal(request.Operation, requestCopy.Operation);
        Assert.Equal(request.DrawingFullPath, requestCopy.DrawingFullPath);
        Assert.Equal(request.DrawingSha256, requestCopy.DrawingSha256);
        var copiedHandles = requestCopy.Parameters!["handles"]
            .EnumerateArray()
            .Select(element => element.GetString()!)
            .ToArray();
        Assert.Equal(new[] { "AB12", "CD34" }, copiedHandles);
        Assert.Equal(result.RequestId, resultCopy.RequestId);
        Assert.Equal(result.Success, resultCopy.Success);
        Assert.Equal(result.EntityHandles!.Single(), resultCopy.EntityHandles!.Single());
        Assert.Equal(result.StartedAt, resultCopy.StartedAt);
        Assert.Equal(result.CompletedAt, resultCopy.CompletedAt);
    }

    [Fact]
    public void MechanicalBomExamplesRoundTripWithPayloadAndValidate()
    {
        var request = ContractJson.DeserializeRequest(File.ReadAllText(
            RepositoryFile("contracts/autocad-ipc/examples/mechanical-bom-request.json")));
        var result = ContractJson.DeserializeResult(File.ReadAllText(
            RepositoryFile("contracts/autocad-ipc/examples/mechanical-bom-result.json")));
        var requestJson = ContractJson.Serialize(request);
        var resultJson = ContractJson.Serialize(result);
        var requestCopy = ContractJson.DeserializeRequest(requestJson);
        var resultCopy = ContractJson.DeserializeResult(resultJson);

        Assert.True(ContractValidator.ValidateRequest(request).IsValid);
        Assert.True(ContractValidator.ValidateResult(result).IsValid);
        Assert.True(ContractValidator.ValidateRequest(requestCopy).IsValid);
        Assert.True(ContractValidator.ValidateResult(resultCopy).IsValid);
        Assert.Equal("mechanical_bom", requestCopy.Operation);
        Assert.Equal("mechanical_bom", resultCopy.Operation);
        Assert.Equal(request.DrawingFullPath, requestCopy.DrawingFullPath);
        Assert.Empty(requestCopy.Parameters!);
        Assert.Equal(result.DrawingFullPath, resultCopy.DrawingFullPath);
        Assert.Equal(1, resultCopy.Payload!["component_count"].GetInt32());
        var component = Assert.Single(resultCopy.Payload["components"].EnumerateArray());
        Assert.Equal("2F", component.GetProperty("handle").GetString());
        Assert.Equal("COMP_FRAME", component.GetProperty("block_name").GetString());
        Assert.Equal(
            "FRAME-001",
            Assert.Single(component.GetProperty("attributes").EnumerateArray())
                .GetProperty("value")
                .GetString());

        foreach (var schemaRelativePath in new[]
        {
            "request.schema.json",
            "result.schema.json"
        })
        {
            using var schema = JsonDocument.Parse(
                File.ReadAllText(RepositoryFile($"contracts/autocad-ipc/{schemaRelativePath}")));
            var pattern = schema.RootElement
                .GetProperty("properties")
                .GetProperty("drawing_full_path")
                .GetProperty("pattern")
                .GetString();
            Assert.NotNull(pattern);
            Assert.Matches(pattern!, requestCopy.DrawingFullPath!);
        }
    }

    [Fact]
    public void DrawingSetupAuditExamplesRoundTripWithReadOnlyPayloadAndValidate()
    {
        var request = ContractJson.DeserializeRequest(File.ReadAllText(
            RepositoryFile("contracts/autocad-ipc/examples/drawing-setup-audit-request.json")));
        var result = ContractJson.DeserializeResult(File.ReadAllText(
            RepositoryFile("contracts/autocad-ipc/examples/drawing-setup-audit-result.json")));

        Assert.True(ContractValidator.ValidateRequest(request).IsValid);
        Assert.True(ContractValidator.ValidateResult(result).IsValid);
        Assert.Equal("drawing_setup_audit", request.Operation);
        Assert.Empty(request.Parameters!);
        Assert.Equal("drawing_setup_audit", result.Operation);
        Assert.False(result.Changed);
        Assert.Empty(result.EntityHandles!);
        Assert.False(result.Payload!["changed"].GetBoolean());
        Assert.Equal(0, result.Payload["dbmod_before"].GetInt32());
        Assert.Equal(0, result.Payload["dbmod_after"].GetInt32());

        using var operationSchema = JsonDocument.Parse(File.ReadAllText(
            RepositoryFile("contracts/autocad-ipc/operations/drawing-setup-audit.schema.json")));
        Assert.False(operationSchema.RootElement.GetProperty("additionalProperties").GetBoolean());
        Assert.Equal(0, operationSchema.RootElement.GetProperty("maxProperties").GetInt32());
    }

    [Fact]
    public void RejectsAMutatingDrawingSetupAuditResult()
    {
        var source = ContractJson.DeserializeResult(File.ReadAllText(
            RepositoryFile("contracts/autocad-ipc/examples/drawing-setup-audit-result.json")));
        var result = source with
        {
            Changed = true,
            EntityHandles = new List<string> { "2F" }
        };

        var validation = ContractValidator.ValidateResult(result);

        Assert.False(validation.IsValid);
        Assert.Contains(
            validation.Errors,
            error => error.Contains("drawing_setup_audit", StringComparison.OrdinalIgnoreCase)
                && error.Contains("read-only", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void VisualEvidenceExamplesRoundTripThroughTheClosedEnvelope()
    {
        var request = ContractJson.DeserializeRequest(File.ReadAllText(
            RepositoryFile("contracts/autocad-ipc/examples/visual-evidence-export-request.json")));
        var result = ContractJson.DeserializeResult(File.ReadAllText(
            RepositoryFile("contracts/autocad-ipc/examples/visual-evidence-export-result.json")));

        Assert.True(ContractValidator.ValidateRequest(request).IsValid);
        Assert.True(ContractValidator.ValidateResult(result).IsValid);
        Assert.Equal("visual_evidence_export", request.Operation);
        Assert.Null(request.Approval);
        Assert.Equal("EV-SIDE-CABIN-001", request.Parameters!["evidence_id"].GetString());
        Assert.False(result.Changed);
        Assert.Empty(result.EntityHandles!);
        Assert.Equal(
            "2026-08-04T00:00:02Z",
            result.Payload!["captured_at_utc"].GetString());
    }

    [Fact]
    public void RejectsVisualEvidenceFieldsOutsideTheExistingRequestEnvelope()
    {
        var json = ContractJson.Serialize(ValidRequest("visual_evidence_export"));
        using var document = JsonDocument.Parse(json);
        var root = document.RootElement.EnumerateObject()
            .Where(property => property.Name != "parameters")
            .ToDictionary(property => property.Name, property => property.Value);
        root["latest_mutation_sha256"] = JsonSerializer.SerializeToElement(new string('a', 64));

        var invalidJson = JsonSerializer.Serialize(root);

        Assert.Throws<JsonException>(() => ContractJson.DeserializeRequest(invalidJson));
    }

    [Fact]
    public void RejectsVisualEvidenceWithMissingParameters()
    {
        var request = ValidRequest("visual_evidence_export") with
        {
            DrawingSha256 = new string('c', 64),
            Parameters = new Dictionary<string, JsonElement>
            {
                ["run_id"] = JsonSerializer.SerializeToElement("RUN-001")
            }
        };

        var validation = ContractValidator.ValidateRequest(request);

        Assert.False(validation.IsValid);
        Assert.Contains(validation.Errors, error => error.Contains("evidence_id", StringComparison.Ordinal));
    }

    [Fact]
    public void RejectsMutatingVisualEvidenceResult()
    {
        var result = ContractJson.DeserializeResult(File.ReadAllText(
            RepositoryFile("contracts/autocad-ipc/examples/visual-evidence-export-result.json"))) with
        {
            Changed = true,
            EntityHandles = new List<string> { "2F" }
        };

        var validation = ContractValidator.ValidateResult(result);

        Assert.False(validation.IsValid);
        Assert.Contains(
            validation.Errors,
            error => error.Contains("visual_evidence_export", StringComparison.Ordinal)
                && error.Contains("read-only", StringComparison.Ordinal));
    }

    [Fact]
    public void AllowsVisualEvidenceFailureWithoutInventingAnAcceptedPayload()
    {
        var result = ContractJson.DeserializeResult(File.ReadAllText(
            RepositoryFile("contracts/autocad-ipc/examples/visual-evidence-export-result.json"))) with
        {
            Success = false,
            Payload = new Dictionary<string, JsonElement>(StringComparer.Ordinal),
            Errors = new List<string> { "active document mismatch" }
        };

        var validation = ContractValidator.ValidateResult(result);

        Assert.True(validation.IsValid);
    }

    [Fact]
    public void AcceptsOnlyProvenanceBoundDatumMeasurementReferences()
    {
        var request = ContractJson.DeserializeRequest(File.ReadAllText(
            RepositoryFile("contracts/autocad-ipc/examples/visual-evidence-export-request.json")));
        var parameters = request.Parameters!.ToDictionary(item => item.Key, item => item.Value, StringComparer.Ordinal);
        parameters["measurements"] = JsonSerializer.SerializeToElement(new[]
        {
            new
            {
                id = "MEASURE-AXLE",
                kind = "DISTANCE",
                reference = new { type = "DATUM", id = "FRONT_AXLE_CENTER" },
                to_reference = new { type = "ENTITY", id = "PART:CABIN_OUTER" }
            }
        });
        parameters["datum_bindings"] = JsonSerializer.SerializeToElement(new[]
        {
            new
            {
                id = "FRONT_AXLE_CENTER",
                entity_handle = "A1",
                run_id = "RUN-001",
                region_id = "SIDE-CABIN",
                visual_run_manifest_sha256 = new string('b', 64),
                dimension_register_sha256 = new string('d', 64),
                dimension_id = "DIM-SIDE-001",
                approval = "DIMENSION_REGISTER_CONFIRMED"
            }
        });

        var validation = ContractValidator.ValidateRequest(request with { Parameters = parameters });

        Assert.True(validation.IsValid, string.Join("; ", validation.Errors));
    }

    [Fact]
    public void NativeRenderEvidenceRequestAcceptsOnlyTheClosedS2AParameterMapping()
    {
        var request = NativeRenderRequest();

        var validation = ContractValidator.ValidateRequest(request);

        Assert.True(validation.IsValid, string.Join("; ", validation.Errors));
    }

    [Theory]
    [InlineData("unexpected", "value")]
    [InlineData("approval", "APPROVED")]
    [InlineData("verdict", "PASS")]
    public void NativeRenderEvidenceRequestRejectsForbiddenOrUnknownFields(string name, string value)
    {
        var parameters = NativeRenderRequest().Parameters!
            .ToDictionary(item => item.Key, item => item.Value, StringComparer.Ordinal);
        parameters[name] = JsonSerializer.SerializeToElement(value);

        var validation = ContractValidator.ValidateRequest(
            NativeRenderRequest() with { Parameters = parameters });

        Assert.False(validation.IsValid);
        Assert.Contains(validation.Errors, error => error.Contains(name, StringComparison.OrdinalIgnoreCase));
    }

    [Theory]
    [InlineData("drawing_sha256", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")]
    [InlineData("artifact_kind", "JPG")]
    [InlineData("requested_at", "2026-08-05T08:00:00+01:00")]
    public void NativeRenderEvidenceRequestRejectsUnsafeOrMalformedS2AValues(string field, string value)
    {
        var request = NativeRenderRequest();
        if (field == "drawing_sha256")
        {
            request = request with { DrawingSha256 = value };
        }
        else
        {
            var parameters = request.Parameters!
                .ToDictionary(item => item.Key, item => item.Value, StringComparer.Ordinal);
            parameters[field] = JsonSerializer.SerializeToElement(value);
            request = request with { Parameters = parameters };
        }

        var validation = ContractValidator.ValidateRequest(request);

        Assert.False(validation.IsValid);
        Assert.Contains(validation.Errors, error => error.Contains(field, StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void NativeRenderEvidenceSuccessResultRequiresReadOnlyClosedPayload()
    {
        var result = NativeRenderResult(success: true);

        var validation = ContractValidator.ValidateResult(result);

        Assert.True(validation.IsValid, string.Join("; ", validation.Errors));
    }

    [Fact]
    public void NativeRenderEvidenceResultRejectsMutationClaims()
    {
        var result = NativeRenderResult(success: true) with { Changed = true };

        var validation = ContractValidator.ValidateResult(result);

        Assert.False(validation.IsValid);
        Assert.Contains(validation.Errors, error => error.Contains("read-only", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void NativeRenderEvidenceResultRejectsNegativeDbmod()
    {
        var result = NativeRenderResult(success: true);
        result.Payload!["dbmod_before"] = JsonSerializer.SerializeToElement(-1);

        var validation = ContractValidator.ValidateResult(result);

        Assert.False(validation.IsValid);
        Assert.Contains(validation.Errors, error => error.Contains("DBMOD", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void NativeRenderEvidenceSuccessExampleRoundTripsAsClosedReadOnlyResult()
    {
        var request = ContractJson.DeserializeRequest(File.ReadAllText(
            RepositoryFile("contracts/autocad-ipc/examples/native-render-evidence-request.json")));
        var result = ContractJson.DeserializeResult(File.ReadAllText(
            RepositoryFile("contracts/autocad-ipc/examples/native-render-evidence-result.json")));

        Assert.True(ContractValidator.ValidateRequest(request).IsValid);
        Assert.True(ContractValidator.ValidateResult(result).IsValid);
        Assert.True(result.Success);
        Assert.Equal("native_render_evidence", request.Operation);
        Assert.Empty(result.Errors!);
        Assert.Equal("AUTOCAD_NATIVE", result.Payload!["renderer"].GetString());
        Assert.Equal(
            "native-render/render-request-001/artifact.png",
            result.Payload["artifact"].GetProperty("relative_path").GetString());
        Assert.Empty(result.EntityHandles!);
        Assert.False(result.Changed);
    }

    [Fact]
    public void ExactBaseXrefOperationsAreAllowlistedWithClosedSchemaBranches()
    {
        using var requestSchema = JsonDocument.Parse(File.ReadAllText(
            RepositoryFile("contracts/autocad-ipc/request.schema.json")));
        using var resultSchema = JsonDocument.Parse(File.ReadAllText(
            RepositoryFile("contracts/autocad-ipc/result.schema.json")));

        foreach (var schema in new[] { requestSchema, resultSchema })
        {
            var operations = schema.RootElement
                .GetProperty("properties")
                .GetProperty("operation")
                .GetProperty("enum")
                .EnumerateArray()
                .Select(value => value.GetString())
                .ToArray();

            Assert.Contains("exact_base_xref_inspection", operations);
            Assert.Contains("exact_base_xref_extraction", operations);
        }

        Assert.Equal(
            "operations/exact-base-xref-inspection.schema.json",
            FindOperationBranch(requestSchema.RootElement, "exact_base_xref_inspection")
                .GetProperty("then")
                .GetProperty("properties")
                .GetProperty("parameters")
                .GetProperty("$ref")
                .GetString());
        Assert.Equal(
            "operations/exact-base-xref-extraction.schema.json",
            FindOperationBranch(requestSchema.RootElement, "exact_base_xref_extraction")
                .GetProperty("then")
                .GetProperty("properties")
                .GetProperty("parameters")
                .GetProperty("$ref")
                .GetString());
        Assert.Equal(
            "operations/exact-base-xref-inspection-result.schema.json",
            FindOperationBranch(resultSchema.RootElement, "exact_base_xref_inspection")
                .GetProperty("then")
                .GetProperty("allOf")[0]
                .GetProperty("then")
                .GetProperty("properties")
                .GetProperty("payload")
                .GetProperty("$ref")
                .GetString());
        Assert.Equal(
            "operations/exact-base-xref-extraction-result.schema.json",
            FindOperationBranch(resultSchema.RootElement, "exact_base_xref_extraction")
                .GetProperty("then")
                .GetProperty("allOf")[0]
                .GetProperty("then")
                .GetProperty("properties")
                .GetProperty("payload")
                .GetProperty("$ref")
                .GetString());

        using var inspectionSchema = JsonDocument.Parse(File.ReadAllText(
            RepositoryFile(
                "contracts/autocad-ipc/operations/exact-base-xref-inspection.schema.json")));
        var expectationProperties = inspectionSchema.RootElement
            .GetProperty("$defs")
            .GetProperty("inspectionExpectations")
            .GetProperty("properties")
            .EnumerateObject()
            .Select(property => property.Name)
            .ToArray();
        foreach (var forbidden in new[]
        {
            "observed", "status", "eligible", "changed", "dbmod_before",
            "dbmod_after", "live_bounds", "live_hashes", "live_timestamps"
        })
        {
            Assert.DoesNotContain(forbidden, expectationProperties);
        }
        Assert.False(
            inspectionSchema.RootElement.GetProperty("additionalProperties").GetBoolean());
        Assert.False(
            inspectionSchema.RootElement
                .GetProperty("$defs")
                .GetProperty("inspectionExpectations")
                .GetProperty("additionalProperties")
                .GetBoolean());
    }

    [Fact]
    public void ExactBaseXrefExamplesRoundTripWithClosedApprovalAndEvidenceSemantics()
    {
        var inspectionRequest = ContractJson.DeserializeRequest(File.ReadAllText(
            RepositoryFile(
                "contracts/autocad-ipc/examples/exact-base-xref-inspection.request.json")));
        var inspectionResult = ContractJson.DeserializeResult(File.ReadAllText(
            RepositoryFile(
                "contracts/autocad-ipc/examples/exact-base-xref-inspection.result.json")));
        var extractionRequest = ContractJson.DeserializeRequest(File.ReadAllText(
            RepositoryFile(
                "contracts/autocad-ipc/examples/exact-base-xref-extraction.request.json")));
        var extractionResult = ContractJson.DeserializeResult(File.ReadAllText(
            RepositoryFile(
                "contracts/autocad-ipc/examples/exact-base-xref-extraction.result.json")));

        Assert.Equal("exact_base_xref_inspection", inspectionRequest.Operation);
        Assert.Null(inspectionRequest.Approval);
        Assert.Equal("INSPECTION_HOST", inspectionRequest.Parameters!["target_role"].GetString());
        Assert.Equal("exact_base_xref_inspection", inspectionResult.Operation);
        Assert.False(inspectionResult.Changed);
        Assert.Empty(inspectionResult.EntityHandles!);
        Assert.Equal(
            "exact-base-xref-inspection-1.0",
            inspectionResult.Payload!["schema_version"].GetString());

        Assert.Equal("exact_base_xref_extraction", extractionRequest.Operation);
        var planApproval = extractionRequest.Parameters!["extraction_plan"]
            .GetProperty("approval");
        Assert.Equal("APPROVED", planApproval.GetProperty("status").GetString());
        Assert.Equal(
            planApproval.GetProperty("reference").GetString(),
            extractionRequest.Approval!.Value.GetProperty("reference").GetString());
        Assert.Equal(
            planApproval.GetProperty("status").GetString(),
            extractionRequest.Approval!.Value.GetProperty("status").GetString());
        Assert.Equal(
            "DISPOSABLE_CANDIDATE",
            extractionRequest.Parameters["target_role"].GetString());

        Assert.Equal("exact_base_xref_extraction", extractionResult.Operation);
        Assert.True(extractionResult.Changed);
        Assert.Equal(new[] { "E001", "E002" }, extractionResult.EntityHandles);
        Assert.Equal(
            "exact-base-xref-extraction-result-1.0",
            extractionResult.Payload!["schema_version"].GetString());
        Assert.False(extractionResult.Payload["source_mutated"].GetBoolean());
        Assert.False(extractionResult.Payload["accepted_target_overwrite"].GetBoolean());
        Assert.Equal(
            2,
            extractionResult.Payload["source_handle_to_candidate_handle"]
                .GetArrayLength());
    }

    [Fact]
    public void ExactBaseXrefResultSchemasCloseReadOnlyAndCandidateBranches()
    {
        using var resultSchema = JsonDocument.Parse(File.ReadAllText(
            RepositoryFile("contracts/autocad-ipc/result.schema.json")));

        var inspectionBranch = FindOperationBranch(
            resultSchema.RootElement,
            "exact_base_xref_inspection");
        var inspectionSuccess = inspectionBranch.GetProperty("then");
        Assert.False(
            inspectionSuccess.GetProperty("properties")
                .GetProperty("changed")
                .GetProperty("const")
                .GetBoolean());
        Assert.Equal(
            0,
            inspectionSuccess.GetProperty("properties")
                .GetProperty("entity_handles")
                .GetProperty("maxItems")
                .GetInt32());

        var inspectionPayload = inspectionSuccess
            .GetProperty("allOf")[0]
            .GetProperty("then");
        Assert.Equal(
            "operations/exact-base-xref-inspection-result.schema.json",
            inspectionPayload.GetProperty("properties")
                .GetProperty("payload")
                .GetProperty("$ref")
                .GetString());

        var extractionBranch = FindOperationBranch(
            resultSchema.RootElement,
            "exact_base_xref_extraction");
        var extractionSuccess = extractionBranch.GetProperty("then")
            .GetProperty("allOf")[0]
            .GetProperty("then");
        Assert.Equal(
            "operations/exact-base-xref-extraction-result.schema.json",
            extractionSuccess.GetProperty("properties")
                .GetProperty("payload")
                .GetProperty("$ref")
                .GetString());
        Assert.True(
            extractionSuccess.GetProperty("properties")
                .GetProperty("changed")
                .GetProperty("const")
                .GetBoolean());
        Assert.Equal(
            1,
            extractionSuccess.GetProperty("properties")
                .GetProperty("entity_handles")
                .GetProperty("minItems")
                .GetInt32());

        var extractionFailure = extractionBranch.GetProperty("then")
            .GetProperty("allOf")[1]
            .GetProperty("then");
        Assert.False(
            extractionFailure.GetProperty("properties")
                .GetProperty("changed")
                .GetProperty("const")
                .GetBoolean());
        Assert.Equal(
            0,
            extractionFailure.GetProperty("properties")
                .GetProperty("entity_handles")
                .GetProperty("maxItems")
                .GetInt32());
        Assert.Equal(
            0,
            extractionFailure.GetProperty("properties")
                .GetProperty("payload")
                .GetProperty("maxProperties")
                .GetInt32());
    }

    private static JsonElement FindOperationBranch(JsonElement schema, string operation)
    {
        return schema.GetProperty("allOf")
            .EnumerateArray()
            .Single(branch =>
                branch.GetProperty("if")
                    .GetProperty("properties")
                    .GetProperty("operation")
                    .GetProperty("const")
                    .GetString() == operation);
    }

    private static string RepositoryFile(string relativePath)
    {
        for (var directory = new DirectoryInfo(AppContext.BaseDirectory);
             directory is not null;
             directory = directory.Parent)
        {
            var candidate = Path.Combine(directory.FullName, relativePath);
            if (File.Exists(candidate))
            {
                return candidate;
            }
        }

        throw new FileNotFoundException($"Could not find repository file '{relativePath}'.");
    }

    private static IpcRequest ValidRequest(string operation = "health") => new()
    {
        RequestId = "request-123",
        SchemaVersion = ContractConstants.SchemaVersion,
        Operation = operation,
        DrawingFullPath = @"C:\temp\sample.dwg",
        DrawingSha256 = null,
        Parameters = new Dictionary<string, JsonElement>(),
        Approval = null
    };

    private static IpcRequest NativeRenderRequest() => new()
    {
        RequestId = "render-request-001",
        SchemaVersion = ContractConstants.SchemaVersion,
        Operation = "native_render_evidence",
        DrawingFullPath = @"C:\drawings\sample.dwg",
        DrawingSha256 = new string('a', 64),
        Parameters = new Dictionary<string, JsonElement>
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
        },
        Approval = null
    };

    private static IpcResult NativeRenderResult(bool success)
    {
        var request = NativeRenderRequest();
        return new IpcResult
        {
            RequestId = request.RequestId,
            Success = success,
            Operation = request.Operation,
            DrawingFullPath = request.DrawingFullPath,
            Changed = false,
            EntityHandles = new List<string>(),
            Warnings = new List<string>(),
            Errors = success ? new List<string>() : new List<string> { "NATIVE_RENDER_NOT_IMPLEMENTED" },
            StartedAt = DateTimeOffset.Parse("2026-08-05T08:00:00Z"),
            CompletedAt = DateTimeOffset.Parse("2026-08-05T08:00:00Z"),
            Payload = success ? NativeRenderPayload() : new Dictionary<string, JsonElement>()
        };
    }

    private static Dictionary<string, JsonElement> NativeRenderPayload() =>
        new(StringComparer.Ordinal)
        {
            ["schema_version"] = JsonSerializer.SerializeToElement("autocad-native-render-evidence-1.0"),
            ["request_id"] = JsonSerializer.SerializeToElement("render-request-001"),
            ["run_id"] = JsonSerializer.SerializeToElement("run-001"),
            ["drawing_sha256"] = JsonSerializer.SerializeToElement(new string('a', 64)),
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
            ["renderer"] = JsonSerializer.SerializeToElement("AUTOCAD_NATIVE"),
            ["artifact"] = JsonSerializer.SerializeToElement(new
            {
                relative_path = "artifact.png",
                sha256 = new string('d', 64),
                width = 1600,
                height = 1200
            }),
            ["capture_timestamp"] = JsonSerializer.SerializeToElement("2026-08-05T08:00:00Z"),
            ["changed"] = JsonSerializer.SerializeToElement(false),
            ["dbmod_before"] = JsonSerializer.SerializeToElement(0),
            ["dbmod_after"] = JsonSerializer.SerializeToElement(0),
            ["warnings"] = JsonSerializer.SerializeToElement(Array.Empty<string>())
        };
}
