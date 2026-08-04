using System.Text.Json;
using CadAgent.AutoCAD2027.Drawing;
using Xunit;

namespace CadAgent.AutoCAD2027.Tests.Drawing;

public sealed class VisualEvidenceBoundaryTests
{
    [Fact]
    public void SessionStateFingerprintIsStableForEquivalentCanonicalState()
    {
        var first = SessionStateSnapshot.Create(
            @"C:\drawings\sample.dwg",
            "doc-001",
            "Model",
            new SessionSpaceSnapshot("Model", 1, 2, "MODEL_SPACE"),
            "0",
            "center=10,20;width=100;height=50;target=0,0,0;direction=0,0,1;twist=0;lens=50",
            new[] { "AB", "CD" },
            new Dictionary<string, SessionLayerSnapshot>
            {
                ["CABIN"] = new(false, false),
                ["CENTER"] = new(true, false)
            },
            new Dictionary<string, JsonElement>
            {
                ["BACKGROUNDCOLOR"] = JsonSerializer.SerializeToElement("WHITE"),
                ["UCSFOLLOW"] = JsonSerializer.SerializeToElement(0)
            });
        var second = SessionStateSnapshot.Create(
            @"C:/drawings/parts/../sample.dwg",
            "doc-001",
            "Model",
            new SessionSpaceSnapshot("Model", 1, 2, "MODEL_SPACE"),
            "0",
            "center=10,20;width=100;height=50;target=0,0,0;direction=0,0,1;twist=0;lens=50",
            new[] { "AB", "CD" },
            new Dictionary<string, SessionLayerSnapshot>
            {
                ["CENTER"] = new(true, false),
                ["CABIN"] = new(false, false)
            },
            new Dictionary<string, JsonElement>
            {
                ["UCSFOLLOW"] = JsonSerializer.SerializeToElement(0),
                ["BACKGROUNDCOLOR"] = JsonSerializer.SerializeToElement("WHITE")
            });

        Assert.Equal(first.FingerprintSha256, second.FingerprintSha256);
    }

    [Fact]
    public void BoundaryRejectsAFullPathMismatchBeforeEvidenceIsAccepted()
    {
        var request = Request(@"C:\drawings\sample.dwg");
        var snapshot = Snapshot(@"C:\other\sample.dwg");

        var errors = VisualEvidenceReadOnlyBoundary.Validate(request, snapshot);

        Assert.Contains(errors, error => error.Contains("full path", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void BoundaryRejectsAnyChangedOrUnprovenSnapshot()
    {
        var request = Request(@"C:\drawings\sample.dwg");
        var snapshot = Snapshot(@"C:\drawings\sample.dwg") with
        {
            DrawingSha256After = new string('b', 64),
            DbModAfter = 1,
            TransientStateRestored = false,
            EntityHandles = new[] { "AB" }
        };

        var errors = VisualEvidenceReadOnlyBoundary.Validate(request, snapshot);

        Assert.Contains(errors, error => error.Contains("drawing hash", StringComparison.OrdinalIgnoreCase));
        Assert.Contains(errors, error => error.Contains("DBMOD", StringComparison.OrdinalIgnoreCase));
        Assert.Contains(errors, error => error.Contains("transient", StringComparison.OrdinalIgnoreCase));
        Assert.Contains(errors, error => error.Contains("entity handles", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void BoundaryRequiresManifestAndEvidenceIdentityToBeEchoedExactly()
    {
        var request = Request(@"C:\drawings\sample.dwg");
        var snapshot = Snapshot(@"C:\drawings\sample.dwg") with
        {
            EvidenceId = "EV-OTHER",
            LatestMutationSha256 = new string('d', 64)
        };

        var errors = VisualEvidenceReadOnlyBoundary.Validate(request, snapshot);

        Assert.Contains(errors, error => error.Contains("evidence_id", StringComparison.Ordinal));
        Assert.Contains(errors, error => error.Contains("latest_mutation_sha256", StringComparison.Ordinal));
    }

    [Fact]
    public void SessionStateFingerprintIncludesTheActualViewSnapshot()
    {
        var first = CreateState(new SessionViewSnapshot(10, 20, 100, 50, 0, 0, 0, 0, 0, 1, 0, 50));
        var second = CreateState(new SessionViewSnapshot(11, 20, 100, 50, 0, 0, 0, 0, 0, 1, 0, 50));

        Assert.NotEqual(first.FingerprintSha256, second.FingerprintSha256);
    }

    [Fact]
    public void SessionStatePreservesTypedSystemVariablesAndFloatingViewportIdentity()
    {
        var state = SessionStateSnapshot.Create(
            @"C:\drawings\sample.dwg",
            "doc-001",
            "Layout1",
            new SessionSpaceSnapshot("Layout1", 0, 2, "PAPER_SPACE_FLOATING_VIEWPORT"),
            "0",
            "actual-view",
            Array.Empty<string>(),
            new Dictionary<string, SessionLayerSnapshot>(),
            new Dictionary<string, JsonElement>
            {
                ["LTSCALE"] = JsonSerializer.SerializeToElement(2.5),
                ["ANNOALLVISIBLE"] = JsonSerializer.SerializeToElement(1)
            },
            null);

        Assert.Equal("PAPER_SPACE_FLOATING_VIEWPORT", state.Space.Kind);
        Assert.Equal(JsonValueKind.Number, state.RendererSystemVariables["LTSCALE"].ValueKind);
        Assert.Equal(2.5, state.RendererSystemVariables["LTSCALE"].GetDouble());
    }

    private static SessionStateSnapshot CreateState(SessionViewSnapshot view) => SessionStateSnapshot.Create(
        @"C:\drawings\sample.dwg",
        "doc-001",
        "Model",
        new SessionSpaceSnapshot("Model", 1, 2, "MODEL_SPACE"),
        "0",
        "actual-view",
        Array.Empty<string>(),
        new Dictionary<string, SessionLayerSnapshot>(),
        new Dictionary<string, JsonElement>(),
        view);

    private static VisualEvidenceRequest Request(string path) => new(
        path,
        new string('a', 64),
        "RUN-001",
        "EV-001",
        "SIDE-CABIN",
        new string('b', 64),
        new string('c', 64),
        "vs-t3-artifacts-1",
        "artifacts/REQ-001",
        JsonSerializer.SerializeToElement(new { }),
        Array.Empty<JsonElement>());

    private static VisualEvidenceSnapshot Snapshot(string path) => new(
        path,
        path,
        "RUN-001",
        "EV-001",
        "SIDE-CABIN",
        new string('a', 64),
        new string('a', 64),
        0,
        0,
        new string('b', 64),
        new string('c', 64),
        new string('d', 64),
        new string('e', 64),
        new string('e', 64),
        true,
        DateTimeOffset.Parse("2026-08-04T00:00:02Z"),
        Array.Empty<EvidenceArtifactDescriptor>(),
        false,
        Array.Empty<string>());
}
