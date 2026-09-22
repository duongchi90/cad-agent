using System.Text.Json;
using CadAgent.AutoCAD2027.Drawing;
using CadAgent.AutoCAD2027.Ipc;
using Xunit;

namespace CadAgent.AutoCAD2027.Tests.Ipc;

public sealed class BoundedNativeLineEditTests
{
    private static readonly string[] TargetHandles =
    {
        "15DC51C", "15DC51A", "15DC518", "15DC516", "15DC514", "15DC512",
        "15DC510", "15DC50E", "15DC50C", "15DC50A", "15DC508", "15DC506"
    };

    private static readonly string[] ProtectedHandles =
    {
        "15DC51D", "15DC51B", "15DC519", "15DC517", "15DC515", "15DC513",
        "15DC511", "15DC50F", "15DC50D", "15DC50B", "15DC509", "15DC507"
    };

    [Fact]
    public void AcceptsTheExplicitUpperLeftOccurrenceAndProtectedCompetingOccurrence()
    {
        var request = Request(TargetHandles, ProtectedHandles);

        var validation = ContractValidator.ValidateRequest(request);

        Assert.True(validation.IsValid, string.Join("; ", validation.Errors));
    }

    [Fact]
    public void RejectsAnyOverlapBetweenTargetAndProtectedOccurrences()
    {
        var request = Request(TargetHandles, TargetHandles);

        var validation = ContractValidator.ValidateRequest(request);

        Assert.False(validation.IsValid);
        Assert.Contains(
            validation.Errors,
            error => error.Contains("overlap", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void SaveFailureAfterPossibleDurableWriteReportsRollbackState()
    {
        Assert.Equal(
            BoundedNativeLineEditDurableStates.Unchanged,
            BoundedNativeLineEditDurableStates.ResolveAfterSaveFailure(rollbackPersisted: true));
        Assert.Equal(
            BoundedNativeLineEditDurableStates.Uncertain,
            BoundedNativeLineEditDurableStates.ResolveAfterSaveFailure(rollbackPersisted: false));
    }

    private static IpcRequest Request(
        IReadOnlyList<string> targetHandles,
        IReadOnlyList<string> protectedHandles) =>
        new()
        {
            RequestId = "phase4-owner-admission-001",
            SchemaVersion = ContractConstants.SchemaVersion,
            Operation = "bounded_native_line_edit",
            DrawingFullPath = @"C:\Users\dkv\Downloads\BVTL.dwg",
            DrawingSha256 = new string('a', 64),
            Approval = JsonSerializer.SerializeToElement(new
            {
                reference = "phase4-owner-admission-20260922",
                status = "APPROVED"
            }),
            Parameters = new Dictionary<string, JsonElement>(StringComparer.Ordinal)
            {
                ["run_id"] = JsonSerializer.SerializeToElement("phase4-owner-admission-001"),
                ["target_role"] = JsonSerializer.SerializeToElement("ACCEPTED_NATIVE_DWG"),
                ["target_handles"] = JsonSerializer.SerializeToElement(targetHandles),
                ["protected_competing_handles"] = JsonSerializer.SerializeToElement(protectedHandles),
                ["expected_type"] = JsonSerializer.SerializeToElement("LINE"),
                ["expected_before_length"] = JsonSerializer.SerializeToElement(490.0),
                ["target_after_length"] = JsonSerializer.SerializeToElement(500.0),
                ["length_tolerance"] = JsonSerializer.SerializeToElement(0.001),
                ["direction"] = JsonSerializer.SerializeToElement("POSITIVE_Y"),
                ["save"] = JsonSerializer.SerializeToElement(true)
            }
        };
}
