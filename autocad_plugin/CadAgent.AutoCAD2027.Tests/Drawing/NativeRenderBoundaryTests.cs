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

        var exception = Assert.Throws<InvalidDataException>(() => NativeRenderPolicy.EnsureSupported(request));
        Assert.Contains(NativeRenderPolicy.UnsupportedProfileErrorCode, exception.Message, StringComparison.Ordinal);
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

    [Fact]
    public void PaperSpaceReaderDoesNotCenterLayoutPlots()
    {
        var readerPath = RepositoryFile(
            "autocad_plugin/CadAgent.AutoCAD2027/Drawing/AutoCadNativeRenderReader.cs");

        var source = File.ReadAllText(readerPath);

        Assert.DoesNotContain("SetPlotCentered(", source, StringComparison.Ordinal);
    }

    [Fact]
    public void PdfMediaCensusReportsObservedTuplesAndRejectsNearMatches()
    {
        var media = new Dictionary<string, NativeRenderMediaObservation>(StringComparer.Ordinal)
        {
            ["ISO_A4_(210.00_x_297.00_MM)"] = new(
                "ISO_A4_(210.00_x_297.00_MM)", true, "Inches", 8.27, 11.69),
            ["OTHER_A4_MM"] = new("OTHER_A4_MM", true, "Millimeters", 210, 297),
            ["ISO_A4_(210.00_x_297.00_MM)_TRUNCATED"] = new(
                "ISO_A4_(210.00_x_297.00_MM)_TRUNCATED", true, "Millimeters", 210, 296),
            ["UNSELECTABLE_A4"] = new("UNSELECTABLE_A4", false, null, null, null),
            ["ALIAS_TO_VALID_A4"] = new("ISO_A4_(210.00_x_297.00_MM)", true, "Millimeters", 210, 297)
        };

        var census = AutoCadNativeRenderReader.CensusPlotMedia(
            "PDF",
            media.Keys,
            name => media[name]);

        Assert.Empty(census.ApprovedMediaNames);
        Assert.Equal(media.Count, census.Observations.Count);
        var diagnostic = census.FormatDiagnostic();
        Assert.Contains("canonical=ISO_A4_(210.00_x_297.00_MM);selectable=true;units=Inches;size=8.27x11.69;approved=false", diagnostic, StringComparison.Ordinal);
        Assert.Contains("canonical=OTHER_A4_MM;selectable=true;units=Millimeters;size=210x297;approved=false", diagnostic, StringComparison.Ordinal);
        Assert.Contains("canonical=ISO_A4_(210.00_x_297.00_MM)_TRUNCATED;selectable=true;units=Millimeters;size=210x296;approved=false", diagnostic, StringComparison.Ordinal);
        Assert.Contains("canonical=UNSELECTABLE_A4;selectable=false;units=unavailable;size=unavailable;approved=false", diagnostic, StringComparison.Ordinal);
        Assert.Contains("canonical=ALIAS_TO_VALID_A4;selectable=true;units=Millimeters;size=210x297;approved=false", diagnostic, StringComparison.Ordinal);
    }

    [Fact]
    public void PdfMediaCensusAdmitsOnlyTheExactSelectableA4Tuple()
    {
        var media = new NativeRenderMediaObservation(
            "ISO_A4_(210.00_x_297.00_MM)", true, "Millimeters", 210, 297);

        var census = AutoCadNativeRenderReader.CensusPlotMedia(
            "PDF",
            new[] { media.CanonicalMediaName },
            _ => media);

        Assert.Equal(new[] { "ISO_A4_(210.00_x_297.00_MM)" }, census.ApprovedMediaNames);
        Assert.Contains("approved=true", census.FormatDiagnostic(), StringComparison.Ordinal);
    }

    [Fact]
    public void PngMediaCensusReportsBothApprovedOrientationsWithoutRelaxingCardinality()
    {
        var media = new Dictionary<string, NativeRenderMediaObservation>(StringComparer.Ordinal)
        {
            ["UserDefinedRasterLandscape"] = new(
                "UserDefinedRasterLandscape", true, "Pixels", 3508, 2480),
            ["UserDefinedRasterPortrait"] = new(
                "UserDefinedRasterPortrait", true, "Pixels", 2480, 3508)
        };

        var census = AutoCadNativeRenderReader.CensusPlotMedia(
            "PNG",
            media.Keys.Reverse().Append("UserDefinedRasterLandscape"),
            name => media[name]);

        Assert.Equal(
            new[]
            {
                "UserDefinedRasterLandscape",
                "UserDefinedRasterLandscape",
                "UserDefinedRasterPortrait"
            },
            census.ApprovedMediaNames);
        Assert.Equal(
            census.Observations.Select(item => item.CanonicalMediaName).Order(StringComparer.Ordinal),
            new[]
            {
                "UserDefinedRasterLandscape",
                "UserDefinedRasterLandscape",
                "UserDefinedRasterPortrait"
            });
        Assert.Contains("approved=true", census.FormatDiagnostic(), StringComparison.Ordinal);
    }

    [Fact]
    public void MediaCensusDiagnosticBoundsTotalOutputAndEscapesUntrustedText()
    {
        var approvedMedia = new NativeRenderMediaObservation(
            "ISO_A4_(210.00_x_297.00_MM)", true, "Millimeters", 210, 297);
        var repeatedNames = Enumerable.Repeat(approvedMedia.CanonicalMediaName, 100);
        var repeatedCensus = AutoCadNativeRenderReader.CensusPlotMedia(
            "PDF",
            repeatedNames,
            _ => approvedMedia);

        Assert.Equal(100, repeatedCensus.Observations.Count);
        Assert.Equal(100, repeatedCensus.ApprovedMediaNames.Count);
        var repeatedDiagnostic = repeatedCensus.FormatDiagnostic();
        Assert.True(repeatedDiagnostic.Length <= 8192);
        Assert.Contains("observation_count=100", repeatedDiagnostic, StringComparison.Ordinal);
        Assert.Contains("approved_count=100", repeatedDiagnostic, StringComparison.Ordinal);
        Assert.Contains("omitted_observations=36", repeatedDiagnostic, StringComparison.Ordinal);
        Assert.DoesNotContain("approved_media=[", repeatedDiagnostic, StringComparison.Ordinal);

        var hostileName = "CUSTOM|A4;\r\n" + new string('x', 1024);
        var hostileMedia = new NativeRenderMediaObservation(
            hostileName, true, "Millimeters\r\nInjected=true", 210, 297);
        var hostileCensus = AutoCadNativeRenderReader.CensusPlotMedia(
            "PDF",
            new[] { hostileName },
            _ => hostileMedia);
        var hostileDiagnostic = hostileCensus.FormatDiagnostic();

        Assert.True(hostileDiagnostic.Length <= 8192);
        Assert.DoesNotContain('\r', hostileDiagnostic);
        Assert.DoesNotContain('\n', hostileDiagnostic);
        Assert.Contains("CUSTOM\\u007CA4\\u003B\\u000D\\u000A", hostileDiagnostic, StringComparison.Ordinal);
        Assert.Contains("Millimeters\\u000D\\u000AInjected\\u003Dtrue", hostileDiagnostic, StringComparison.Ordinal);
        Assert.Contains('…', hostileDiagnostic);
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

        throw new FileNotFoundException($"Repository file was not found: {relativePath}");
    }
}
