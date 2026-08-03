using CadAgent.AutoCAD2027.DrawingSetup;
using Xunit;

namespace CadAgent.AutoCAD2027.Tests.DrawingSetup;

public sealed class DrawingSetupPayloadTests
{
    [Fact]
    public void CreateSortsEveryCollectionAndReportsNoMutation()
    {
        var payload = DrawingSetupPayload.Create(DrawingSetupFixtures.UnsortedSnapshot());

        Assert.False(payload["changed"].GetBoolean());
        Assert.Equal(0, payload["dbmod_before"].GetInt32());
        Assert.Equal(0, payload["dbmod_after"].GetInt32());
        Assert.Equal(
            new[] { "0", "NET_CHINH" },
            payload["layers"]
                .EnumerateArray()
                .Select(item => item.GetProperty("name").GetString()));
        Assert.Equal(
            new[] { "A1-01" },
            payload["layouts"]
                .EnumerateArray()
                .Select(item => item.GetProperty("name").GetString()));
        Assert.Equal(
            new[] { "INSUNITS", "PSLTSCALE" },
            payload["variables"].EnumerateObject().Select(item => item.Name));
        Assert.Equal(
            new[] { "Standard", "TCVN" },
            payload["styles"]
                .GetProperty("text")
                .EnumerateArray()
                .Select(item => item.GetString()));
        Assert.Equal(
            new[] { 0.01, 0.02 },
            payload["layouts"]
                .EnumerateArray()
                .Single()
                .GetProperty("viewport_scales")
                .EnumerateArray()
                .Select(item => item.GetDouble()));
    }

    [Fact]
    public void CreateRejectsAChangedDbMod()
    {
        var snapshot = DrawingSetupFixtures.UnsortedSnapshot(dbModAfter: 1);

        var error = Assert.Throws<InvalidOperationException>(
            () => DrawingSetupPayload.Create(snapshot));

        Assert.Contains("DBMOD", error.Message, StringComparison.OrdinalIgnoreCase);
    }
}
