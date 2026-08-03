namespace CadAgent.AutoCAD2027.Drawing;

public sealed record DrawingSetupSnapshot(
    string DrawingFullPath,
    int DbModBefore,
    int DbModAfter,
    int InsUnits,
    int Measurement,
    double LtScale,
    double Celtscale,
    int PsLtScale,
    int MsLtScale,
    int DimAssoc,
    int AnnoAllVisible,
    string CurrentLayer,
    IReadOnlyDictionary<string, string> CustomProperties,
    IReadOnlyList<LayerSetupSnapshot> Layers,
    IReadOnlyList<TextStyleSetupSnapshot> TextStyles,
    IReadOnlyList<NamedStyleSnapshot> DimensionStyles,
    IReadOnlyList<NamedStyleSnapshot> MLeaderStyles,
    IReadOnlyList<NamedStyleSnapshot> TableStyles,
    IReadOnlyList<LayoutSetupSnapshot> Layouts);

public sealed record LayerSetupSnapshot(
    string Name,
    int ColorIndex,
    string Linetype,
    int LineWeight,
    bool Plottable,
    bool Frozen,
    bool Locked);

public sealed record TextStyleSetupSnapshot(string Name, string Font, string BigFont);

public sealed record NamedStyleSnapshot(string Name);

public sealed record ViewportSetupSnapshot(string Handle, double CustomScale, bool Locked);

public sealed record LayoutSetupSnapshot(
    string Name,
    bool IsModel,
    string CanonicalMediaName,
    string PlotDevice,
    string PlotType,
    double ScaleNumerator,
    double ScaleDenominator,
    IReadOnlyList<ViewportSetupSnapshot> Viewports);
