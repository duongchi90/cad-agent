using System.Text.Json;
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

    [Fact]
    public void RejectsUnsupportedOperation()
    {
        var request = ValidRequest() with { Operation = "repair" };

        var validation = ContractValidator.ValidateRequest(request);

        Assert.False(validation.IsValid);
        Assert.Contains(validation.Errors, error => error.Contains("operation", StringComparison.OrdinalIgnoreCase));
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
