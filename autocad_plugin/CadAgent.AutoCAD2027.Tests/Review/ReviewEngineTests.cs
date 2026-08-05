using System.Text.Json;
using CadAgent.AutoCAD2027.Drawing;
using CadAgent.AutoCAD2027.DrawingSetup;
using CadAgent.AutoCAD2027.Review;
using Xunit;

namespace CadAgent.AutoCAD2027.Tests.Review;

public sealed class ReviewEngineTests
{
    [Fact]
    public void MatchesAnActiveDrawingByItsNormalizedFullPath()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\drawings\Sample.dwg",
            Entities = new[] { Entity("L1", "LINE") }
        };
        var engine = new ReviewEngine(gateway);

        var result = engine.Review(new ReviewRequest(
            @"c:/drawings/./Sample.dwg",
            new[] { "L1" }));

        Assert.True(result.Success);
        Assert.Empty(result.Errors);
        Assert.Equal(@"C:\drawings\Sample.dwg", result.DrawingFullPath);
    }

    [Theory]
    [InlineData(@"\drawings\Sample.dwg")]
    [InlineData(@"C:drawings\Sample.dwg")]
    public void RejectsWindowsPathsThatAreNotFullyQualified(string path)
    {
        Assert.Throws<ArgumentException>(() => ReviewEngine.NormalizeFullPath(path));
    }

    [Fact]
    public void AcceptsUncPathsAsFullyQualifiedWindowsPaths()
    {
        const string path = @"\\server\share\drawings\Sample.dwg";

        Assert.Equal(path, ReviewEngine.NormalizeFullPath(path));
    }

    [Fact]
    public void DoesNotTreatTheSameFilenameInAnotherDirectoryAsTheActiveDrawing()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\other\Sample.dwg"
        };
        var engine = new ReviewEngine(gateway);

        var result = engine.Review(new ReviewRequest(
            @"C:\drawings\Sample.dwg",
            Array.Empty<string>()));

        Assert.False(result.Success);
        Assert.Contains(result.Errors, error => error.Contains("full path", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void MapsSupportedEntityTypesAndPreservesTheirBasicGeometry()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\drawings\Sample.dwg",
            Entities = new[]
            {
                Entity("L1", "LINE", ("start_x", 1.0), ("start_y", 2.0), ("end_x", 3.0), ("end_y", 4.0)),
                Entity("C1", "CIRCLE", ("center_x", 5.0), ("center_y", 6.0), ("radius", 7.0)),
                Entity("A1", "ARC", ("center_x", 8.0), ("center_y", 9.0), ("radius", 10.0), ("start_angle", 0.25), ("end_angle", 1.5)),
                Entity("T1", "TEXT", ("position_x", 11.0), ("position_y", 12.0), ("height", 2.5), ("text", "NOTE")),
                Entity("D1", "DIMENSION", ("measurement", 42.0), ("definition_x", 13.0), ("definition_y", 14.0))
            }
        };
        var engine = new ReviewEngine(gateway);

        var result = engine.Review(new ReviewRequest(
            @"C:\drawings\Sample.dwg",
            new[] { "L1", "C1", "A1", "T1", "D1" }));

        Assert.True(result.Success);
        Assert.Equal(new[] { "LINE", "CIRCLE", "ARC", "TEXT", "DIMENSION" }, result.Entities.Select(entity => entity.Type));
        Assert.Equal(3.0, result.Entities[0].Geometry["end_x"].GetDouble());
        Assert.Equal("NOTE", result.Entities[3].Geometry["text"].GetString());
        Assert.Equal(42.0, result.Entities[4].Geometry["measurement"].GetDouble());
    }

    [Fact]
    public void ReturnsMissingHandlesAsWarningsWithoutFailingTheReview()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\drawings\Sample.dwg",
            Entities = new[] { Entity("L1", "LINE") }
        };
        var engine = new ReviewEngine(gateway);

        var result = engine.Review(new ReviewRequest(
            @"C:\drawings\Sample.dwg",
            new[] { "L1", "MISSING" }));

        Assert.True(result.Success);
        Assert.Single(result.Entities);
        Assert.Contains(result.Warnings, warning => warning.Contains("MISSING", StringComparison.Ordinal));
    }

    [Fact]
    public void ReturnsAnEntityWithoutAHandleAsAWarning()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\drawings\Sample.dwg",
            Entities = new[] { Entity(null, "LINE") }
        };

        var result = new ReviewEngine(gateway).Review(new ReviewRequest(
            @"C:\drawings\Sample.dwg",
            new[] { "L1" }));

        Assert.True(result.Success);
        Assert.Empty(result.Entities);
        Assert.Contains(result.Warnings, warning => warning.Contains("without a handle", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void ReturnsUnsupportedTypesAsWarningsWithoutIncludingThemInThePayload()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\drawings\Sample.dwg",
            Entities = new[]
            {
                Entity("H1", "HATCH"),
                Entity("L1", "LINE")
            }
        };
        var engine = new ReviewEngine(gateway);

        var result = engine.Review(new ReviewRequest(
            @"C:\drawings\Sample.dwg",
            new[] { "H1", "L1" }));

        Assert.True(result.Success);
        Assert.Equal("L1", Assert.Single(result.Entities).Handle);
        Assert.Contains(result.Warnings, warning => warning.Contains("HATCH", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void ReportsAnUnavailableActiveDocumentAsAnError()
    {
        var result = new ReviewEngine(new NullDrawingGateway()).Review(new ReviewRequest(
            @"C:\drawings\Sample.dwg",
            Array.Empty<string>()));

        Assert.False(result.Success);
        Assert.False(result.Changed);
        Assert.Contains(result.Errors, error => error.Contains("active document", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void KeepsTheReviewBoundaryReadOnlyAndCallsOnlyTheGatewayReadMethod()
    {
        var gateway = new StubDrawingGateway
        {
            ActiveDocumentFullPath = @"C:\drawings\Sample.dwg",
            Entities = new[] { Entity("L1", "LINE") }
        };

        var result = new ReviewEngine(gateway).Review(new ReviewRequest(
            @"C:\drawings\Sample.dwg",
            new[] { "L1" }));

        Assert.True(result.Success);
        Assert.False(result.Changed);
        Assert.Equal(1, gateway.ReadEntitiesCallCount);
    }

    private static EntitySnapshot Entity(
        string? handle,
        string? type,
        params (string Name, object Value)[] geometry) =>
        new(handle, type, "0", geometry.ToDictionary(
            item => item.Name,
            item => JsonSerializer.SerializeToElement(item.Value),
            StringComparer.Ordinal));

    private sealed class StubDrawingGateway : IDrawingGateway
    {
        public string? ActiveDocumentFullPath { get; init; }

        public IReadOnlyList<EntitySnapshot> Entities { get; init; } = Array.Empty<EntitySnapshot>();

        public int ReadEntitiesCallCount { get; private set; }

        public IReadOnlyList<EntitySnapshot> ReadEntities(IReadOnlyCollection<string> handles)
        {
            ReadEntitiesCallCount++;
            return Entities;
        }

        public DrawingSetupSnapshot ReadDrawingSetup() =>
            throw new NotSupportedException();

        public VisualEvidenceSnapshot ReadVisualEvidence(VisualEvidenceRequest request) =>
            throw new NotSupportedException();

        public NativeRenderEvidenceSnapshot ReadNativeRenderEvidence(NativeRenderRequest request) =>
            throw new NotSupportedException();
    }
}
