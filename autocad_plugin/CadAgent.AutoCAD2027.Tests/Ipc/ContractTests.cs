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
}
