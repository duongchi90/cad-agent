using System.Text.Json;

namespace CadAgent.AutoCAD2027.Drawing;

public static class DrawingSetupPayload
{
    public static Dictionary<string, JsonElement> Create(DrawingSetupSnapshot snapshot)
    {
        ArgumentNullException.ThrowIfNull(snapshot);

        return new Dictionary<string, JsonElement>(StringComparer.Ordinal)
        {
            ["drawing_full_path"] = Json(snapshot.DrawingFullPath),
            ["dbmod_before"] = Json(snapshot.DbModBefore),
            ["dbmod_after"] = Json(snapshot.DbModAfter),
            ["changed"] = Json(snapshot.DbModBefore != snapshot.DbModAfter),
            ["variables"] = Json(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["INSUNITS"] = snapshot.InsUnits,
                ["MEASUREMENT"] = snapshot.Measurement,
                ["LTSCALE"] = snapshot.LtScale,
                ["CELTSCALE"] = snapshot.Celtscale,
                ["PSLTSCALE"] = snapshot.PsLtScale,
                ["MSLTSCALE"] = snapshot.MsLtScale,
                ["DIMASSOC"] = snapshot.DimAssoc,
                ["ANNOALLVISIBLE"] = snapshot.AnnoAllVisible
            }),
            ["current_layer"] = Json(snapshot.CurrentLayer),
            ["custom_properties"] = Json(snapshot.CustomProperties
                .OrderBy(item => item.Key, StringComparer.Ordinal)
                .ToDictionary(item => item.Key, item => item.Value, StringComparer.Ordinal)),
            ["layers"] = Json(snapshot.Layers
                .OrderBy(item => item.Name, StringComparer.Ordinal)
                .Select(LayerPayload)
                .ToArray()),
            ["styles"] = Json(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["text"] = snapshot.TextStyles
                    .OrderBy(item => item.Name, StringComparer.Ordinal)
                    .Select(item => item.Name)
                    .ToArray(),
                ["dimension"] = snapshot.DimensionStyles
                    .OrderBy(item => item.Name, StringComparer.Ordinal)
                    .Select(item => item.Name)
                    .ToArray(),
                ["mleader"] = snapshot.MLeaderStyles
                    .OrderBy(item => item.Name, StringComparer.Ordinal)
                    .Select(item => item.Name)
                    .ToArray(),
                ["table"] = snapshot.TableStyles
                    .OrderBy(item => item.Name, StringComparer.Ordinal)
                    .Select(item => item.Name)
                    .ToArray()
            }),
            ["text_styles"] = Json(snapshot.TextStyles
                .OrderBy(item => item.Name, StringComparer.Ordinal)
                .Select(item => new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["name"] = item.Name,
                    ["font"] = item.Font,
                    ["big_font"] = item.BigFont
                })
                .ToArray()),
            ["dimension_styles"] = Json(snapshot.DimensionStyles
                .OrderBy(item => item.Name, StringComparer.Ordinal)
                .Select(item => item.Name)
                .ToArray()),
            ["mleader_styles"] = Json(snapshot.MLeaderStyles
                .OrderBy(item => item.Name, StringComparer.Ordinal)
                .Select(item => item.Name)
                .ToArray()),
            ["table_styles"] = Json(snapshot.TableStyles
                .OrderBy(item => item.Name, StringComparer.Ordinal)
                .Select(item => item.Name)
                .ToArray()),
            ["layouts"] = Json(snapshot.Layouts
                .OrderBy(item => item.Name, StringComparer.Ordinal)
                .Select(LayoutPayload)
                .ToArray())
        };
    }

    private static Dictionary<string, object?> LayerPayload(LayerSetupSnapshot layer) =>
        new(StringComparer.Ordinal)
        {
            ["name"] = layer.Name,
            ["color_index"] = layer.ColorIndex,
            ["linetype"] = layer.Linetype,
            ["lineweight"] = layer.LineWeight,
            ["plottable"] = layer.Plottable,
            ["frozen"] = layer.Frozen,
            ["locked"] = layer.Locked
        };

    private static Dictionary<string, object?> LayoutPayload(LayoutSetupSnapshot layout) =>
        new(StringComparer.Ordinal)
        {
            ["name"] = layout.Name,
            ["is_model"] = layout.IsModel,
            ["canonical_media_name"] = layout.CanonicalMediaName,
            ["plot_device"] = layout.PlotDevice,
            ["plot_type"] = layout.PlotType,
            ["scale_numerator"] = layout.ScaleNumerator,
            ["scale_denominator"] = layout.ScaleDenominator,
            ["viewports"] = layout.Viewports
                .OrderBy(item => item.Handle, StringComparer.Ordinal)
                .Select(item => new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["handle"] = item.Handle,
                    ["custom_scale"] = item.CustomScale,
                    ["locked"] = item.Locked
                })
                .ToArray()
        };

    private static JsonElement Json(object? value) => JsonSerializer.SerializeToElement(value);
}
