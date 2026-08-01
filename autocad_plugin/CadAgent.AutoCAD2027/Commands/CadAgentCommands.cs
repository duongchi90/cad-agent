using System.Text.Json;
using Autodesk.AutoCAD.Runtime;
using CadAgent.AutoCAD2027.Ipc;
using CadAgent.AutoCAD2027.Review;

namespace CadAgent.AutoCAD2027.Commands;

public sealed class CadAgentCommands
{
    private const string ManualHealthRequestId = "manual-health";
    private const string ManualReviewRequestId = "manual-review";
    private const string ManualCloseDisposableRequestId = "manual-close-disposable";
    private readonly Func<CommandContext> _contextFactory;

    public static IReadOnlyList<string> RegisteredCommandNames { get; } = new[]
    {
        "CADAGENT_HEALTH",
        "CADAGENT_DISPATCH",
        "CADAGENT_REVIEW",
        "CADAGENT_CLOSE_DISPOSABLE"
    };

    public CadAgentCommands()
        : this(CommandContext.CreateLive)
    {
    }

    public CadAgentCommands(Func<CommandContext> contextFactory)
    {
        _contextFactory = contextFactory ?? throw new ArgumentNullException(nameof(contextFactory));
    }

    [CommandMethod("CADAGENT_HEALTH")]
    public void Health()
    {
        var context = _contextFactory();
        var request = new IpcRequest
        {
            RequestId = ManualHealthRequestId,
            SchemaVersion = ContractConstants.SchemaVersion,
            Operation = "health",
            DrawingFullPath = null,
            DrawingSha256 = null,
            Parameters = new Dictionary<string, JsonElement>(StringComparer.Ordinal),
            Approval = null
        };
        ReportResult(context, context.CreateDispatcher().Dispatch(request));
    }

    [CommandMethod("CADAGENT_DISPATCH")]
    public void Dispatch()
    {
        var context = _contextFactory();
        var requestId = context.GetPendingRequestIds().FirstOrDefault();
        if (requestId is null)
        {
            context.Report("CADAGENT_DISPATCH: no pending .NET request was found.");
            return;
        }

        var dispatcher = context.CreateDispatcher();
        IpcResult result;
        try
        {
            result = dispatcher.Dispatch(context.Store.ReadRequest(requestId));
        }
        catch (System.Exception exception)
        {
            result = dispatcher.ErrorToResult(
                new IpcRequest
                {
                    RequestId = requestId,
                    SchemaVersion = ContractConstants.SchemaVersion,
                    Operation = "health",
                    DrawingFullPath = null,
                    DrawingSha256 = null,
                    Parameters = new Dictionary<string, JsonElement>(StringComparer.Ordinal),
                    Approval = null
                },
                exception);
        }

        context.Store.WriteResult(result);
        context.Report($"CADAGENT_DISPATCH: request {requestId} completed (success={result.Success}).");
    }

    [CommandMethod("CADAGENT_REVIEW")]
    public void Review()
    {
        var context = _contextFactory();
        var startedAt = context.Clock();
        var review = new ReviewEngine(context.DrawingGateway).Review(
            new ReviewRequest(context.DrawingGateway.ActiveDocumentFullPath, Array.Empty<string>()));
        var result = new IpcResult
        {
            RequestId = ManualReviewRequestId,
            Success = review.Success,
            Operation = "review",
            DrawingFullPath = review.DrawingFullPath,
            Changed = review.Changed,
            EntityHandles = review.EntityHandles.ToList(),
            Warnings = review.Warnings.ToList(),
            Errors = review.Errors.ToList(),
            StartedAt = startedAt,
            CompletedAt = context.Clock(),
            Payload = review.Payload.ToDictionary(
                item => item.Key,
                item => item.Value,
                StringComparer.Ordinal)
        };
        ReportResult(context, result);
    }

    [CommandMethod("CADAGENT_CLOSE_DISPOSABLE")]
    public void CloseDisposable()
    {
        var context = _contextFactory();
        var request = new IpcRequest
        {
            RequestId = ManualCloseDisposableRequestId,
            SchemaVersion = ContractConstants.SchemaVersion,
            Operation = "close_disposable",
            DrawingFullPath = context.DrawingGateway.ActiveDocumentFullPath,
            DrawingSha256 = null,
            Parameters = new Dictionary<string, JsonElement>(StringComparer.Ordinal)
            {
                ["disposable"] = JsonSerializer.SerializeToElement(true),
                ["save_changes"] = JsonSerializer.SerializeToElement(false)
            },
            Approval = null
        };
        ReportResult(context, context.CreateDispatcher().Dispatch(request));
    }

    private static void ReportResult(CommandContext context, IpcResult result)
    {
        context.Report(ContractJson.Serialize(result));
    }
}
