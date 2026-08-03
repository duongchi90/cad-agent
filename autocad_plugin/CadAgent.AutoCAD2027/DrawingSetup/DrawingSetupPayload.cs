using System.Text.Json;

namespace CadAgent.AutoCAD2027.DrawingSetup;

public static class DrawingSetupPayload
{
    public static Dictionary<string, JsonElement> Create(DrawingSetupSnapshot snapshot)
    {
        ArgumentNullException.ThrowIfNull(snapshot);

        if (snapshot.DbModBefore != snapshot.DbModAfter)
        {
            throw new InvalidOperationException(
                $"Drawing setup audit changed DBMOD from {snapshot.DbModBefore} to {snapshot.DbModAfter}.");
        }

        var styles = new SortedDictionary<string, object>(StringComparer.Ordinal)
        {
            ["dimension"] = SortedStrings(snapshot.DimensionStyles),
            ["mleader"] = SortedStrings(snapshot.MLeaderStyles),
            ["table"] = SortedStrings(snapshot.TableStyles),
            ["text"] = snapshot.TextStyles
                .Select(style => style.Name)
                .OrderBy(name => name, StringComparer.Ordinal)
                .ToArray()
        };
        var fontReport = new SortedDictionary<string, object>(StringComparer.Ordinal)
        {
            ["missing"] = SortedStrings(snapshot.MissingFonts),
            ["substituted"] = SortedStrings(snapshot.SubstitutedFonts)
        };

        return new Dictionary<string, JsonElement>(StringComparer.Ordinal)
        {
            ["changed"] = JsonSerializer.SerializeToElement(false),
            ["dbmod_before"] = JsonSerializer.SerializeToElement(snapshot.DbModBefore),
            ["dbmod_after"] = JsonSerializer.SerializeToElement(snapshot.DbModAfter),
            ["variables"] = JsonSerializer.SerializeToElement(SortedMapping(snapshot.Variables)),
            ["current_layer"] = JsonSerializer.SerializeToElement(snapshot.CurrentLayer),
            ["custom_properties"] = JsonSerializer.SerializeToElement(
                SortedMapping(snapshot.CustomProperties)),
            ["layers"] = JsonSerializer.SerializeToElement(
                snapshot.Layers
                    .OrderBy(layer => layer.Name, StringComparer.Ordinal)
                    .ThenBy(layer => layer.Linetype, StringComparer.Ordinal)
                    .Select(layer => new SortedDictionary<string, object>(StringComparer.Ordinal)
                    {
                        ["linetype"] = layer.Linetype,
                        ["name"] = layer.Name,
                        ["plottable"] = layer.Plottable
                    })
                    .ToArray()),
            ["styles"] = JsonSerializer.SerializeToElement(styles),
            ["layouts"] = JsonSerializer.SerializeToElement(
                snapshot.Layouts
                    .OrderBy(layout => layout.Name, StringComparer.Ordinal)
                    .Select(layout => new SortedDictionary<string, object>(StringComparer.Ordinal)
                    {
                        ["locked"] = layout.Locked,
                        ["name"] = layout.Name,
                        ["viewport_scales"] = layout.ViewportScales.OrderBy(scale => scale).ToArray()
                    })
                    .ToArray()),
            ["font_report"] = JsonSerializer.SerializeToElement(fontReport)
        };
    }

    private static string[] SortedStrings(IEnumerable<string> values) =>
        values.OrderBy(value => value, StringComparer.Ordinal).ToArray();

    private static SortedDictionary<string, TValue> SortedMapping<TValue>(
        IEnumerable<KeyValuePair<string, TValue>> values)
    {
        var result = new SortedDictionary<string, TValue>(StringComparer.Ordinal);
        foreach (var (key, value) in values)
        {
            result[key] = value;
        }

        return result;
    }
}
