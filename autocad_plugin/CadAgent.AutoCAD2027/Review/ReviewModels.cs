using System.Text.Json;

namespace CadAgent.AutoCAD2027.Review;

public static class ReviewEntityTypes
{
    public const string Line = "LINE";
    public const string Circle = "CIRCLE";
    public const string Arc = "ARC";
    public const string Text = "TEXT";
    public const string Dimension = "DIMENSION";
    public const string Spline = "SPLINE";
    public const string LwPolyline = "LWPOLYLINE";
    public const string Polyline = "POLYLINE";
    public const string Ellipse = "ELLIPSE";
    public const string MText = "MTEXT";
    public const string Insert = "INSERT";
    public const int MaxReviewEntityCount = 50_000;
    public const int MaxReviewSampledPoints = 16;

    public static bool TryNormalize(string? value, out string normalized)
    {
        normalized = value?.Trim().ToUpperInvariant() switch
        {
            "LINE" or "ACDBLINE" => Line,
            "CIRCLE" or "ACDBCIRCLE" => Circle,
            "ARC" or "ACDBARC" => Arc,
            "TEXT" or "DBTEXT" or "ACDBTEXT" => Text,
            "DIMENSION" or "ACDBDIMENSION" => Dimension,
            _ => string.Empty
        };

        return normalized.Length != 0;
    }

    public static bool TryNormalizeExtended(string? value, out string normalized)
    {
        if (TryNormalize(value, out normalized))
        {
            return true;
        }

        normalized = value?.Trim().ToUpperInvariant() switch
        {
            "SPLINE" or "ACDBSPLINE" => Spline,
            "LWPOLYLINE" => LwPolyline,
            "POLYLINE" or "POLYLINE2D" or "POLYLINE3D" or "ACDBPOLYLINE" or "ACDB2DPOLYLINE" or "ACDB3DPOLYLINE" => Polyline,
            "ELLIPSE" or "ACDBELLIPSE" => Ellipse,
            "MTEXT" or "ACDBMTEXT" => MText,
            "INSERT" or "BLOCKREFERENCE" or "BLOCK_REFERENCE" or "ACDBBLOCKREFERENCE" => Insert,
            _ => string.Empty
        };

        return normalized.Length != 0;
    }
}

public sealed record ReviewRequest(
    string? DrawingFullPath,
    IReadOnlyList<string> Handles,
    bool IncludeExtendedEntities = false);

public sealed record EntitySnapshot(
    string? Handle,
    string? Type,
    string? Layer,
    IReadOnlyDictionary<string, JsonElement>? Geometry);

public sealed record ReviewEntity(
    string Handle,
    string Type,
    string Layer,
    IReadOnlyDictionary<string, JsonElement> Geometry);

public sealed record ReviewResult
{
    public bool Success { get; init; }

    public string? DrawingFullPath { get; init; }

    public bool Changed { get; init; }

    public IReadOnlyList<string> EntityHandles { get; init; } = Array.Empty<string>();

    public IReadOnlyList<ReviewEntity> Entities { get; init; } = Array.Empty<ReviewEntity>();

    public IReadOnlyList<string> Warnings { get; init; } = Array.Empty<string>();

    public IReadOnlyList<string> Errors { get; init; } = Array.Empty<string>();

    public IReadOnlyDictionary<string, JsonElement> Payload { get; init; } =
        new Dictionary<string, JsonElement>(StringComparer.Ordinal);
}
