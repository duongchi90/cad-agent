using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Globalization;
using System.Security.Cryptography;
using System.Text.Json;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Geometry;
using CadAgent.AutoCAD2027.Ipc;
using CadAgent.AutoCAD2027.Review;
using AcadApplication = Autodesk.AutoCAD.ApplicationServices.Application;

namespace CadAgent.AutoCAD2027.Drawing;

internal static class AutoCadVisualEvidenceReader
{
    private static readonly string[] RendererSystemVariableNames =
    {
        "TILEMODE",
        "CVPORT",
        "CLAYER",
        "LTSCALE",
        "CELTSCALE",
        "MSLTSCALE",
        "PSLTSCALE",
        "ANNOALLVISIBLE"
    };

    public static VisualEvidenceSnapshot Export(
        Document document,
        VisualEvidenceRequest request,
        string ipcDirectory,
        DateTimeOffset capturedAtUtc)
    {
        ArgumentNullException.ThrowIfNull(document);
        ArgumentNullException.ThrowIfNull(request);
        var database = document.Database
            ?? throw new InvalidOperationException("The active document has no database.");
        var drawingPath = ContractValidator.NormalizeWindowsAbsolutePath(database.Filename);
        var requestPath = ContractValidator.NormalizeWindowsAbsolutePath(request.DrawingFullPath);
        if (!StringComparer.OrdinalIgnoreCase.Equals(drawingPath, requestPath))
        {
            throw new InvalidOperationException("The requested drawing path does not match the active AutoCAD document.");
        }

        var drawingHashBefore = HashFile(drawingPath);
        if (!string.Equals(drawingHashBefore, request.DrawingSha256, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("The drawing hash changed before the VS-T3 export started.");
        }

        var dbmodBefore = ReadDbMod();
        var stateBefore = CaptureSessionState(document);
        RequestOwnedArtifactStore? store = null;
        IDisposable? lease = null;
        try
        {
            var requestId = GetRequestIdFromArtifactDirectory(request.ArtifactDirectory);
            store = RequestOwnedArtifactStore.Create(ipcDirectory, requestId, request.ArtifactDirectory);
            lease = store.AcquireLease();

            var entities = ReadModelSpaceEntities(database, request.Region);
            var projectedEntities = VisualEvidenceProjection.ProjectEntities(entities);
            if (projectedEntities.Count > VisualEvidenceArtifactPolicy.MaxEntityRecords)
            {
                throw new InvalidDataException("The VS-T3 entity limit was exceeded.");
            }

            if (request.Measurements.Count > VisualEvidenceArtifactPolicy.MaxMeasurementRecords)
            {
                throw new InvalidDataException("The VS-T3 measurement limit was exceeded.");
            }

            var measurements = EvaluateMeasurements(request.Measurements, projectedEntities);
            var renderBytes = RenderRegion(request.Region, projectedEntities);
            var entityBytes = JsonSerializer.SerializeToUtf8Bytes(projectedEntities.Select(entity => new
            {
                stable_id = entity.StableId,
                handle = entity.Handle,
                type = entity.Type,
                layer = entity.Layer,
                geometry = entity.Geometry
            }).ToArray());
            var measurementBytes = JsonSerializer.SerializeToUtf8Bytes(measurements.ToArray());

            var renderWidth = request.Region.GetProperty("pixel_size")[0].GetInt32();
            var renderHeight = request.Region.GetProperty("pixel_size")[1].GetInt32();
            var artifacts = new List<EvidenceArtifactDescriptor>
            {
                store.Write("render", "cad-render.png", "image/png", renderBytes, renderWidth, renderHeight),
                store.Write("entity-map", "entities.json", "application/json", entityBytes),
                store.Write("measurements", "measurements.json", "application/json", measurementBytes)
            };

            var dbmodAfter = ReadDbMod();
            var drawingHashAfter = HashFile(drawingPath);
            var stateAfter = CaptureSessionState(document);
            var snapshot = new VisualEvidenceSnapshot(
                document.Database.Filename,
                request.DrawingFullPath,
                request.RunId,
                request.EvidenceId,
                request.RegionId,
                drawingHashBefore,
                drawingHashAfter,
                dbmodBefore,
                dbmodAfter,
                request.LatestMutationSha256,
                request.VisualRunManifestSha256,
                VisualEvidenceProjection.CanonicalRegionConfigSha256(request.Region),
                stateBefore.FingerprintSha256,
                stateAfter.FingerprintSha256,
                string.Equals(stateBefore.FingerprintSha256, stateAfter.FingerprintSha256, StringComparison.Ordinal),
                capturedAtUtc.ToUniversalTime(),
                artifacts,
                Changed: false,
                EntityHandles: Array.Empty<string>());
            var errors = VisualEvidenceReadOnlyBoundary.Validate(request, snapshot);
            if (errors.Count != 0)
            {
                throw new InvalidOperationException(string.Join("; ", errors));
            }

            lease.Dispose();
            lease = null;
            store.Dispose();
            store = null;
            return snapshot;
        }
        catch
        {
            lease?.Dispose();
            lease = null;
            if (store is not null)
            {
                try
                {
                    store.CleanupOnFailure();
                }
                catch
                {
                    // Preserve the original export failure. The scavenger will handle
                    // an orphaned request directory once its lease-free TTL expires.
                }
            }

            throw;
        }
    }

    private static IReadOnlyList<EntitySnapshot> ReadModelSpaceEntities(
        Database database,
        JsonElement region)
    {
        var includeLayers = region.GetProperty("include_layers")
            .EnumerateArray()
            .Select(value => value.GetString()!)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
        var excludeLayers = region.GetProperty("exclude_layers")
            .EnumerateArray()
            .Select(value => value.GetString()!)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
        var snapshots = new List<EntitySnapshot>();
        using var transaction = database.TransactionManager.StartOpenCloseTransaction();
        var blockTable = (BlockTable)transaction.GetObject(database.BlockTableId, OpenMode.ForRead);
        var modelSpace = (BlockTableRecord)transaction.GetObject(
            blockTable[BlockTableRecord.ModelSpace],
            OpenMode.ForRead);
        foreach (var objectId in modelSpace)
        {
            if (transaction.GetObject(objectId, OpenMode.ForRead, false) is not Entity entity)
            {
                continue;
            }

            if ((includeLayers.Count > 0 && !includeLayers.Contains(entity.Layer))
                || excludeLayers.Contains(entity.Layer))
            {
                continue;
            }

            snapshots.Add(CreateSnapshot(entity));
        }

        return snapshots;
    }

    private static EntitySnapshot CreateSnapshot(Entity entity)
    {
        var geometry = new Dictionary<string, JsonElement>(StringComparer.Ordinal);
        var type = entity switch
        {
            Line => ReviewEntityTypes.Line,
            Circle => ReviewEntityTypes.Circle,
            Arc => ReviewEntityTypes.Arc,
            DBText => ReviewEntityTypes.Text,
            Dimension => ReviewEntityTypes.Dimension,
            _ => entity.GetType().Name.ToUpperInvariant()
        };
        try
        {
            var extents = entity.GeometricExtents;
            geometry["bounding_box"] = JsonSerializer.SerializeToElement(new
            {
                min_x = extents.MinPoint.X,
                min_y = extents.MinPoint.Y,
                max_x = extents.MaxPoint.X,
                max_y = extents.MaxPoint.Y
            });
        }
        catch (Autodesk.AutoCAD.Runtime.Exception)
        {
            // Some proxy/empty entities do not expose extents. Their identity is
            // still retained in the read-only map, without inventing geometry.
        }

        switch (entity)
        {
            case Line line:
                AddPoint(geometry, "start", line.StartPoint);
                AddPoint(geometry, "end", line.EndPoint);
                break;
            case Circle circle:
                AddPoint(geometry, "center", circle.Center);
                geometry["radius"] = JsonSerializer.SerializeToElement(circle.Radius);
                break;
            case Arc arc:
                AddPoint(geometry, "center", arc.Center);
                geometry["radius"] = JsonSerializer.SerializeToElement(arc.Radius);
                geometry["start_angle"] = JsonSerializer.SerializeToElement(arc.StartAngle);
                geometry["end_angle"] = JsonSerializer.SerializeToElement(arc.EndAngle);
                break;
            case DBText text:
                AddPoint(geometry, "position", text.Position);
                geometry["height"] = JsonSerializer.SerializeToElement(text.Height);
                geometry["text"] = JsonSerializer.SerializeToElement(text.TextString);
                break;
            case Dimension dimension:
                geometry["measurement"] = JsonSerializer.SerializeToElement(dimension.Measurement);
                break;
        }

        return new EntitySnapshot(entity.Handle.ToString(), type, entity.Layer, geometry);
    }

    private static IReadOnlyList<object> EvaluateMeasurements(
        IReadOnlyList<JsonElement> requests,
        IReadOnlyList<VisualEvidenceEntityRecord> entities)
    {
        var byId = entities.ToDictionary(entity => entity.StableId, StringComparer.Ordinal);
        var byHandle = entities.ToDictionary(entity => entity.Handle, StringComparer.OrdinalIgnoreCase);
        return requests.Select(request =>
        {
            var projection = VisualEvidenceProjection.ProjectMeasurements(new[] { request })[0];
            var first = ResolveReference(projection.Reference, byId, byHandle);
            var value = projection.Kind switch
            {
                "RADIUS" => ReadRadius(first),
                "DIAMETER" => ReadRadius(first) * 2,
                "BOUNDING_BOX" => ReadBoundingBox(first),
                "DISTANCE" => ResolveDistance(projection, first, byId, byHandle),
                "ANGLE" => ResolveAngle(projection, first, byId, byHandle),
                _ => throw new InvalidDataException($"Unsupported measurement kind '{projection.Kind}'.")
            };
            return new
            {
                id = projection.Id,
                kind = projection.Kind,
                reference = projection.Reference,
                to_reference = projection.ToReference,
                value,
                status = "PASSED"
            };
        }).ToArray();
    }

    private static VisualEvidenceEntityRecord ResolveReference(
        JsonElement reference,
        IReadOnlyDictionary<string, VisualEvidenceEntityRecord> byId,
        IReadOnlyDictionary<string, VisualEvidenceEntityRecord> byHandle)
    {
        var type = reference.GetProperty("type").GetString();
        var id = reference.GetProperty("id").GetString()!;
        if (!string.Equals(type, "ENTITY", StringComparison.Ordinal))
        {
            throw new InvalidDataException($"The measurement datum reference '{id}' is unresolved.");
        }

        if (byId.TryGetValue(id, out var stable)
            || byId.TryGetValue($"ENTITY:{id.ToUpperInvariant()}", out stable)
            || byHandle.TryGetValue(id, out stable))
        {
            return stable;
        }

        throw new InvalidDataException($"The measurement entity reference '{id}' is unresolved.");
    }

    private static double ReadRadius(VisualEvidenceEntityRecord entity)
    {
        if (!entity.Geometry.TryGetValue("radius", out var radius)
            || radius.ValueKind != JsonValueKind.Number)
        {
            throw new InvalidDataException($"Entity '{entity.StableId}' has no radius metadata.");
        }

        return radius.GetDouble();
    }

    private static object ReadBoundingBox(VisualEvidenceEntityRecord entity)
    {
        if (!entity.Geometry.TryGetValue("bounding_box", out var boundingBox))
        {
            throw new InvalidDataException($"Entity '{entity.StableId}' has no bounding-box metadata.");
        }

        return boundingBox;
    }

    private static double ResolveDistance(
        VisualEvidenceMeasurementRecord measurement,
        VisualEvidenceEntityRecord first,
        IReadOnlyDictionary<string, VisualEvidenceEntityRecord> byId,
        IReadOnlyDictionary<string, VisualEvidenceEntityRecord> byHandle)
    {
        if (measurement.ToReference is not JsonElement toReference)
        {
            throw new InvalidDataException($"Distance measurement '{measurement.Id}' has no to_reference.");
        }

        var second = ResolveReference(toReference, byId, byHandle);
        var firstPoint = RepresentativePoint(first);
        var secondPoint = RepresentativePoint(second);
        return Math.Sqrt(Math.Pow(firstPoint.X - secondPoint.X, 2) + Math.Pow(firstPoint.Y - secondPoint.Y, 2));
    }

    private static double ResolveAngle(
        VisualEvidenceMeasurementRecord measurement,
        VisualEvidenceEntityRecord first,
        IReadOnlyDictionary<string, VisualEvidenceEntityRecord> byId,
        IReadOnlyDictionary<string, VisualEvidenceEntityRecord> byHandle)
    {
        if (measurement.ToReference is not JsonElement toReference)
        {
            throw new InvalidDataException($"Angle measurement '{measurement.Id}' has no to_reference.");
        }

        var second = ResolveReference(toReference, byId, byHandle);
        var firstPoint = RepresentativePoint(first);
        var secondPoint = RepresentativePoint(second);
        var angle = Math.Atan2(secondPoint.Y - firstPoint.Y, secondPoint.X - firstPoint.X);
        return angle * 180 / Math.PI;
    }

    private static PointF RepresentativePoint(VisualEvidenceEntityRecord entity)
    {
        if (entity.Geometry.TryGetValue("center_x", out var centerX)
            && entity.Geometry.TryGetValue("center_y", out var centerY))
        {
            return new PointF(centerX.GetSingle(), centerY.GetSingle());
        }

        if (entity.Geometry.TryGetValue("start_x", out var startX)
            && entity.Geometry.TryGetValue("start_y", out var startY))
        {
            return new PointF(startX.GetSingle(), startY.GetSingle());
        }

        if (entity.Geometry.TryGetValue("bounding_box", out var box))
        {
            return new PointF(
                (float)((box.GetProperty("min_x").GetDouble() + box.GetProperty("max_x").GetDouble()) / 2),
                (float)((box.GetProperty("min_y").GetDouble() + box.GetProperty("max_y").GetDouble()) / 2));
        }

        throw new InvalidDataException($"Entity '{entity.StableId}' has no point metadata.");
    }

    private static byte[] RenderRegion(
        JsonElement region,
        IReadOnlyList<VisualEvidenceEntityRecord> entities)
    {
        var bbox = region.GetProperty("model_bbox_mm").EnumerateArray().Select(value => value.GetDouble()).ToArray();
        var pixels = region.GetProperty("pixel_size").EnumerateArray().Select(value => value.GetInt32()).ToArray();
        var background = string.Equals(region.GetProperty("background").GetString(), "BLACK", StringComparison.Ordinal)
            ? Color.Black
            : Color.White;
        using var bitmap = new Bitmap(pixels[0], pixels[1], PixelFormat.Format24bppRgb);
        using var graphics = Graphics.FromImage(bitmap);
        graphics.Clear(background);
        graphics.SmoothingMode = SmoothingMode.None;
        using var pen = new Pen(background == Color.Black ? Color.White : Color.Black, 1);
        foreach (var entity in entities)
        {
            DrawEntity(graphics, pen, entity, bbox, pixels[0], pixels[1]);
        }

        using var stream = new MemoryStream();
        bitmap.Save(stream, ImageFormat.Png);
        return stream.ToArray();
    }

    private static void DrawEntity(
        Graphics graphics,
        Pen pen,
        VisualEvidenceEntityRecord entity,
        IReadOnlyList<double> bbox,
        int width,
        int height)
    {
        PointF Transform(double x, double y) => new(
            (float)((x - bbox[0]) / (bbox[2] - bbox[0]) * (width - 1)),
            (float)((bbox[3] - y) / (bbox[3] - bbox[1]) * (height - 1)));

        if (entity.Geometry.TryGetValue("start_x", out var startX)
            && entity.Geometry.TryGetValue("start_y", out var startY)
            && entity.Geometry.TryGetValue("end_x", out var endX)
            && entity.Geometry.TryGetValue("end_y", out var endY))
        {
            graphics.DrawLine(pen, Transform(startX.GetDouble(), startY.GetDouble()), Transform(endX.GetDouble(), endY.GetDouble()));
            return;
        }

        if (entity.Geometry.TryGetValue("center_x", out var centerX)
            && entity.Geometry.TryGetValue("center_y", out var centerY)
            && entity.Geometry.TryGetValue("radius", out var radius))
        {
            var center = Transform(centerX.GetDouble(), centerY.GetDouble());
            var radiusPixelsX = (float)(radius.GetDouble() / (bbox[2] - bbox[0]) * (width - 1));
            var radiusPixelsY = (float)(radius.GetDouble() / (bbox[3] - bbox[1]) * (height - 1));
            if (entity.Geometry.TryGetValue("start_angle", out var startAngle)
                && entity.Geometry.TryGetValue("end_angle", out var endAngle))
            {
                graphics.DrawArc(pen, center.X - radiusPixelsX, center.Y - radiusPixelsY, radiusPixelsX * 2, radiusPixelsY * 2,
                    (float)-RadiansToDegrees(endAngle.GetDouble()),
                    (float)-RadiansToDegrees(endAngle.GetDouble() - startAngle.GetDouble()));
            }
            else
            {
                graphics.DrawEllipse(pen, center.X - radiusPixelsX, center.Y - radiusPixelsY, radiusPixelsX * 2, radiusPixelsY * 2);
            }
        }
    }

    private static double RadiansToDegrees(double radians) => radians * 180 / Math.PI;

    private static SessionStateSnapshot CaptureSessionState(Document document)
    {
        var database = document.Database;
        var layerStates = new Dictionary<string, bool>(StringComparer.Ordinal);
        using (var transaction = database.TransactionManager.StartOpenCloseTransaction())
        {
            var layerTable = (LayerTable)transaction.GetObject(database.LayerTableId, OpenMode.ForRead);
            foreach (ObjectId layerId in layerTable)
            {
                var layer = (LayerTableRecord)transaction.GetObject(layerId, OpenMode.ForRead);
                layerStates[layer.Name] = !layer.IsOff && !layer.IsFrozen;
            }
        }

        var variables = RendererSystemVariableNames.ToDictionary(
            name => name,
            name => Convert.ToString(AcadApplication.GetSystemVariable(name), CultureInfo.InvariantCulture) ?? string.Empty,
            StringComparer.Ordinal);
        var selectionHandles = Array.Empty<string>();
        var currentLayer = Convert.ToString(
            AcadApplication.GetSystemVariable("CLAYER"),
            CultureInfo.InvariantCulture) ?? string.Empty;
        var currentLayout = LayoutManager.Current.CurrentLayout;
        var modelSpace = Convert.ToInt32(AcadApplication.GetSystemVariable("TILEMODE"), CultureInfo.InvariantCulture) != 0;
        var cvport = Convert.ToInt32(AcadApplication.GetSystemVariable("CVPORT"), CultureInfo.InvariantCulture);
        var viewProperties = string.Join(
            "|",
            RendererSystemVariableNames.Select(name => $"{name}={variables[name]}"));
        return SessionStateSnapshot.Create(
            database.Filename,
            database.Filename,
            currentLayout,
            modelSpace,
            cvport,
            currentLayer,
            viewProperties,
            selectionHandles,
            layerStates,
            variables);
    }

    private static long ReadDbMod() => Convert.ToInt64(
        AcadApplication.GetSystemVariable("DBMOD"),
        CultureInfo.InvariantCulture);

    private static string HashFile(string path)
    {
        using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }

    private static string GetRequestIdFromArtifactDirectory(string artifactDirectory)
    {
        var normalized = artifactDirectory.Replace('\\', '/');
        var requestId = normalized.Split('/', StringSplitOptions.RemoveEmptyEntries).LastOrDefault();
        if (string.IsNullOrWhiteSpace(requestId))
        {
            throw new InvalidDataException("artifact_directory does not contain a request ID.");
        }

        ContractValidator.EnsureRequestId(requestId);
        return requestId;
    }

    private static void AddPoint(
        IDictionary<string, JsonElement> geometry,
        string prefix,
        Point3d point)
    {
        geometry[$"{prefix}_x"] = JsonSerializer.SerializeToElement(point.X);
        geometry[$"{prefix}_y"] = JsonSerializer.SerializeToElement(point.Y);
    }
}
