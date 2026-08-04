using System.Text.Json;
using CadAgent.AutoCAD2027.Drawing;
using CadAgent.AutoCAD2027.Review;
using Xunit;

namespace CadAgent.AutoCAD2027.Tests.Drawing;

public sealed class VisualEvidenceProjectionTests
{
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
}
