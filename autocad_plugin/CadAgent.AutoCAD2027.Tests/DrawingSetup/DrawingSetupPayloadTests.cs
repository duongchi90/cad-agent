using CadAgent.AutoCAD2027.Drawing;
using Xunit;

namespace CadAgent.AutoCAD2027.Tests.DrawingSetup;

public sealed class DrawingSetupPayloadTests
{
    [Fact]
    public void PayloadSortsLayersStylesLayoutsAndViewportsOrdinally()
    {
        var snapshot = DrawingSetupFixtures.UnsortedSnapshot();
        var payload = DrawingSetupPayload.Create(snapshot);

        Assert.Equal(
            new[] { "0", "NET_CHINH" },
            payload["layers"].EnumerateArray().Select(item => item.GetProperty("name").GetString()));
        Assert.False(payload["changed"].GetBoolean());
        Assert.Equal(0, payload["dbmod_before"].GetInt32());
        Assert.Equal(0, payload["dbmod_after"].GetInt32());
    }
}
