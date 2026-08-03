using CadAgent.AutoCAD2027.Drawing;

namespace CadAgent.AutoCAD2027.Tests.DrawingSetup;

internal static class DrawingSetupFixtures
{
    internal static DrawingSetupSnapshot VerifiedSnapshot(string path) => new(
        path, 0, 0, 4, 1, 100.0, 1.0, 1, 1, 2, 0, "0",
        new Dictionary<string, string>
        {
            ["CAD_AGENT_SETTINGS_SHA256"] = new string('a', 64)
        },
        new[]
        {
            new LayerSetupSnapshot("0", 7, "Continuous", -1, true, false, false),
            new LayerSetupSnapshot("NET_CHINH", 7, "Continuous", 35, true, false, false)
        },
        new[] { new TextStyleSetupSnapshot("VX_TEXT", "Arial.ttf", "") },
        new[] { new NamedStyleSnapshot("VX_DIM_20") },
        new[] { new NamedStyleSnapshot("VX_MLEADER") },
        new[] { new NamedStyleSnapshot("VX_TABLE") },
        new[]
        {
            new LayoutSetupSnapshot(
                "A1-01", false, "ISO_A1_(841.00_x_594.00_MM)",
                "DWG To PDF.pc3", "Layout", 1.0, 1.0,
                new[] { new ViewportSetupSnapshot("2F", 0.05, true) })
        });

    internal static DrawingSetupSnapshot UnsortedSnapshot()
    {
        var source = VerifiedSnapshot(@"C:\temp\setup.dwg");
        return source with
        {
            Layers = source.Layers.Reverse().ToArray(),
            Layouts = source.Layouts.Reverse().ToArray()
        };
    }
}
