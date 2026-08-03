using CadAgent.AutoCAD2027.DrawingSetup;

namespace CadAgent.AutoCAD2027.Tests.DrawingSetup;

internal static class DrawingSetupFixtures
{
    public static DrawingSetupSnapshot VerifiedSnapshot(string drawingFullPath)
    {
        var source = UnsortedSnapshot();
        return source with
        {
            DrawingFullPath = drawingFullPath,
            Layers = source.Layers.OrderBy(layer => layer.Name, StringComparer.Ordinal).ToArray(),
            TextStyles = source.TextStyles.OrderBy(style => style.Name, StringComparer.Ordinal).ToArray()
        };
    }

    public static DrawingSetupSnapshot UnsortedSnapshot(
        int dbModBefore = 0,
        int dbModAfter = 0)
    {
        return new DrawingSetupSnapshot(
            @"C:\drawings\setup.dwg",
            dbModBefore,
            dbModAfter,
            new Dictionary<string, double>(StringComparer.Ordinal)
            {
                ["PSLTSCALE"] = 1,
                ["INSUNITS"] = 4
            },
            "NET_CHINH",
            new Dictionary<string, string>(StringComparer.Ordinal)
            {
                ["drawing_standard"] = "TCVN",
                ["domain_pack"] = "mechanical"
            },
            new[]
            {
                new LayerSetupSnapshot("NET_CHINH", "CONTINUOUS", true),
                new LayerSetupSnapshot("0", "CONTINUOUS", true)
            },
            new[]
            {
                new TextStyleSetupSnapshot("TCVN", "arial.ttf", string.Empty),
                new TextStyleSetupSnapshot("Standard", "txt.shx", string.Empty)
            },
            new[] { "TCVN", "Standard" },
            new[] { "TCVN", "Standard" },
            new[] { "TCVN", "Standard" },
            new[]
            {
                new LayoutSetupSnapshot("A1-01", new[] { 0.02, 0.01 }, true)
            },
            new[] { "missing.shx" },
            new[] { "simplex.shx -> simplex8.shx" });
    }
}
