namespace CadAgent.AutoCAD2027.DrawingSetup;

public sealed record LayerSetupSnapshot(
    string Name,
    string Linetype,
    bool Plottable);

public sealed record TextStyleSetupSnapshot(
    string Name,
    string Font,
    string BigFont);

public sealed record LayoutSetupSnapshot(
    string Name,
    IReadOnlyList<double> ViewportScales,
    bool Locked);

public sealed record DrawingSetupSnapshot(
    string DrawingFullPath,
    int DbModBefore,
    int DbModAfter,
    IReadOnlyDictionary<string, double> Variables,
    string CurrentLayer,
    IReadOnlyDictionary<string, string> CustomProperties,
    IReadOnlyList<LayerSetupSnapshot> Layers,
    IReadOnlyList<TextStyleSetupSnapshot> TextStyles,
    IReadOnlyList<string> DimensionStyles,
    IReadOnlyList<string> MLeaderStyles,
    IReadOnlyList<string> TableStyles,
    IReadOnlyList<LayoutSetupSnapshot> Layouts,
    IReadOnlyList<string> MissingFonts,
    IReadOnlyList<string> SubstitutedFonts);
