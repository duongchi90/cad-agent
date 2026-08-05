using CadAgent.AutoCAD2027.Drawing;
using Xunit;

namespace CadAgent.AutoCAD2027.Tests.Drawing;

public sealed class NativeRenderBoundaryTests
{
    [Theory]
    [InlineData("PNG")]
    [InlineData("PDF")]
    public void SupportedProfileAcceptsTheApprovedPaperSpaceRequest(string artifactKind)
    {
        var request = Request(artifactKind, "Layout1");

        NativeRenderPolicy.EnsureSupported(request);
    }

    [Theory]
    [InlineData("Model", "PNG", "white", 300, true, "A4", "monochrome.ctb")]
    [InlineData("Layout1", "PNG", "black", 300, true, "A4", "monochrome.ctb")]
    [InlineData("Layout1", "PNG", "white", 600, true, "A4", "monochrome.ctb")]
    [InlineData("Layout1", "PNG", "white", 300, false, "A4", "monochrome.ctb")]
    [InlineData("Layout1", "PNG", "white", 300, true, "A3", "monochrome.ctb")]
    [InlineData("Layout1", "PNG", "white", 300, true, "A4", "acad.ctb")]
    [InlineData("Layout1", "BMP", "white", 300, true, "A4", "monochrome.ctb")]
    public void UnsupportedProfileFailsClosed(
        string layoutName,
        string artifactKind,
        string background,
        long dpi,
        bool fitToPaper,
        string paperSize,
        string plotStyle)
    {
        var request = Request(
            artifactKind,
            layoutName,
            new NativeRenderOptions(background, dpi, fitToPaper, paperSize, plotStyle));

        Assert.Throws<InvalidDataException>(() => NativeRenderPolicy.EnsureSupported(request));
    }

    [Fact]
    public void ReadOnlyPolicyAcceptsStableNonNegativeState()
    {
        NativeRenderPolicy.EnsureReadOnly(0, 0, new string('a', 64), new string('a', 64), true);
    }

    [Theory]
    [InlineData(-1, 0, true)]
    [InlineData(0, 1, true)]
    [InlineData(0, 0, false)]
    public void ReadOnlyPolicyRejectsUnstableState(int before, int after, bool restored)
    {
        Assert.Throws<InvalidDataException>(() => NativeRenderPolicy.EnsureReadOnly(
            before,
            after,
            new string('a', 64),
            new string('a', 64),
            restored));
    }

    [Fact]
    public void ReadOnlyPolicyRejectsAChangedDrawingHash()
    {
        Assert.Throws<InvalidDataException>(() => NativeRenderPolicy.EnsureReadOnly(
            0,
            0,
            new string('a', 64),
            new string('b', 64),
            true));
    }

    private static NativeRenderRequest Request(
        string artifactKind,
        string layoutName,
        NativeRenderOptions? options = null) =>
        new(
            "render-request-001",
            "run-001",
            @"C:\drawings\sample.dwg",
            new string('a', 64),
            new string('b', 64),
            new string('c', 64),
            new("layout-001", layoutName),
            artifactKind,
            options ?? new("white", 300, true, "A4", "monochrome.ctb"));
}
