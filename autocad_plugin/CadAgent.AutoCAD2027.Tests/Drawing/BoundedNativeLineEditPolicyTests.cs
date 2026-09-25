using CadAgent.AutoCAD2027.Drawing;
using CadAgent.AutoCAD2027.Ipc;
using System.Security.Cryptography;
using Xunit;

namespace CadAgent.AutoCAD2027.Tests.Drawing;

public sealed class BoundedNativeLineEditPolicyTests
{
    private const string CandidatePath = @"C:\Cad agent temp\candidate.dwg";
    private const string ExpectedSha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";

    [Fact]
    public void AcceptsFreshCleanCandidateAndDirectModelSpaceLines()
    {
        BoundedNativeLineEditPolicy.ValidateBeforeWrite(
            Request(),
            CandidatePath,
            CandidatePath,
            ExpectedSha256,
            0,
            BeforeObservations());
    }

    [Fact]
    public void RejectsWrongCandidatePath()
    {
        Assert.Throws<InvalidOperationException>(() =>
            BoundedNativeLineEditPolicy.ValidateBeforeWrite(
                Request(),
                @"C:\Cad agent temp\other.dwg",
                CandidatePath,
                ExpectedSha256,
                0,
                BeforeObservations()));
    }

    [Fact]
    public void RejectsFreshDiskHashDrift()
    {
        Assert.Throws<InvalidOperationException>(() =>
            BoundedNativeLineEditPolicy.ValidateBeforeWrite(
                Request(),
                CandidatePath,
                CandidatePath,
                new string('b', 64),
                0,
                BeforeObservations()));
    }

    [Fact]
    public void RejectsDirtyActiveDocument()
    {
        Assert.Throws<InvalidOperationException>(() =>
            BoundedNativeLineEditPolicy.ValidateBeforeWrite(
                Request(),
                CandidatePath,
                CandidatePath,
                ExpectedSha256,
                1,
                BeforeObservations()));
    }

    [Theory]
    [InlineData(false, true, false)]
    [InlineData(true, false, false)]
    [InlineData(true, false, true)]
    public void RejectsWrongTypeOwnerOrSharedDefinitionReachability(
        bool isAcDbLine,
        bool isDirectModelSpace,
        bool hasSharedDefinitionReachability)
    {
        var observations = BeforeObservations()
            .Select(item => item.Handle == "A1"
                ? item with
                {
                    IsAcDbLine = isAcDbLine,
                    IsDirectModelSpace = isDirectModelSpace,
                    HasSharedDefinitionReachability = hasSharedDefinitionReachability
                }
                : item)
            .ToArray();

        Assert.Throws<InvalidOperationException>(() =>
            BoundedNativeLineEditPolicy.ValidateBeforeWrite(
                Request(),
                CandidatePath,
                CandidatePath,
                ExpectedSha256,
                0,
                observations));
    }

    [Fact]
    public void RejectsDirectModelSpaceTargetWithPersistentReactorsBeforeMutation()
    {
        var observations = BeforeObservations()
            .Select(item => item.Handle == "A1"
                ? item with { HasPersistentReactors = true }
                : item)
            .ToArray();

        Assert.Throws<InvalidOperationException>(() =>
            BoundedNativeLineEditPolicy.ValidateBeforeWrite(
                Request(),
                CandidatePath,
                CandidatePath,
                ExpectedSha256,
                0,
                observations));
    }

    [Fact]
    public void RejectsExpectedBeforeMismatch()
    {
        var observations = BeforeObservations()
            .Select(item => item.Handle == "A1"
                ? item with
                {
                    Geometry = new(
                        new[] { 0d, 0d, 0d },
                        new[] { 1.001d, 0d, 0d })
                }
                : item)
            .ToArray();

        Assert.Throws<InvalidOperationException>(() =>
            BoundedNativeLineEditPolicy.ValidateBeforeWrite(
                Request(),
                CandidatePath,
                CandidatePath,
                ExpectedSha256,
                0,
                observations));
    }

    [Fact]
    public void RejectsTargetAndProtectedHandleOverlapAtTheGatewayBoundary()
    {
        var request = Request() with
        {
            Protected = new[]
            {
                new BoundedNativeLineProtectedEntity(
                    "A1",
                    new(new[] { 0d, 0d, 0d }, new[] { 1d, 0d, 0d }))
            }
        };

        Assert.Throws<InvalidOperationException>(() =>
            BoundedNativeLineEditPolicy.ValidateBeforeWrite(
                request,
                CandidatePath,
                CandidatePath,
                ExpectedSha256,
                0,
                BeforeObservations()));
    }

    [Fact]
    public void AcceptsWithinToleranceReadbackAndUnchangedProtectedLines()
    {
        var before = BeforeObservations();
        var after = new[]
        {
            new NativeLineEditObservation(
                "A1",
                true,
                true,
                false,
                new(new[] { 0d, 0d, 0d }, new[] { 2d + 5e-9, 0d, 0d })),
            before[1]
        };

        BoundedNativeLineEditPolicy.ValidateReadback(Request(), before, after);
    }

    [Fact]
    public void RejectsProtectedLineDriftOnReadback()
    {
        var before = BeforeObservations();
        var after = new[]
        {
            new NativeLineEditObservation(
                "A1",
                true,
                true,
                false,
                new(new[] { 0d, 0d, 0d }, new[] { 2d, 0d, 0d })),
            before[1] with
            {
                Geometry = new(new[] { 0d, 1d, 0d }, new[] { 0d, 2.001d, 0d })
            }
        };

        Assert.Throws<InvalidOperationException>(() =>
            BoundedNativeLineEditPolicy.ValidateReadback(Request(), before, after));
    }

    [Fact]
    public void ProvesRollbackOnlyWhenAllTargetsAndProtectedLinesReturnToBeforeState()
    {
        var before = BeforeObservations();
        BoundedNativeLineEditPolicy.ValidateRollbackReadback(Request(), before, before);

        var changed = new[]
        {
            before[0] with
            {
                Geometry = new(new[] { 0d, 0d, 0d }, new[] { 2d, 0d, 0d })
            },
            before[1]
        };
        Assert.Throws<InvalidOperationException>(() =>
            BoundedNativeLineEditPolicy.ValidateRollbackReadback(Request(), before, changed));
    }

    [Fact]
    public void ReportsUncertainWhenSaveFailedAndRollbackWasNotProven()
    {
        Assert.Equal(
            "UNCERTAIN",
            BoundedNativeLineEditPolicy.ResolveDurableState(
                saveCompleted: false,
                savedReadbackMatches: false,
                savedFileMatches: false,
                databaseClean: false,
                rollbackProven: false));

        Assert.Equal(
            "ROLLED_BACK",
            BoundedNativeLineEditPolicy.ResolveDurableState(
                saveCompleted: false,
                savedReadbackMatches: false,
                savedFileMatches: false,
                databaseClean: false,
                rollbackProven: true));
    }

    [Fact]
    public void PreservesExternallyChangedCandidateAndSkipsRollbackPersistence()
    {
        var candidatePath = Path.Combine(
            Path.GetTempPath(),
            $"cad-agent-rollback-{Guid.NewGuid():N}.dwg");
        try
        {
            File.WriteAllText(candidatePath, "authorized pre-edit candidate");
            var authorizedSha256 = HashFile(candidatePath);
            File.WriteAllText(candidatePath, "external candidate change");
            var externalBytes = File.ReadAllBytes(candidatePath);
            var saveAsCalled = false;

            var persisted = BoundedNativeLineEditPolicy.TryPersistRollbackIfDiskCurrent(
                authorizedSha256,
                HashFile(candidatePath),
                () =>
                {
                    saveAsCalled = true;
                    File.WriteAllText(candidatePath, "rollback SaveAs");
                });

            Assert.False(persisted);
            Assert.False(saveAsCalled);
            Assert.Equal(externalBytes, File.ReadAllBytes(candidatePath));
        }
        finally
        {
            if (File.Exists(candidatePath))
            {
                File.Delete(candidatePath);
            }
        }
    }

    [Fact]
    public void PersistsRollbackWhenCandidateDiskStillMatchesAuthorizedState()
    {
        var candidatePath = Path.Combine(
            Path.GetTempPath(),
            $"cad-agent-rollback-{Guid.NewGuid():N}.dwg");
        try
        {
            File.WriteAllText(candidatePath, "authorized pre-edit candidate");
            var authorizedSha256 = HashFile(candidatePath);
            var saveAsCalled = false;

            var persisted = BoundedNativeLineEditPolicy.TryPersistRollbackIfDiskCurrent(
                authorizedSha256,
                HashFile(candidatePath),
                () =>
                {
                    saveAsCalled = true;
                    File.WriteAllText(candidatePath, "rollback SaveAs");
                });

            Assert.True(persisted);
            Assert.True(saveAsCalled);
            Assert.Equal("rollback SaveAs", File.ReadAllText(candidatePath));
        }
        finally
        {
            if (File.Exists(candidatePath))
            {
                File.Delete(candidatePath);
            }
        }
    }

    [Fact]
    public void SkipsRollbackPersistenceWhenNoTrustedDiskShaWasCaptured()
    {
        var saveAsCalled = false;

        var persisted = BoundedNativeLineEditPolicy.TryPersistRollbackIfDiskCurrent(
            string.Empty,
            "current-disk-sha",
            () => saveAsCalled = true);

        Assert.False(persisted);
        Assert.False(saveAsCalled);
    }

    [Fact]
    public void ReportsSavedOnlyWhenSaveDiskReadbackAndDbmodAgree()
    {
        Assert.Equal(
            "SAVED",
            BoundedNativeLineEditPolicy.ResolveDurableState(
                saveCompleted: true,
                savedReadbackMatches: true,
                savedFileMatches: true,
                databaseClean: true,
                rollbackProven: false));

        Assert.Equal(
            "UNCERTAIN",
            BoundedNativeLineEditPolicy.ResolveDurableState(
                saveCompleted: true,
                savedReadbackMatches: false,
                savedFileMatches: true,
                databaseClean: true,
                rollbackProven: false));
    }

    private static BoundedNativeLineEditRequest Request() => new(
        CandidatePath,
        ExpectedSha256,
        new[]
        {
            new BoundedNativeLineTarget(
                "A1",
                new(new[] { 0d, 0d, 0d }, new[] { 1d, 0d, 0d }),
                new(new[] { 0d, 0d, 0d }, new[] { 2d, 0d, 0d }))
        },
        new[]
        {
            new BoundedNativeLineProtectedEntity(
                "AF",
                new(new[] { 0d, 1d, 0d }, new[] { 0d, 2d, 0d }))
        });

    private static NativeLineEditObservation[] BeforeObservations() =>
    [
        new("A1", true, true, false, new(new[] { 0d, 0d, 0d }, new[] { 1d, 0d, 0d })),
        new("AF", true, true, false, new(new[] { 0d, 1d, 0d }, new[] { 0d, 2d, 0d }))
    ];

    private static string HashFile(string path) =>
        Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
}
