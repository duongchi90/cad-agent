using CadAgent.AutoCAD2027.Commands;
using Xunit;

namespace CadAgent.AutoCAD2027.Tests.Commands;

public sealed class CommandGuardTests
{
    [Fact]
    public void RegistersExactlyTheFourTaskCommands()
    {
        Assert.Equal(
            new[]
            {
                "CADAGENT_CLOSE_DISPOSABLE",
                "CADAGENT_DISPATCH",
                "CADAGENT_HEALTH",
                "CADAGENT_REVIEW"
            },
            CadAgentCommands.RegisteredCommandNames.OrderBy(name => name, StringComparer.Ordinal));
    }
}
