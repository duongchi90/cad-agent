using System.Text.Json;
using System.Drawing;
using CadAgent.AutoCAD2027.Drawing;
using CadAgent.AutoCAD2027.Review;
using Xunit;

namespace CadAgent.AutoCAD2027.Tests.Drawing;

public sealed class VisualEvidenceProjectionTests
{
    [Fact]
    public void NonConformalBlockBasisIsRejected()
    {
        Assert.True(AutoCadVisualEvidenceReader.IsConformalBasisForTesting(
            2,
            2,
            0));
        Assert.False(AutoCadVisualEvidenceReader.IsConformalBasisForTesting(
            2,
            3,
            0));
        Assert.False(AutoCadVisualEvidenceReader.IsConformalBasisForTesting(
            1,
            Math.Sqrt(2),
            1));
    }

    [Fact]
    public void LayerPolicyRejectsHiddenExcludedAndNestedChildLayers()
    {
        Assert.True(AutoCadVisualEvidenceReader.LayerPolicyAllowsForTesting(
            "CABIN",
            isOff: false,
            isFrozen: false,
            new[] { "CABIN" },
            Array.Empty<string>()));
        Assert.False(AutoCadVisualEvidenceReader.LayerPolicyAllowsForTesting(
            "CABIN",
            isOff: true,
            isFrozen: false,
            new[] { "CABIN" },
            Array.Empty<string>()));
        Assert.False(AutoCadVisualEvidenceReader.LayerPolicyAllowsForTesting(
            "TEXT",
            isOff: false,
            isFrozen: false,
            Array.Empty<string>(),
            new[] { "TEXT" }));
    }

    [Fact]
    public void RegionHashIsIndependentOfJsonPropertyOrder()
    {
        var first = JsonDocument.Parse(
            "{\"pixel_size\":[1600,1200],\"background\":\"WHITE\",\"model_bbox_mm\":[0,0,2400,2200],\"include_layers\":[\"CABIN\"],\"exclude_layers\":[]}").RootElement;
        var second = JsonDocument.Parse(
            "{\"exclude_layers\":[],\"include_layers\":[\"CABIN\"],\"model_bbox_mm\":[0,0,2400,2200],\"background\":\"WHITE\",\"pixel_size\":[1600,1200]}").RootElement;

        Assert.Equal(
            VisualEvidenceProjection.CanonicalRegionConfigSha256(first),
            VisualEvidenceProjection.CanonicalRegionConfigSha256(second));
    }

    [Fact]
    public void EntityProjectionIsSortedAndCopiesGeometryAsReadOnlyMetadata()
    {
        var snapshots = new[]
        {
            new EntitySnapshot(
                "B2",
                "CIRCLE",
                "CABIN",
                new Dictionary<string, JsonElement>
                {
                    ["radius"] = JsonSerializer.SerializeToElement(25.0),
                    ["center"] = JsonSerializer.SerializeToElement(new[] { 10.0, 20.0 })
                }),
            new EntitySnapshot(
                "A1",
                "LINE",
                "0",
                new Dictionary<string, JsonElement>
                {
                    ["end"] = JsonSerializer.SerializeToElement(new[] { 2.0, 2.0 }),
                    ["start"] = JsonSerializer.SerializeToElement(new[] { 1.0, 1.0 })
                })
        };

        var projected = VisualEvidenceProjection.ProjectEntities(snapshots);

        Assert.Equal(new[] { "A1", "B2" }, projected.Select(item => item.Handle));
        Assert.Equal("ENTITY:A1", projected[0].StableId);
        Assert.Equal(new[] { "end", "start" }, projected[0].Geometry.Keys);
    }

    [Fact]
    public void MeasurementProjectionIsSortedByStableId()
    {
        var requests = new[]
        {
            JsonDocument.Parse("{\"id\":\"M2\",\"kind\":\"DISTANCE\",\"reference\":{\"type\":\"ENTITY\",\"id\":\"B2\"}}").RootElement,
            JsonDocument.Parse("{\"id\":\"M1\",\"kind\":\"DISTANCE\",\"reference\":{\"type\":\"DATUM\",\"id\":\"AXLE\"}}").RootElement
        };

        var projected = VisualEvidenceProjection.ProjectMeasurements(requests);

        Assert.Equal(new[] { "M1", "M2" }, projected.Select(item => item.Id));
        Assert.Equal("DATUM", projected[0].Reference.GetProperty("type").GetString());
    }

    [Fact]
    public void RequestOwnedArtifactsRefuseTraversalAndExistingDestinations()
    {
        var root = Path.Combine(Path.GetTempPath(), "cadagent-vs-t3", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            Assert.Throws<ArgumentException>(() =>
                RequestOwnedArtifactStore.Create(root, "REQ-001", "artifacts/../escape"));

            using var store = RequestOwnedArtifactStore.Create(root, "REQ-001", "artifacts/REQ-001");
            var descriptor = store.Write("entity-map", "entities.json", "application/json", "[]"u8.ToArray());
            Assert.Equal("application/json", descriptor.MimeType);
            Assert.Equal(2, descriptor.ByteLength);
            Assert.Equal("artifacts/REQ-001/entities.json", descriptor.RelativePath);
            Assert.True(File.Exists(Path.Combine(root, descriptor.RelativePath.Replace('/', Path.DirectorySeparatorChar))));

            Assert.Throws<IOException>(() =>
                RequestOwnedArtifactStore.Create(root, "REQ-001", "artifacts/REQ-001"));
        }
        finally
        {
            if (Directory.Exists(root))
            {
                Directory.Delete(root, recursive: true);
            }
        }
    }

    [Fact]
    public void RequestOwnedArtifactsEnforceTheTotalByteLimit()
    {
        var root = Path.Combine(Path.GetTempPath(), "cadagent-vs-t3", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            using var store = RequestOwnedArtifactStore.Create(root, "REQ-001", "artifacts/REQ-001");
            var oversized = new byte[VisualEvidenceArtifactPolicy.MaxTotalArtifactBytes + 1];

            Assert.Throws<InvalidDataException>(() =>
                store.Write("render", "cad-render.png", "image/png", oversized));
        }
        finally
        {
            if (Directory.Exists(root))
            {
                Directory.Delete(root, recursive: true);
            }
        }
    }

    [Fact]
    public void RendererCoversLinePolylineBlockTextAndDimensionRecords()
    {
        var region = JsonDocument.Parse(
            "{\"model_bbox_mm\":[0,0,100,100],\"pixel_size\":[320,320],\"background\":\"WHITE\",\"include_layers\":[],\"exclude_layers\":[]}").RootElement;
        var boundingBox = JsonSerializer.SerializeToElement(new
        {
            min_x = 10.0,
            min_y = 10.0,
            max_x = 90.0,
            max_y = 90.0
        });
        var snapshots = new[]
        {
            new EntitySnapshot(
                "1",
                "LINE",
                "0",
                new Dictionary<string, JsonElement>
                {
                    ["bounding_box"] = boundingBox,
                    ["start_x"] = JsonSerializer.SerializeToElement(10.0),
                    ["start_y"] = JsonSerializer.SerializeToElement(10.0),
                    ["end_x"] = JsonSerializer.SerializeToElement(90.0),
                    ["end_y"] = JsonSerializer.SerializeToElement(90.0)
                }),
            new EntitySnapshot(
                "2",
                "POLYLINE",
                "0",
                new Dictionary<string, JsonElement>
                {
                    ["bounding_box"] = boundingBox,
                    ["vertices"] = JsonSerializer.SerializeToElement(new[]
                    {
                        new { x = 10.0, y = 10.0, bulge = 0.0 },
                        new { x = 90.0, y = 10.0, bulge = 0.0 }
                    }),
                    ["closed"] = JsonSerializer.SerializeToElement(false)
                }),
            new EntitySnapshot(
                "3",
                "BLOCK_REFERENCE",
                "0",
                new Dictionary<string, JsonElement>
                {
                    ["bounding_box"] = boundingBox,
                    ["children"] = JsonSerializer.SerializeToElement(new[]
                    {
                        new
                        {
                            type = "LINE",
                            layer = "0",
                            geometry = new
                            {
                                start_x = 40.0,
                                start_y = 40.0,
                                end_x = 70.0,
                                end_y = 70.0
                            }
                        }
                    })
                }),
            new EntitySnapshot(
                "4",
                "TEXT",
                "0",
                new Dictionary<string, JsonElement>
                {
                    ["bounding_box"] = boundingBox,
                    ["position_x"] = JsonSerializer.SerializeToElement(20.0),
                    ["position_y"] = JsonSerializer.SerializeToElement(20.0),
                    ["height"] = JsonSerializer.SerializeToElement(10.0),
                    ["text"] = JsonSerializer.SerializeToElement("CABIN")
                }),
            new EntitySnapshot(
                "5",
                "DIMENSION",
                "0",
                new Dictionary<string, JsonElement>
                {
                    ["bounding_box"] = boundingBox,
                    ["text_position_x"] = JsonSerializer.SerializeToElement(20.0),
                    ["text_position_y"] = JsonSerializer.SerializeToElement(30.0),
                    ["height"] = JsonSerializer.SerializeToElement(10.0),
                    ["text"] = JsonSerializer.SerializeToElement("4500"),
                    ["xline1_x"] = JsonSerializer.SerializeToElement(20.0),
                    ["xline1_y"] = JsonSerializer.SerializeToElement(40.0),
                    ["xline2_x"] = JsonSerializer.SerializeToElement(80.0),
                    ["xline2_y"] = JsonSerializer.SerializeToElement(40.0),
                    ["dimline_x"] = JsonSerializer.SerializeToElement(50.0),
                    ["dimline_y"] = JsonSerializer.SerializeToElement(30.0)
                })
        };

        var projected = VisualEvidenceProjection.ProjectEntities(snapshots);
        var png = AutoCadVisualEvidenceReader.RenderRegion(region, projected);

        Assert.True(png.Length > 100);
    }

    [Fact]
    public void RendererPreservesPolylineBulgeAsCurvedPixels()
    {
        var region = JsonDocument.Parse(
            "{\"model_bbox_mm\":[0,0,100,100],\"pixel_size\":[400,400],\"background\":\"WHITE\",\"include_layers\":[],\"exclude_layers\":[]}").RootElement;
        var snapshots = new[]
        {
            new EntitySnapshot(
                "BULGE",
                "POLYLINE",
                "0",
                new Dictionary<string, JsonElement>
                {
                    ["vertices"] = JsonSerializer.SerializeToElement(new[]
                    {
                        new { x = 20.0, y = 50.0, bulge = 1.0 },
                        new { x = 80.0, y = 50.0, bulge = 0.0 }
                    }),
                    ["closed"] = JsonSerializer.SerializeToElement(false)
                })
        };

        var png = AutoCadVisualEvidenceReader.RenderRegion(
            region,
            VisualEvidenceProjection.ProjectEntities(snapshots));
        using var bitmap = new Bitmap(new MemoryStream(png));
        var offChordPixels = 0;
        for (var x = 120; x <= 280; x++)
        {
            for (var y = 0; y < bitmap.Height; y++)
            {
                if (Math.Abs(y - 200) > 12 && bitmap.GetPixel(x, y).R < 100)
                {
                    offChordPixels++;
                }
            }
        }

        Assert.True(offChordPixels > 10);
    }

    [Fact]
    public void RendererRejectsBoundingBoxPlaceholderForVisibleEntity()
    {
        var region = JsonDocument.Parse(
            "{\"model_bbox_mm\":[0,0,100,100],\"pixel_size\":[320,320],\"background\":\"WHITE\",\"include_layers\":[],\"exclude_layers\":[]}").RootElement;
        var boundingBox = JsonSerializer.SerializeToElement(new
        {
            min_x = 10.0,
            min_y = 10.0,
            max_x = 90.0,
            max_y = 90.0
        });
        var snapshot = new EntitySnapshot(
            "3",
            "HATCH",
            "0",
            new Dictionary<string, JsonElement>
            {
                ["bounding_box"] = boundingBox,
                ["render_fallback"] = JsonSerializer.SerializeToElement("BOUNDING_BOX")
            });

        var projected = VisualEvidenceProjection.ProjectEntities(new[] { snapshot });

        Assert.Throws<InvalidDataException>(() => AutoCadVisualEvidenceReader.RenderRegion(region, projected));
    }
}
