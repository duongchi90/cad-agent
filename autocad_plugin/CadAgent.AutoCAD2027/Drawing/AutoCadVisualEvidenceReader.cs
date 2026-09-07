using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Globalization;
using System.Security.Cryptography;
using System.Runtime.CompilerServices;
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
    private sealed record NestedEntityProjection(
        string Type,
        string Layer,
        Dictionary<string, object?> Geometry);

    private sealed class RenderLayerPolicy
    {
        private readonly IReadOnlySet<string> _includeLayers;
        private readonly IReadOnlySet<string> _excludeLayers;
        private readonly IReadOnlyDictionary<string, SessionLayerSnapshot> _layerStates;

        public RenderLayerPolicy(
            IReadOnlySet<string> includeLayers,
            IReadOnlySet<string> excludeLayers,
            IReadOnlyDictionary<string, SessionLayerSnapshot> layerStates)
        {
            _includeLayers = includeLayers;
            _excludeLayers = excludeLayers;
            _layerStates = layerStates.ToDictionary(
                item => item.Key,
                item => item.Value,
                StringComparer.OrdinalIgnoreCase);
        }

        public bool Allows(string layer)
        {
            if (!_layerStates.TryGetValue(layer, out var state))
            {
                throw new InvalidDataException(
                    $"The VS-T3 layer state snapshot is missing layer '{layer}'.");
            }

            if (_includeLayers.Count > 0 && !_includeLayers.Contains(layer))
            {
                return false;
            }

            if (_excludeLayers.Contains(layer))
            {
                return false;
            }

            return !state.IsOff && !state.IsFrozen;
        }
    }

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

    private const int MaxSerializedSampledPoints = 8;

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
        IReadOnlyList<EvidenceArtifactDescriptor>? artifacts = null;
        SessionStateSnapshot? stateAfterRestore = null;
        Exception? operationFailure = null;
        try
        {
            var requestId = GetRequestIdFromArtifactDirectory(request.ArtifactDirectory);
            store = RequestOwnedArtifactStore.Create(ipcDirectory, requestId, request.ArtifactDirectory);
            lease = store.AcquireLease();

            var entities = ReadModelSpaceEntities(database, request.Region, stateBefore.LayerStates);
            var projectedEntities = VisualEvidenceProjection.ProjectEntities(entities);
            if (projectedEntities.Count > VisualEvidenceArtifactPolicy.MaxEntityRecords)
            {
                throw new InvalidDataException("The VS-T3 entity limit was exceeded.");
            }

            if (request.Measurements.Count > VisualEvidenceArtifactPolicy.MaxMeasurementRecords)
            {
                throw new InvalidDataException("The VS-T3 measurement limit was exceeded.");
            }

            var measurements = EvaluateMeasurements(request.Measurements, request.DatumBindings, projectedEntities);
            var renderBytes = RenderRegion(request.Region, projectedEntities);
            var entityBytes = SerializeEntityMap(projectedEntities);
            var measurementBytes = JsonSerializer.SerializeToUtf8Bytes(measurements.ToArray());

            var renderWidth = request.Region.GetProperty("pixel_size")[0].GetInt32();
            var renderHeight = request.Region.GetProperty("pixel_size")[1].GetInt32();
            artifacts = new List<EvidenceArtifactDescriptor>
            {
                store.Write("render", "cad-render.png", "image/png", renderBytes, renderWidth, renderHeight),
                store.Write("entity-map", "entities.json", "application/json", entityBytes),
                store.Write("measurements", "measurements.json", "application/json", measurementBytes)
            };
        }
        catch (Exception exception)
        {
            operationFailure = exception;
        }
        finally
        {
            try
            {
                RestoreSessionState(document, stateBefore);
            }
            catch (Exception exception)
            {
                operationFailure ??= new InvalidOperationException(
                    "VS-T3 could not restore the AutoCAD session state.",
                    exception);
            }

            try
            {
                stateAfterRestore = CaptureSessionState(document);
            }
            catch (Exception exception)
            {
                operationFailure ??= new InvalidOperationException(
                    "VS-T3 could not capture the restored AutoCAD session state.",
                    exception);
            }
        }

        try
        {
            if (operationFailure is not null)
            {
                throw operationFailure;
            }

            if (store is null || artifacts is null || stateAfterRestore is null)
            {
                throw new InvalidOperationException("VS-T3 did not produce a complete evidence snapshot.");
            }

            var dbmodAfter = ReadDbMod();
            var drawingHashAfter = HashFile(drawingPath);
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
                stateAfterRestore.FingerprintSha256,
                string.Equals(stateBefore.FingerprintSha256, stateAfterRestore.FingerprintSha256, StringComparison.Ordinal),
                capturedAtUtc.ToUniversalTime(),
                artifacts,
                Changed: false,
                EntityHandles: Array.Empty<string>());
            var errors = VisualEvidenceReadOnlyBoundary.Validate(request, snapshot);
            if (errors.Count != 0)
            {
                throw new InvalidOperationException(string.Join("; ", errors));
            }

            lease?.Dispose();
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
                    // Preserve the original export failure. The scavenger handles
                    // an orphaned request directory once its lease-free TTL expires.
                }
            }

            throw;
        }
    }

    private static IReadOnlyList<EntitySnapshot> ReadModelSpaceEntities(
        Database database,
        JsonElement region,
        IReadOnlyDictionary<string, SessionLayerSnapshot> layerStates)
    {
        var includeLayers = region.GetProperty("include_layers")
            .EnumerateArray()
            .Select(value => value.GetString()!)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
        var excludeLayers = region.GetProperty("exclude_layers")
            .EnumerateArray()
            .Select(value => value.GetString()!)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
        var bbox = region.GetProperty("model_bbox_mm")
            .EnumerateArray()
            .Select(value => value.GetDouble())
            .ToArray();
        if (bbox[2] <= bbox[0] || bbox[3] <= bbox[1])
        {
            throw new InvalidDataException("The VS-T3 region bounding box must have positive width and height.");
        }
        var layerPolicy = new RenderLayerPolicy(includeLayers, excludeLayers, layerStates);
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

            if (!entity.Visible || !layerPolicy.Allows(entity.Layer))
            {
                continue;
            }

            Extents3d extents;
            try
            {
                extents = entity.GeometricExtents;
            }
            catch (Autodesk.AutoCAD.Runtime.Exception exception)
            {
                if (entity is BlockReference blockReference
                    && IsEmptyBlockReference(blockReference, transaction))
                {
                    continue;
                }

                throw new InvalidDataException(
                    $"Entity '{entity.Handle}' has no readable extents for region filtering.",
                    exception);
            }

            if (extents.MaxPoint.X < bbox[0]
                || extents.MinPoint.X > bbox[2]
                || extents.MaxPoint.Y < bbox[1]
                || extents.MinPoint.Y > bbox[3])
            {
                continue;
            }

            var snapshot = CreateSnapshot(entity, extents, transaction, layerPolicy);
            if (snapshot is not null)
            {
                snapshots.Add(snapshot);
            }
        }

        return snapshots;
    }

    private static bool IsEmptyBlockReference(
        BlockReference blockReference,
        Transaction transaction)
    {
        var blockRecord = (BlockTableRecord)transaction.GetObject(
            blockReference.BlockTableRecord,
            OpenMode.ForRead);
        return !blockRecord
            .Cast<ObjectId>()
            .Any(objectId => transaction.GetObject(objectId, OpenMode.ForRead, false) is Entity);
    }

    private static EntitySnapshot? CreateSnapshot(
        Entity entity,
        Extents3d extents,
        Transaction transaction,
        RenderLayerPolicy layerPolicy)
    {
        var geometry = CreateGeometry(
            entity,
            Matrix3d.Identity,
            transaction,
            new HashSet<ObjectId>(),
            layerPolicy);
        if (entity is BlockReference && !HasRenderableChildren(geometry))
        {
            return null;
        }
        geometry["bounding_box"] = new
        {
            min_x = extents.MinPoint.X,
            min_y = extents.MinPoint.Y,
            max_x = extents.MaxPoint.X,
            max_y = extents.MaxPoint.Y
        };
        var jsonGeometry = geometry.ToDictionary(
            item => item.Key,
            item => JsonSerializer.SerializeToElement(item.Value),
            StringComparer.Ordinal);
        return new EntitySnapshot(entity.Handle.ToString(), GetEntityType(entity), entity.Layer, jsonGeometry);
    }

    private static string GetEntityType(Entity entity)
    {
        return entity switch
        {
            Line => ReviewEntityTypes.Line,
            Circle => ReviewEntityTypes.Circle,
            Arc => ReviewEntityTypes.Arc,
            Ellipse => "ELLIPSE",
            Leader => "LEADER",
            Solid => "SOLID",
            Wipeout => "WIPEOUT",
            Viewport => "VIEWPORT",
            DBText => ReviewEntityTypes.Text,
            Dimension => ReviewEntityTypes.Dimension,
            Polyline => "POLYLINE",
            MText => "MTEXT",
            BlockReference => "BLOCK_REFERENCE",
            Hatch => "HATCH",
            Spline => "SPLINE",
            _ => throw new InvalidDataException(
                $"Entity '{entity.Handle}' has unsupported visible type '{entity.GetType().Name}'.")
        };
    }

    private static Dictionary<string, object?> CreateGeometry(
        Entity entity,
        Matrix3d transform,
        Transaction transaction,
        HashSet<ObjectId> blockStack,
        RenderLayerPolicy layerPolicy,
        string? parentEffectiveLayer = null)
    {
        var geometry = new Dictionary<string, object?>(StringComparer.Ordinal);
        switch (entity)
        {
            case Line line:
                AddPoint(geometry, "start", line.StartPoint.TransformBy(transform));
                AddPoint(geometry, "end", line.EndPoint.TransformBy(transform));
                break;
            case Circle circle:
                AddPoint(geometry, "center", circle.Center.TransformBy(transform));
                geometry["radius"] = TransformRadius(circle.Radius, transform);
                break;
            case Ellipse ellipse:
                geometry["closed"] = ellipse.Closed;
                geometry["sampled_points"] = Enumerable.Range(0, 65)
                    .Select(index =>
                    {
                        var parameter = ellipse.StartParam
                            + (ellipse.EndParam - ellipse.StartParam) * index / 64.0;
                        var point = ellipse.GetPointAtParameter(parameter).TransformBy(transform);
                        return new { x = point.X, y = point.Y };
                    })
                    .ToArray();
                break;
            case Arc arc:
                var arcCenter = arc.Center.TransformBy(transform);
                AddPoint(geometry, "center", arcCenter);
                geometry["radius"] = TransformRadius(arc.Radius, transform);
                var arcStart = new Point3d(
                    arc.Center.X + Math.Cos(arc.StartAngle) * arc.Radius,
                    arc.Center.Y + Math.Sin(arc.StartAngle) * arc.Radius,
                    arc.Center.Z).TransformBy(transform);
                var arcEnd = new Point3d(
                    arc.Center.X + Math.Cos(arc.EndAngle) * arc.Radius,
                    arc.Center.Y + Math.Sin(arc.EndAngle) * arc.Radius,
                    arc.Center.Z).TransformBy(transform);
                geometry["start_angle"] = Math.Atan2(arcStart.Y - arcCenter.Y, arcStart.X - arcCenter.X);
                geometry["end_angle"] = Math.Atan2(arcEnd.Y - arcCenter.Y, arcEnd.X - arcCenter.X);
                break;
            case DBText text:
                AddPoint(geometry, "position", text.Position.TransformBy(transform));
                geometry["height"] = TransformRadius(text.Height, transform);
                geometry["text"] = text.TextString;
                geometry["rotation"] = TransformAngle(text.Rotation, transform);
                break;
            case Dimension dimension:
                geometry["measurement"] = dimension.Measurement;
                geometry["text"] = dimension.DimensionText;
                AddPoint(geometry, "text_position", dimension.TextPosition.TransformBy(transform));
                switch (dimension)
                {
                    case AlignedDimension aligned:
                        AddPoint(geometry, "xline1", aligned.XLine1Point.TransformBy(transform));
                        AddPoint(geometry, "xline2", aligned.XLine2Point.TransformBy(transform));
                        AddPoint(geometry, "dimline", aligned.DimLinePoint.TransformBy(transform));
                        break;
                    case RotatedDimension rotated:
                        AddPoint(geometry, "xline1", rotated.XLine1Point.TransformBy(transform));
                        AddPoint(geometry, "xline2", rotated.XLine2Point.TransformBy(transform));
                        AddPoint(geometry, "dimline", rotated.DimLinePoint.TransformBy(transform));
                        break;
                    case LineAngularDimension2 angular:
                        geometry["dimension_kind"] = "LINE_ANGULAR";
                        AddPoint(geometry, "xline1_start", angular.XLine1Start.TransformBy(transform));
                        AddPoint(geometry, "xline1_end", angular.XLine1End.TransformBy(transform));
                        AddPoint(geometry, "xline2_start", angular.XLine2Start.TransformBy(transform));
                        AddPoint(geometry, "xline2_end", angular.XLine2End.TransformBy(transform));
                        AddPoint(geometry, "arc_point", angular.ArcPoint.TransformBy(transform));
                        break;
                    default:
                        throw new InvalidDataException(
                            $"Dimension '{dimension.Handle}' has unsupported visible subtype '{dimension.GetType().Name}'.");
                }
                geometry["height"] = 20.0;
                break;
            case Polyline polyline:
                var polylineReversesOrientation = HasReversedOrientation(transform);
                geometry["closed"] = polyline.Closed;
                geometry["vertices"] = Enumerable.Range(0, polyline.NumberOfVertices)
                        .Select(index => new
                        {
                            point = new Point3d(polyline.GetPoint2dAt(index).X, polyline.GetPoint2dAt(index).Y, 0).TransformBy(transform),
                            bulge = polylineReversesOrientation
                                ? -polyline.GetBulgeAt(index)
                                : polyline.GetBulgeAt(index)
                        })
                    .Select(value => new { x = value.point.X, y = value.point.Y, value.bulge })
                    .ToArray();
                break;
            case Leader leader:
                geometry["closed"] = false;
                geometry["vertices"] = Enumerable.Range(0, leader.NumVertices)
                    .Select(index => ToPointObject(leader.VertexAt(index).TransformBy(transform)))
                    .ToArray();
                break;
            case Solid solid:
                geometry["closed"] = true;
                geometry["vertices"] = Enumerable.Range(0, 4)
                    .Select(index => ToPointObject(solid.GetPointAt((short)index).TransformBy(transform)))
                    .ToArray();
                break;
            case Wipeout wipeout:
                var wipeoutVertices = wipeout.GetVertices().Cast<Point3d>().ToArray();
                if (wipeoutVertices.Length < 2)
                {
                    throw new InvalidDataException(
                        $"Wipeout '{entity.Handle}' has too few deterministic boundary vertices.");
                }

                geometry["closed"] = true;
                geometry["vertices"] = wipeoutVertices
                    .Select(point => ToPointObject(point.TransformBy(transform)))
                    .ToArray();
                break;
            case Viewport viewport:
                var halfWidth = viewport.Width / 2.0;
                var halfHeight = viewport.Height / 2.0;
                geometry["closed"] = true;
                geometry["vertices"] = new[]
                {
                    ToPointObject(new Point3d(viewport.CenterPoint.X - halfWidth, viewport.CenterPoint.Y - halfHeight, viewport.CenterPoint.Z).TransformBy(transform)),
                    ToPointObject(new Point3d(viewport.CenterPoint.X + halfWidth, viewport.CenterPoint.Y - halfHeight, viewport.CenterPoint.Z).TransformBy(transform)),
                    ToPointObject(new Point3d(viewport.CenterPoint.X + halfWidth, viewport.CenterPoint.Y + halfHeight, viewport.CenterPoint.Z).TransformBy(transform)),
                    ToPointObject(new Point3d(viewport.CenterPoint.X - halfWidth, viewport.CenterPoint.Y + halfHeight, viewport.CenterPoint.Z).TransformBy(transform))
                };
                break;
            case MText mtext:
                AddPoint(geometry, "position", mtext.Location.TransformBy(transform));
                geometry["height"] = TransformRadius(mtext.TextHeight, transform);
                geometry["text"] = mtext.Text;
                geometry["rotation"] = TransformAngle(mtext.Rotation, transform);
                break;
            case BlockReference block:
                if (!blockStack.Add(block.BlockTableRecord))
                {
                    throw new InvalidDataException($"Block '{block.Handle}' contains a recursive block reference.");
                }

                try
                {
                    geometry["position"] = ToPointObject(block.Position.TransformBy(transform));
                    geometry["rotation"] = TransformAngle(block.Rotation, transform);
                    var childTransform = block.BlockTransform * transform;
                    if (!IsConformalTransform(childTransform))
                    {
                        throw new InvalidDataException(
                            $"Block '{block.Handle}' has a non-conformal transform; VS-T3 fails closed rather than flattening circles, arcs, or bulges incorrectly.");
                    }
                    var blockRecord = (BlockTableRecord)transaction.GetObject(block.BlockTableRecord, OpenMode.ForRead);
                    geometry["children"] = blockRecord
                        .Cast<ObjectId>()
                        .Select(objectId => transaction.GetObject(objectId, OpenMode.ForRead, false))
                        .OfType<Entity>()
                        .Where(child => child.Visible)
                        .Select(child =>
                        {
                            var effectiveLayer = EffectiveLayer(child.Layer, block.Layer, parentEffectiveLayer);
                            if (!layerPolicy.Allows(effectiveLayer))
                            {
                                return null;
                            }

                            var childGeometry = CreateGeometry(
                                child,
                                childTransform,
                                transaction,
                                blockStack,
                                layerPolicy,
                                effectiveLayer);
                            return child is BlockReference && !HasRenderableChildren(childGeometry)
                                ? null
                                : new NestedEntityProjection(GetEntityType(child), effectiveLayer, childGeometry);
                        })
                        .Where(child => child is not null)
                        .Select(child => new
                        {
                            type = child!.Type,
                            layer = child.Layer,
                            geometry = child.Geometry
                        })
                        .ToArray();
                }
                finally
                {
                    blockStack.Remove(block.BlockTableRecord);
                }
                break;
            case Hatch hatch:
                geometry["loops"] = CreateHatchBoundaryLoops(hatch, transform, entity.Handle.ToString());
                break;
            case Spline spline:
                geometry["sampled_points"] = Enumerable.Range(0, 65)
                    .Select(index =>
                    {
                        var parameter = spline.StartParam
                            + (spline.EndParam - spline.StartParam) * index / 64.0;
                        var point = spline.GetPointAtParameter(parameter).TransformBy(transform);
                        return new { x = point.X, y = point.Y };
                    })
                    .ToArray();
                break;
            default:
                throw new InvalidDataException(
                    $"Entity '{entity.Handle}' has unsupported visible type '{entity.GetType().Name}'.");
        }

        return geometry;
    }

    private static byte[] SerializeEntityMap(
        IReadOnlyList<VisualEvidenceEntityRecord> entities)
    {
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream))
        {
            writer.WriteStartArray();
            foreach (var entity in entities)
            {
                writer.WriteStartObject();
                writer.WriteString("stable_id", entity.StableId);
                writer.WriteString("handle", entity.Handle);
                writer.WriteString("type", entity.Type);
                writer.WriteString("layer", entity.Layer);
                writer.WritePropertyName("geometry");
                WriteCompactJson(entity.Geometry, writer);
                writer.WriteEndObject();
            }

            writer.WriteEndArray();
        }

        return stream.ToArray();
    }

    private static void WriteCompactJson(
        IReadOnlyDictionary<string, JsonElement> geometry,
        Utf8JsonWriter writer)
    {
        writer.WriteStartObject();
        foreach (var property in geometry.OrderBy(item => item.Key, StringComparer.Ordinal))
        {
            if (property.Key == "bounding_box")
            {
                continue;
            }

            writer.WritePropertyName(property.Key);
            WriteCompactJson(property.Value, writer);
        }

        writer.WriteEndObject();
    }

    private static void WriteCompactJson(JsonElement value, Utf8JsonWriter writer)
    {
        switch (value.ValueKind)
        {
            case JsonValueKind.Object:
                writer.WriteStartObject();
                foreach (var property in value.EnumerateObject())
                {
                    writer.WritePropertyName(property.Name);
                    if (property.Name == "sampled_points"
                        && property.Value.ValueKind == JsonValueKind.Array)
                    {
                        WriteCompactSampledPoints(property.Value, writer);
                    }
                    else
                    {
                        WriteCompactJson(property.Value, writer);
                    }
                }

                writer.WriteEndObject();
                break;
            case JsonValueKind.Array:
                writer.WriteStartArray();
                foreach (var item in value.EnumerateArray())
                {
                    WriteCompactJson(item, writer);
                }

                writer.WriteEndArray();
                break;
            case JsonValueKind.Number:
                if (value.TryGetDouble(out var number))
                {
                    var rounded = Math.Round(number, 1, MidpointRounding.ToEven);
                    writer.WriteNumberValue(rounded == 0 ? 0 : rounded);
                }
                else
                {
                    writer.WriteRawValue(value.GetRawText(), skipInputValidation: true);
                }

                break;
            case JsonValueKind.String:
                writer.WriteStringValue(value.GetString());
                break;
            case JsonValueKind.True:
                writer.WriteBooleanValue(true);
                break;
            case JsonValueKind.False:
                writer.WriteBooleanValue(false);
                break;
            case JsonValueKind.Null:
                writer.WriteNullValue();
                break;
            default:
                throw new JsonException($"Unsupported JSON value kind {value.ValueKind}.");
        }
    }

    private static void WriteCompactSampledPoints(
        JsonElement value,
        Utf8JsonWriter writer)
    {
        var points = value.EnumerateArray().ToArray();
        if (points.Length <= MaxSerializedSampledPoints)
        {
            WriteCompactJson(value, writer);
            return;
        }

        writer.WriteStartArray();
        foreach (var index in Enumerable.Range(0, MaxSerializedSampledPoints)
                     .Select(item => (int)Math.Round(
                         item * (points.Length - 1) / (double)(MaxSerializedSampledPoints - 1)))
                     .Distinct())
        {
            WriteCompactJson(points[index], writer);
        }

        writer.WriteEndArray();
    }

    private static object[] CreateHatchBoundaryLoops(
        Hatch hatch,
        Matrix3d transform,
        string handle)
    {
        var loops = new List<object>();
        var reversesOrientation = HasReversedOrientation(transform);
        for (var loopIndex = 0; loopIndex < hatch.NumberOfLoops; loopIndex++)
        {
            var loop = hatch.GetLoopAt(loopIndex);
            var closed = (hatch.LoopTypeAt(loopIndex) & HatchLoopTypes.NotClosed) == 0;
            if (loop.IsPolyline && loop.Polyline is { Count: >= 2 } polyline)
            {
                loops.Add(new
                {
                    closed,
                    vertices = polyline
                        .Cast<BulgeVertex>()
                        .Select(vertex =>
                        {
                            var point = new Point3d(
                                vertex.Vertex.X,
                                vertex.Vertex.Y,
                                0).TransformBy(transform);
                            return new
                            {
                                x = point.X,
                                y = point.Y,
                                bulge = reversesOrientation ? -vertex.Bulge : vertex.Bulge
                            };
                        })
                        .ToArray()
                });
                continue;
            }

            var curves = loop.Curves.Cast<Curve2d>().ToArray();
            if (curves.Length == 0)
            {
                throw new InvalidDataException(
                    $"Hatch '{handle}' loop {loopIndex} has no deterministic curve boundary.");
            }

            var vertices = new List<object>();
            foreach (var curve in curves)
            {
                var samples = curve.GetSamplePoints(32);
                if (samples is null || samples.Length < 2)
                {
                    throw new InvalidDataException(
                        $"Hatch '{handle}' loop {loopIndex} curve '{curve.GetType().Name}' has too few deterministic samples.");
                }

                foreach (var sample in samples)
                {
                    var point = new Point3d(sample.X, sample.Y, 0).TransformBy(transform);
                    vertices.Add(new
                    {
                        x = point.X,
                        y = point.Y,
                        bulge = 0.0
                    });
                }
            }

            if (vertices.Count < 2)
            {
                throw new InvalidDataException(
                    $"Hatch '{handle}' loop {loopIndex} has too few deterministic curve samples.");
            }

            loops.Add(new { closed, vertices = vertices.ToArray() });
        }

        if (loops.Count == 0)
        {
            throw new InvalidDataException(
                $"Hatch '{handle}' has no deterministic boundary loops.");
        }

        return loops.ToArray();
    }

    private static object ToPointObject(Point3d point) => new { x = point.X, y = point.Y };

    private static bool HasRenderableChildren(Dictionary<string, object?> geometry)
    {
        return geometry.TryGetValue("children", out var children)
            && children is Array array
            && array.Length > 0;
    }

    internal static bool IsConformalBasisForTesting(
        double xLength,
        double yLength,
        double dotProduct,
        double orientation = 1.0)
    {
        if (xLength < 1e-12 || yLength < 1e-12)
        {
            return false;
        }

        var scale = Math.Max(1.0, Math.Max(xLength, yLength));
        return Math.Abs(xLength - yLength) <= 1e-9 * scale
            && Math.Abs(dotProduct) <= 1e-9 * scale * scale
            && Math.Abs(orientation) > 1e-9 * scale * scale;
    }

    private static bool IsConformalTransform(Matrix3d transform)
    {
        var basis = transform.CoordinateSystem3d;
        return IsConformalBasisForTesting(
            basis.Xaxis.Length,
            basis.Yaxis.Length,
            basis.Xaxis.DotProduct(basis.Yaxis),
            basis.Xaxis.CrossProduct(basis.Yaxis).DotProduct(Vector3d.ZAxis));
    }

    private static bool HasReversedOrientation(Matrix3d transform)
    {
        var basis = transform.CoordinateSystem3d;
        return basis.Xaxis.CrossProduct(basis.Yaxis).DotProduct(Vector3d.ZAxis) < 0;
    }

    private static string EffectiveLayer(
        string layer,
        string? insertionLayer,
        string? parentEffectiveLayer)
    {
        var normalizedInsertionLayer = insertionLayer?.Trim() ?? string.Empty;
        if (normalizedInsertionLayer.Length == 0)
        {
            throw new InvalidDataException("A visible block reference has an empty layer name.");
        }

        var effectiveInsertionLayer = EffectiveLayer(
            normalizedInsertionLayer,
            parentEffectiveLayer);
        return EffectiveLayer(layer, effectiveInsertionLayer);
    }

    private static string EffectiveLayer(string layer, string? parentEffectiveLayer)
    {
        var normalizedLayer = layer?.Trim() ?? string.Empty;
        if (normalizedLayer.Length == 0)
        {
            throw new InvalidDataException("A visible entity has an empty layer name.");
        }

        return string.Equals(normalizedLayer, "0", StringComparison.OrdinalIgnoreCase)
            && !string.IsNullOrWhiteSpace(parentEffectiveLayer)
            ? parentEffectiveLayer!
            : normalizedLayer;
    }

    internal static string EffectiveLayerForTesting(string layer, string? parentEffectiveLayer) =>
        EffectiveLayer(layer, parentEffectiveLayer);

    internal static bool LayerPolicyAllowsForTesting(
        string layer,
        bool isOff,
        bool isFrozen,
        IEnumerable<string> includeLayers,
        IEnumerable<string> excludeLayers)
    {
        var states = new Dictionary<string, SessionLayerSnapshot>(StringComparer.OrdinalIgnoreCase)
        {
            [layer] = new SessionLayerSnapshot(isOff, isFrozen)
        };
        return new RenderLayerPolicy(
            includeLayers.ToHashSet(StringComparer.OrdinalIgnoreCase),
            excludeLayers.ToHashSet(StringComparer.OrdinalIgnoreCase),
            states).Allows(layer);
    }

    internal static bool LayerPolicyAllowsForTesting(
        string layer,
        IReadOnlyDictionary<string, SessionLayerSnapshot> layerStates) =>
        new RenderLayerPolicy(
            new HashSet<string>(StringComparer.OrdinalIgnoreCase),
            new HashSet<string>(StringComparer.OrdinalIgnoreCase),
            layerStates).Allows(layer);

    private static double TransformRadius(double radius, Matrix3d transform)
    {
        var vector = new Vector3d(radius, 0, 0).TransformBy(transform);
        return vector.Length;
    }

    private static double TransformAngle(double angle, Matrix3d transform)
    {
        var vector = new Vector3d(Math.Cos(angle), Math.Sin(angle), 0).TransformBy(transform);
        return Math.Atan2(vector.Y, vector.X);
    }

    private static IReadOnlyList<object> EvaluateMeasurements(
        IReadOnlyList<JsonElement> requests,
        IReadOnlyList<JsonElement> datumBindingValues,
        IReadOnlyList<VisualEvidenceEntityRecord> entities)
    {
        var byId = entities.ToDictionary(entity => entity.StableId, StringComparer.Ordinal);
        var byHandle = entities.ToDictionary(entity => entity.Handle, StringComparer.OrdinalIgnoreCase);
        var datumBindings = datumBindingValues.ToDictionary(
            binding => binding.GetProperty("id").GetString()!,
            StringComparer.Ordinal);
        return requests.Select(request =>
        {
            var projection = VisualEvidenceProjection.ProjectMeasurements(new[] { request })[0];
            var first = ResolveReference(projection.Reference, datumBindings, byId, byHandle);
            var value = projection.Kind switch
            {
                "RADIUS" => ReadRadius(first),
                "DIAMETER" => ReadRadius(first) * 2,
                "BOUNDING_BOX" => ReadBoundingBox(first),
                "DISTANCE" => ResolveDistance(projection, first, datumBindings, byId, byHandle),
                "ANGLE" => ResolveAngle(projection, first, datumBindings, byId, byHandle),
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
        IReadOnlyDictionary<string, JsonElement> datumBindings,
        IReadOnlyDictionary<string, VisualEvidenceEntityRecord> byId,
        IReadOnlyDictionary<string, VisualEvidenceEntityRecord> byHandle)
    {
        var type = reference.GetProperty("type").GetString();
        var id = reference.GetProperty("id").GetString()!;
        if (string.Equals(type, "DATUM", StringComparison.Ordinal))
        {
            if (!datumBindings.TryGetValue(id, out var binding))
            {
                throw new InvalidDataException($"The measurement datum reference '{id}' is not provenance-bound.");
            }

            id = binding.GetProperty("entity_handle").GetString()!;
        }
        else if (!string.Equals(type, "ENTITY", StringComparison.Ordinal))
        {
            throw new InvalidDataException($"The measurement reference '{id}' has an unsupported type.");
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
        IReadOnlyDictionary<string, JsonElement> datumBindings,
        IReadOnlyDictionary<string, VisualEvidenceEntityRecord> byId,
        IReadOnlyDictionary<string, VisualEvidenceEntityRecord> byHandle)
    {
        if (measurement.ToReference is not JsonElement toReference)
        {
            throw new InvalidDataException($"Distance measurement '{measurement.Id}' has no to_reference.");
        }

        var second = ResolveReference(toReference, datumBindings, byId, byHandle);
        var firstPoint = RepresentativePoint(first);
        var secondPoint = RepresentativePoint(second);
        return Math.Sqrt(Math.Pow(firstPoint.X - secondPoint.X, 2) + Math.Pow(firstPoint.Y - secondPoint.Y, 2));
    }

    private static double ResolveAngle(
        VisualEvidenceMeasurementRecord measurement,
        VisualEvidenceEntityRecord first,
        IReadOnlyDictionary<string, JsonElement> datumBindings,
        IReadOnlyDictionary<string, VisualEvidenceEntityRecord> byId,
        IReadOnlyDictionary<string, VisualEvidenceEntityRecord> byHandle)
    {
        if (measurement.ToReference is not JsonElement toReference)
        {
            throw new InvalidDataException($"Angle measurement '{measurement.Id}' has no to_reference.");
        }

        var second = ResolveReference(toReference, datumBindings, byId, byHandle);
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

    internal static byte[] RenderRegion(
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

        if ((entity.Type == "POLYLINE"
                || entity.Type == "LEADER"
                || entity.Type == "SOLID"
                || entity.Type == "WIPEOUT"
                || entity.Type == "VIEWPORT")
            && entity.Geometry.TryGetValue("vertices", out var vertices)
            && vertices.ValueKind == JsonValueKind.Array)
        {
            var values = vertices.EnumerateArray().ToArray();
            if (values.Length >= 2)
            {
                var closed = entity.Geometry.TryGetValue("closed", out var closedValue)
                    && closedValue.ValueKind == JsonValueKind.True;
                var segmentCount = closed ? values.Length : values.Length - 1;
                for (var index = 0; index < segmentCount; index++)
                {
                    var first = values[index];
                    var second = values[(index + 1) % values.Length];
                    var start = Transform(first.GetProperty("x").GetDouble(), first.GetProperty("y").GetDouble());
                    var end = Transform(second.GetProperty("x").GetDouble(), second.GetProperty("y").GetDouble());
                    var bulge = first.TryGetProperty("bulge", out var bulgeValue)
                        ? bulgeValue.GetDouble()
                        : 0.0;
                    DrawBulgeSegment(graphics, pen, start, end, bulge);
                }
            }

            return;
        }

        if (entity.Type == "HATCH"
            && entity.Geometry.TryGetValue("loops", out var loops)
            && loops.ValueKind == JsonValueKind.Array)
        {
            var loopIndex = 0;
            foreach (var loop in loops.EnumerateArray())
            {
                if (loop.ValueKind != JsonValueKind.Object
                    || !loop.TryGetProperty("vertices", out var loopVertices)
                    || loopVertices.ValueKind != JsonValueKind.Array)
                {
                    throw new InvalidDataException(
                        $"Hatch '{entity.StableId}' loop {loopIndex} has an invalid boundary projection.");
                }

                var values = loopVertices.EnumerateArray().ToArray();
                if (values.Length < 2)
                {
                    throw new InvalidDataException(
                        $"Hatch '{entity.StableId}' loop {loopIndex} has too few boundary vertices.");
                }

                var closed = loop.TryGetProperty("closed", out var closedValue)
                    && closedValue.ValueKind == JsonValueKind.True;
                var segmentCount = closed ? values.Length : values.Length - 1;
                for (var index = 0; index < segmentCount; index++)
                {
                    var first = values[index];
                    var second = values[(index + 1) % values.Length];
                    var start = Transform(first.GetProperty("x").GetDouble(), first.GetProperty("y").GetDouble());
                    var end = Transform(second.GetProperty("x").GetDouble(), second.GetProperty("y").GetDouble());
                    var bulge = first.TryGetProperty("bulge", out var bulgeValue)
                        ? bulgeValue.GetDouble()
                        : 0.0;
                    DrawBulgeSegment(graphics, pen, start, end, bulge);
                }

                loopIndex++;
            }

            return;
        }

        if ((entity.Type == "SPLINE" || entity.Type == "ELLIPSE")
            && entity.Geometry.TryGetValue("sampled_points", out var sampledPoints)
            && sampledPoints.ValueKind == JsonValueKind.Array)
        {
            var points = sampledPoints.EnumerateArray()
                .Select(point => Transform(point.GetProperty("x").GetDouble(), point.GetProperty("y").GetDouble()))
                .ToArray();
            if (points.Length < 2)
            {
                throw new InvalidDataException($"Spline '{entity.StableId}' has too few sampled points.");
            }

            graphics.DrawLines(pen, points);
            if (entity.Type == "ELLIPSE"
                && entity.Geometry.TryGetValue("closed", out var closedValue)
                && closedValue.ValueKind == JsonValueKind.True
                && points[0] != points[^1])
            {
                graphics.DrawLine(pen, points[^1], points[0]);
            }

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
                    (float)-RadiansToDegrees(startAngle.GetDouble()),
                    (float)-RadiansToDegrees(endAngle.GetDouble() - startAngle.GetDouble()));
            }
            else
            {
                graphics.DrawEllipse(pen, center.X - radiusPixelsX, center.Y - radiusPixelsY, radiusPixelsX * 2, radiusPixelsY * 2);
            }

            return;
        }

        if (entity.Geometry.TryGetValue("text", out var text)
            && text.ValueKind == JsonValueKind.String)
        {
            var positionPrefix = entity.Type == ReviewEntityTypes.Dimension ? "text_position" : "position";
            if (entity.Geometry.TryGetValue($"{positionPrefix}_x", out var textX)
                && entity.Geometry.TryGetValue($"{positionPrefix}_y", out var textY))
            {
                var point = Transform(textX.GetDouble(), textY.GetDouble());
                var modelHeight = entity.Geometry.TryGetValue("height", out var heightValue)
                    && heightValue.ValueKind == JsonValueKind.Number
                    ? heightValue.GetDouble()
                    : 20.0;
                var pixelHeight = Math.Max(6.0, modelHeight / (bbox[3] - bbox[1]) * height);
                using var font = new System.Drawing.Font(FontFamily.GenericSansSerif, (float)pixelHeight, FontStyle.Regular, GraphicsUnit.Pixel);
                using var brush = new SolidBrush(pen.Color);
                var state = graphics.Save();
                graphics.TranslateTransform(point.X, point.Y);
                var rotation = entity.Geometry.TryGetValue("rotation", out var rotationValue)
                    && rotationValue.ValueKind == JsonValueKind.Number
                    ? (float)-RadiansToDegrees(rotationValue.GetDouble())
                    : 0.0f;
                graphics.RotateTransform(rotation);
                graphics.DrawString(text.GetString(), font, brush, 0, 0);
                graphics.Restore(state);
                if (entity.Type != ReviewEntityTypes.Text && entity.Type != "MTEXT")
                {
                    DrawDimensionGeometry(graphics, pen, entity, Transform);
                }

                return;
            }
        }

        if (entity.Geometry.TryGetValue("children", out var children)
            && children.ValueKind == JsonValueKind.Array)
        {
            var index = 0;
            foreach (var child in children.EnumerateArray())
            {
                if (child.ValueKind != JsonValueKind.Object
                    || !child.TryGetProperty("type", out var childType)
                    || childType.ValueKind != JsonValueKind.String
                    || !child.TryGetProperty("layer", out var childLayer)
                    || childLayer.ValueKind != JsonValueKind.String
                    || !child.TryGetProperty("geometry", out var childGeometry)
                    || childGeometry.ValueKind != JsonValueKind.Object)
                {
                    throw new InvalidDataException($"Entity '{entity.StableId}' has an invalid block child render projection.");
                }

                var childMap = childGeometry.EnumerateObject()
                    .ToDictionary(property => property.Name, property => property.Value.Clone(), StringComparer.Ordinal);
                DrawEntity(
                    graphics,
                    pen,
                    new VisualEvidenceEntityRecord(
                        $"{entity.StableId}:CHILD:{index++}",
                        entity.Handle,
                        childType.GetString()!,
                        childLayer.GetString()!,
                        childMap),
                    bbox,
                    width,
                    height);
            }

            return;
        }

        throw new InvalidDataException($"Entity '{entity.StableId}' has no deterministic render projection.");
    }

    private static void DrawBulgeSegment(
        Graphics graphics,
        Pen pen,
        PointF start,
        PointF end,
        double bulge)
    {
        if (Math.Abs(bulge) < 1e-9)
        {
            graphics.DrawLine(pen, start, end);
            return;
        }

        var dx = end.X - start.X;
        var dy = end.Y - start.Y;
        var chord = Math.Sqrt(dx * dx + dy * dy);
        if (chord < 1e-6)
        {
            return;
        }

        var sweep = 4.0 * Math.Atan(bulge);
        var radius = chord / (2.0 * Math.Sin(Math.Abs(sweep) / 2.0));
        var midpoint = new PointF((start.X + end.X) / 2.0f, (start.Y + end.Y) / 2.0f);
        var normalX = -dy / chord;
        var normalY = dx / chord;
        var offset = Math.Sqrt(Math.Max(0.0, radius * radius - (chord / 2.0) * (chord / 2.0)));
        var center = new PointF(
            (float)(midpoint.X + Math.Sign(bulge) * normalX * offset),
            (float)(midpoint.Y + Math.Sign(bulge) * normalY * offset));
        var startAngle = Math.Atan2(start.Y - center.Y, start.X - center.X) * 180.0 / Math.PI;
        var sweepAngle = sweep * 180.0 / Math.PI;
        var diameter = (float)(radius * 2.0);
        graphics.DrawArc(
            pen,
            center.X - (float)radius,
            center.Y - (float)radius,
            diameter,
            diameter,
            (float)startAngle,
            (float)sweepAngle);
    }

    private static void DrawDimensionGeometry(
        Graphics graphics,
        Pen pen,
        VisualEvidenceEntityRecord entity,
        Func<double, double, PointF> transform)
    {
        if (entity.Geometry.TryGetValue("dimension_kind", out var dimensionKind)
            && dimensionKind.ValueKind == JsonValueKind.String
            && string.Equals(dimensionKind.GetString(), "LINE_ANGULAR", StringComparison.Ordinal))
        {
            DrawLineAngularDimensionGeometry(graphics, pen, entity, transform);
            return;
        }

        if (!entity.Geometry.TryGetValue("xline1_x", out var xline1X)
            || !entity.Geometry.TryGetValue("xline1_y", out var xline1Y)
            || !entity.Geometry.TryGetValue("xline2_x", out var xline2X)
            || !entity.Geometry.TryGetValue("xline2_y", out var xline2Y)
            || !entity.Geometry.TryGetValue("dimline_x", out var dimlineX)
            || !entity.Geometry.TryGetValue("dimline_y", out var dimlineY))
        {
            throw new InvalidDataException($"Dimension '{entity.StableId}' has no deterministic dimension-line projection.");
        }

        var first = transform(xline1X.GetDouble(), xline1Y.GetDouble());
        var second = transform(xline2X.GetDouble(), xline2Y.GetDouble());
        var dimensionPoint = transform(dimlineX.GetDouble(), dimlineY.GetDouble());
        var offset = new PointF(dimensionPoint.X - ((first.X + second.X) / 2.0f), dimensionPoint.Y - ((first.Y + second.Y) / 2.0f));
        var dimensionFirst = new PointF(first.X + offset.X, first.Y + offset.Y);
        var dimensionSecond = new PointF(second.X + offset.X, second.Y + offset.Y);
        graphics.DrawLine(pen, first, dimensionFirst);
        graphics.DrawLine(pen, second, dimensionSecond);
        graphics.DrawLine(pen, dimensionFirst, dimensionSecond);
        DrawArrow(graphics, pen, dimensionFirst, dimensionSecond);
        DrawArrow(graphics, pen, dimensionSecond, dimensionFirst);
    }

    private static void DrawLineAngularDimensionGeometry(
        Graphics graphics,
        Pen pen,
        VisualEvidenceEntityRecord entity,
        Func<double, double, PointF> transform)
    {
        var firstStart = ReadPoint(entity, "xline1_start", transform);
        var firstEnd = ReadPoint(entity, "xline1_end", transform);
        var secondStart = ReadPoint(entity, "xline2_start", transform);
        var secondEnd = ReadPoint(entity, "xline2_end", transform);
        var arcPoint = ReadPoint(entity, "arc_point", transform);
        if (!TryIntersectLines(firstStart, firstEnd, secondStart, secondEnd, out var center))
        {
            throw new InvalidDataException(
                $"Dimension '{entity.StableId}' has parallel angular extension lines.");
        }

        graphics.DrawLine(pen, firstStart, firstEnd);
        graphics.DrawLine(pen, secondStart, secondEnd);

        var radius = Distance(center, arcPoint);
        if (radius < 1e-6)
        {
            throw new InvalidDataException(
                $"Dimension '{entity.StableId}' has an angular arc point at its vertex.");
        }

        var firstAngle = Math.Atan2(firstEnd.Y - center.Y, firstEnd.X - center.X);
        var secondAngle = Math.Atan2(secondEnd.Y - center.Y, secondEnd.X - center.X);
        var arcAngle = Math.Atan2(arcPoint.Y - center.Y, arcPoint.X - center.X);
        var positiveSweep = NormalizePositiveAngle(secondAngle - firstAngle);
        var sweep = IsAngleOnSweep(firstAngle, positiveSweep, arcAngle)
            ? positiveSweep
            : positiveSweep - (2.0 * Math.PI);
        var points = Enumerable.Range(0, 33)
            .Select(index =>
            {
                var angle = firstAngle + sweep * index / 32.0;
                return new PointF(
                    center.X + (float)(Math.Cos(angle) * radius),
                    center.Y + (float)(Math.Sin(angle) * radius));
            })
            .ToArray();
        graphics.DrawLines(pen, points);
        DrawArrow(graphics, pen, points[0], points[1]);
        DrawArrow(graphics, pen, points[^1], points[^2]);
    }

    private static PointF ReadPoint(
        VisualEvidenceEntityRecord entity,
        string prefix,
        Func<double, double, PointF> transform)
    {
        if (!entity.Geometry.TryGetValue($"{prefix}_x", out var x)
            || !entity.Geometry.TryGetValue($"{prefix}_y", out var y))
        {
            throw new InvalidDataException(
                $"Dimension '{entity.StableId}' is missing angular point '{prefix}'.");
        }

        return transform(x.GetDouble(), y.GetDouble());
    }

    private static bool TryIntersectLines(
        PointF firstStart,
        PointF firstEnd,
        PointF secondStart,
        PointF secondEnd,
        out PointF intersection)
    {
        var firstDx = firstEnd.X - firstStart.X;
        var firstDy = firstEnd.Y - firstStart.Y;
        var secondDx = secondEnd.X - secondStart.X;
        var secondDy = secondEnd.Y - secondStart.Y;
        var determinant = firstDx * secondDy - firstDy * secondDx;
        if (Math.Abs(determinant) < 1e-6)
        {
            intersection = default;
            return false;
        }

        var offsetX = secondStart.X - firstStart.X;
        var offsetY = secondStart.Y - firstStart.Y;
        var firstParameter = (offsetX * secondDy - offsetY * secondDx) / determinant;
        intersection = new PointF(
            firstStart.X + firstParameter * firstDx,
            firstStart.Y + firstParameter * firstDy);
        return true;
    }

    private static double Distance(PointF first, PointF second)
    {
        var dx = second.X - first.X;
        var dy = second.Y - first.Y;
        return Math.Sqrt(dx * dx + dy * dy);
    }

    private static double NormalizePositiveAngle(double angle)
    {
        var fullTurn = 2.0 * Math.PI;
        var normalized = angle % fullTurn;
        return normalized < 0 ? normalized + fullTurn : normalized;
    }

    private static bool IsAngleOnSweep(double start, double sweep, double candidate)
    {
        return NormalizePositiveAngle(candidate - start) <= sweep + 1e-9;
    }

    private static void DrawArrow(Graphics graphics, Pen pen, PointF tip, PointF tail)
    {
        var dx = tail.X - tip.X;
        var dy = tail.Y - tip.Y;
        var length = Math.Sqrt(dx * dx + dy * dy);
        if (length < 1e-6)
        {
            return;
        }

        var ux = dx / length;
        var uy = dy / length;
        var px = -uy;
        var py = ux;
        const double size = 7.0;
        var left = new PointF((float)(tip.X + ux * size + px * size * 0.45), (float)(tip.Y + uy * size + py * size * 0.45));
        var right = new PointF((float)(tip.X + ux * size - px * size * 0.45), (float)(tip.Y + uy * size - py * size * 0.45));
        graphics.DrawLine(pen, tip, left);
        graphics.DrawLine(pen, tip, right);
    }

    private static double RadiansToDegrees(double radians) => radians * 180 / Math.PI;

    private static SessionStateSnapshot CaptureSessionState(Document document)
    {
        var database = document.Database;
        var layerStates = new Dictionary<string, SessionLayerSnapshot>(StringComparer.OrdinalIgnoreCase);
        using (var transaction = database.TransactionManager.StartOpenCloseTransaction())
        {
            var layerTable = (LayerTable)transaction.GetObject(database.LayerTableId, OpenMode.ForRead);
            foreach (ObjectId layerId in layerTable)
            {
                var layer = (LayerTableRecord)transaction.GetObject(layerId, OpenMode.ForRead);
                layerStates[layer.Name] = new SessionLayerSnapshot(layer.IsOff, layer.IsFrozen);
            }
        }

        var variables = RendererSystemVariableNames.ToDictionary(
            name => name,
            name => JsonSerializer.SerializeToElement(AcadApplication.GetSystemVariable(name)),
            StringComparer.Ordinal);
        var selectionHandles = new List<string>();
        var impliedSelection = document.Editor.SelectImplied();
        if (impliedSelection.Status == PromptStatus.OK && impliedSelection.Value is not null)
        {
            selectionHandles.AddRange(
                impliedSelection.Value.GetObjectIds()
                    .Select(objectId => objectId.Handle.ToString().ToUpperInvariant()));
        }
        var currentLayer = Convert.ToString(
            AcadApplication.GetSystemVariable("CLAYER"),
            CultureInfo.InvariantCulture) ?? string.Empty;
        var currentLayout = LayoutManager.Current.CurrentLayout;
        var space = CaptureSessionSpace();
        using var currentView = document.Editor.GetCurrentView();
        var viewState = new SessionViewSnapshot(
            currentView.CenterPoint.X,
            currentView.CenterPoint.Y,
            currentView.Width,
            currentView.Height,
            currentView.Target.X,
            currentView.Target.Y,
            currentView.Target.Z,
            currentView.ViewDirection.X,
            currentView.ViewDirection.Y,
            currentView.ViewDirection.Z,
            currentView.ViewTwist,
            currentView.LensLength);
        var viewProperties = JsonSerializer.Serialize(viewState);
        return SessionStateSnapshot.Create(
            database.Filename,
            $"DOCUMENT:{RuntimeHelpers.GetHashCode(document):X8}",
            currentLayout,
            space,
            currentLayer,
            viewProperties,
            selectionHandles,
            layerStates,
            variables,
            viewState);
    }

    private static void RestoreSessionState(Document document, SessionStateSnapshot snapshot)
    {
        ArgumentNullException.ThrowIfNull(document);
        ArgumentNullException.ThrowIfNull(snapshot);

        if (!string.Equals(
                LayoutManager.Current.CurrentLayout,
                snapshot.CurrentLayout,
                StringComparison.OrdinalIgnoreCase))
        {
            LayoutManager.Current.CurrentLayout = snapshot.CurrentLayout;
        }

        var currentSpace = CaptureSessionSpace();
        if (!currentSpace.Equals(snapshot.Space)
            && snapshot.Space.Kind == "MODEL_SPACE"
            && currentSpace.Kind != "MODEL_SPACE")
        {
            document.Editor.SwitchToModelSpace();
        }
        else if (!currentSpace.Equals(snapshot.Space)
            && snapshot.Space.Kind != "MODEL_SPACE"
            && currentSpace.Kind == "MODEL_SPACE")
        {
            document.Editor.SwitchToPaperSpace();
        }

        foreach (var variable in snapshot.RendererSystemVariables)
        {
            if (variable.Key is not "ANNOALLVISIBLE")
            {
                continue;
            }

            AcadApplication.SetSystemVariable(variable.Key, ToSystemVariableValue(variable.Value));
        }

        AcadApplication.SetSystemVariable("CLAYER", snapshot.CurrentLayer);
        var restoredSpace = CaptureSessionSpace();
        if (snapshot.Space.Kind == "PAPER_SPACE_FLOATING_VIEWPORT"
            && restoredSpace.Cvport != snapshot.Space.Cvport)
        {
            AcadApplication.SetSystemVariable("CVPORT", snapshot.Space.Cvport);
        }

        if (snapshot.Space.Kind == "PAPER_SPACE" && restoredSpace.Cvport != 1)
        {
            AcadApplication.SetSystemVariable("CVPORT", 1);
        }

        var ids = snapshot.SelectionHandles
            .Select(handle => document.Database.GetObjectId(false, new Handle(Convert.ToInt64(handle, 16)), 0))
            .Where(id => !id.IsNull)
            .ToArray();
        document.Editor.SetImpliedSelection(ids);

        if (snapshot.CurrentView is not null)
        {
            using var view = document.Editor.GetCurrentView();
            view.CenterPoint = new Point2d(snapshot.CurrentView.CenterX, snapshot.CurrentView.CenterY);
            view.Width = snapshot.CurrentView.Width;
            view.Height = snapshot.CurrentView.Height;
            view.Target = new Point3d(
                snapshot.CurrentView.TargetX,
                snapshot.CurrentView.TargetY,
                snapshot.CurrentView.TargetZ);
            view.ViewDirection = new Vector3d(
                snapshot.CurrentView.DirectionX,
                snapshot.CurrentView.DirectionY,
                snapshot.CurrentView.DirectionZ);
            view.ViewTwist = snapshot.CurrentView.Twist;
            view.LensLength = snapshot.CurrentView.LensLength;
            document.Editor.SetCurrentView(view);
        }
    }

    private static SessionSpaceSnapshot CaptureSessionSpace()
    {
        var currentLayout = LayoutManager.Current.CurrentLayout;
        var tileMode = Convert.ToInt32(AcadApplication.GetSystemVariable("TILEMODE"), CultureInfo.InvariantCulture);
        var cvport = Convert.ToInt32(AcadApplication.GetSystemVariable("CVPORT"), CultureInfo.InvariantCulture);
        var spaceKind = tileMode != 0
            ? "MODEL_SPACE"
            : cvport > 1
                ? "PAPER_SPACE_FLOATING_VIEWPORT"
                : "PAPER_SPACE";
        return new SessionSpaceSnapshot(currentLayout, tileMode, cvport, spaceKind);
    }

    private static long ReadDbMod() => Convert.ToInt64(
        AcadApplication.GetSystemVariable("DBMOD"),
        CultureInfo.InvariantCulture);

    private static object ToSystemVariableValue(JsonElement value)
    {
        return value.ValueKind switch
        {
            JsonValueKind.String => value.GetString() ?? string.Empty,
            JsonValueKind.Number when value.TryGetInt32(out var integer) => integer,
            JsonValueKind.Number when value.TryGetDouble(out var number) => number,
            JsonValueKind.True => true,
            JsonValueKind.False => false,
            _ => throw new InvalidDataException("Unsupported system-variable value type in the session snapshot.")
        };
    }

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
        IDictionary<string, object?> geometry,
        string prefix,
        Point3d point)
    {
        geometry[$"{prefix}_x"] = point.X;
        geometry[$"{prefix}_y"] = point.Y;
    }
}
