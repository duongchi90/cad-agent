using System.Text.Json;
using System.Text.RegularExpressions;

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

        var payload = new Dictionary<string, JsonElement>(StringComparer.Ordinal)
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

        if (snapshot.ModelSpaceInventory is not null)
        {
            payload["model_space_inventory"] = JsonSerializer.SerializeToElement(
                CreateModelSpaceInventoryPayload(snapshot.ModelSpaceInventory));
        }

        return payload;
    }

    private static SortedDictionary<string, object?> CreateModelSpaceInventoryPayload(
        ModelSpaceInventorySnapshot inventory)
    {
        ArgumentNullException.ThrowIfNull(inventory);
        if (inventory.Entities.Count > Ipc.ContractConstants.ModelSpaceInventoryMaxEntityCount
            || inventory.EntityCount != inventory.Entities.Count
            || !inventory.EnumerationComplete
            || inventory.DbModBefore != 0
            || inventory.DbModAfter != 0
            || inventory.ProcessId <= 0
            || string.IsNullOrWhiteSpace(inventory.DrawingFullPath)
            || string.IsNullOrWhiteSpace(inventory.PluginVersion)
            || string.IsNullOrWhiteSpace(inventory.PluginBinaryPath)
            || !IsSha256(inventory.DrawingSha256Before)
            || !IsSha256(inventory.DrawingSha256After)
            || !string.Equals(
                inventory.DrawingSha256Before,
                inventory.DrawingSha256After,
                StringComparison.OrdinalIgnoreCase)
            || !IsSha256(inventory.PluginBinarySha256))
        {
            throw new InvalidDataException("ModelSpace inventory identity or completeness is invalid.");
        }

        var seenHandles = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var boundsComplete = true;
        var entities = new List<SortedDictionary<string, object?>>(inventory.Entities.Count);
        foreach (var entity in inventory.Entities.OrderBy(item => item.Handle, StringComparer.OrdinalIgnoreCase))
        {
            if (string.IsNullOrWhiteSpace(entity.Handle)
                || string.IsNullOrWhiteSpace(entity.Type)
                || !seenHandles.Add(entity.Handle))
            {
                throw new InvalidDataException("ModelSpace inventory contains an invalid or duplicate entity identity.");
            }

            object? bounds = null;
            switch (entity.BoundsStatus)
            {
                case "BOUNDS_READ":
                    if (entity.Bounds is not { Length: 6 }
                        || entity.Bounds.Any(value => !double.IsFinite(value))
                        || entity.Bounds[0] > entity.Bounds[3]
                        || entity.Bounds[1] > entity.Bounds[4]
                        || entity.Bounds[2] > entity.Bounds[5])
                    {
                        throw new InvalidDataException(
                            $"ModelSpace inventory bounds are invalid for handle '{entity.Handle}'.");
                    }
                    bounds = entity.Bounds;
                    break;
                case "UNSUPPORTED":
                case "UNREADABLE":
                case "NONFINITE":
                    if (entity.Bounds is not null)
                    {
                        throw new InvalidDataException(
                            $"ModelSpace inventory non-readable bounds must be absent for handle '{entity.Handle}'.");
                    }
                    boundsComplete = false;
                    break;
                default:
                    throw new InvalidDataException(
                        $"ModelSpace inventory has an unsupported bounds status for handle '{entity.Handle}'.");
            }

            entities.Add(new SortedDictionary<string, object?>(StringComparer.Ordinal)
            {
                ["bounds"] = bounds,
                ["bounds_status"] = entity.BoundsStatus,
                ["handle"] = entity.Handle,
                ["type"] = entity.Type
            });
        }

        if (inventory.BoundsComplete != boundsComplete)
        {
            throw new InvalidDataException("ModelSpace inventory bounds completeness is inconsistent.");
        }

        return new SortedDictionary<string, object?>(StringComparer.Ordinal)
        {
            ["bounds_complete"] = inventory.BoundsComplete,
            ["dbmod_after"] = inventory.DbModAfter,
            ["dbmod_before"] = inventory.DbModBefore,
            ["drawing_full_path"] = inventory.DrawingFullPath,
            ["drawing_sha256_after"] = inventory.DrawingSha256After,
            ["drawing_sha256_before"] = inventory.DrawingSha256Before,
            ["entities"] = entities,
            ["entity_count"] = inventory.EntityCount,
            ["enumeration_complete"] = inventory.EnumerationComplete,
            ["plugin_binary_path"] = inventory.PluginBinaryPath,
            ["plugin_binary_sha256"] = inventory.PluginBinarySha256,
            ["plugin_version"] = inventory.PluginVersion,
            ["process_id"] = inventory.ProcessId
        };
    }

    private static bool IsSha256(string value) =>
        Regex.IsMatch(value, "^[0-9a-fA-F]{64}$", RegexOptions.CultureInvariant);

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
