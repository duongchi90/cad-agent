using System.Text.Json;
using CadAgent.AutoCAD2027.Commands;
using CadAgent.AutoCAD2027.Review;

namespace CadAgent.AutoCAD2027.Ipc;

public sealed class OperationDispatcher
{
    public const string PluginVersion = "1.0.0";

    private readonly CommandContext _context;
    private readonly ReviewEngine _reviewEngine;

    public OperationDispatcher(CommandContext context)
    {
        _context = context ?? throw new ArgumentNullException(nameof(context));
        _reviewEngine = new ReviewEngine(context.DrawingGateway);
    }

    public IpcResult Dispatch(IpcRequest? request)
    {
        var startedAt = _context.Clock();
        if (request is null)
        {
            return ErrorToResult(null, new ArgumentNullException(nameof(request)), startedAt);
        }

        try
        {
            var validation = ContractValidator.ValidateRequest(request);
            if (!validation.IsValid)
            {
                return Failure(request, validation.Errors, startedAt);
            }

            return request.Operation switch
            {
                "health" => DispatchHealth(request, startedAt),
                "review" => DispatchReview(request, startedAt),
                "close_disposable" => DispatchCloseDisposable(request, startedAt),
                _ => Failure(request, new[] { "operation is not supported" }, startedAt)
            };
        }
        catch (System.Exception exception)
        {
            return ErrorToResult(request, exception, startedAt);
        }
    }

    public IpcResult ErrorToResult(
        IpcRequest? request,
        System.Exception exception,
        DateTimeOffset? startedAt = null)
    {
        ArgumentNullException.ThrowIfNull(exception);
        var started = startedAt ?? _context.Clock();
        var operation = GetResultOperation(request?.Operation);
        var payload = new Dictionary<string, JsonElement>(StringComparer.Ordinal);
        if (!string.IsNullOrWhiteSpace(request?.Operation)
            && !string.Equals(request.Operation, operation, StringComparison.Ordinal))
        {
            payload["requested_operation"] = JsonSerializer.SerializeToElement(request.Operation);
        }

        return CreateResult(
            request?.RequestId is { Length: > 0 } requestId ? requestId : "invalid-request",
            operation,
            NormalizePathOrNull(request?.DrawingFullPath),
            success: false,
            changed: false,
            entityHandles: Array.Empty<string>(),
            warnings: Array.Empty<string>(),
            errors: new[] { exception.Message },
            payload,
            started);
    }

    private IpcResult DispatchHealth(IpcRequest request, DateTimeOffset startedAt)
    {
        var activePath = NormalizePathOrNull(_context.DrawingGateway.ActiveDocumentFullPath);
        var payload = new Dictionary<string, JsonElement>(StringComparer.Ordinal)
        {
            ["host"] = JsonSerializer.SerializeToElement("AutoCAD Mechanical 2027"),
            ["plugin_version"] = JsonSerializer.SerializeToElement(PluginVersion),
            ["active_document"] = JsonSerializer.SerializeToElement(activePath is not null),
            ["ipc_directory"] = JsonSerializer.SerializeToElement(_context.Store.IpcDirectory),
            ["ipc_readable"] = JsonSerializer.SerializeToElement(true),
            ["ipc_writable"] = JsonSerializer.SerializeToElement(true),
            ["read_only"] = JsonSerializer.SerializeToElement(true)
        };

        return CreateResult(
            request.RequestId!,
            "health",
            activePath,
            success: true,
            changed: false,
            entityHandles: Array.Empty<string>(),
            warnings: Array.Empty<string>(),
            errors: Array.Empty<string>(),
            payload,
            startedAt);
    }

    private IpcResult DispatchReview(IpcRequest request, DateTimeOffset startedAt)
    {
        var handles = request.Parameters!["handles"]
            .EnumerateArray()
            .Select(value => value.GetString()!)
            .ToArray();
        var review = _reviewEngine.Review(new ReviewRequest(request.DrawingFullPath, handles));
        return CreateResult(
            request.RequestId!,
            "review",
            review.DrawingFullPath,
            review.Success,
            review.Changed,
            review.EntityHandles,
            review.Warnings,
            review.Errors,
            review.Payload.ToDictionary(item => item.Key, item => item.Value, StringComparer.Ordinal),
            startedAt);
    }

    private IpcResult DispatchCloseDisposable(IpcRequest request, DateTimeOffset startedAt)
    {
        if (!TryMatchActiveDocument(request.DrawingFullPath, out var activePath, out var error))
        {
            return Failure(request, new[] { error }, startedAt);
        }

        _context.CloseWithoutSaving();
        var payload = new Dictionary<string, JsonElement>(StringComparer.Ordinal)
        {
            ["closed_without_saving"] = JsonSerializer.SerializeToElement(true)
        };
        return CreateResult(
            request.RequestId!,
            "close_disposable",
            activePath,
            success: true,
            changed: false,
            entityHandles: Array.Empty<string>(),
            warnings: Array.Empty<string>(),
            errors: Array.Empty<string>(),
            payload,
            startedAt);
    }

    private bool TryMatchActiveDocument(
        string? requestedPath,
        out string activePath,
        out string error)
    {
        activePath = NormalizePathOrNull(_context.DrawingGateway.ActiveDocumentFullPath) ?? string.Empty;
        if (activePath.Length == 0)
        {
            error = "No active document is available.";
            return false;
        }

        var normalizedRequestedPath = NormalizePathOrNull(requestedPath);
        if (normalizedRequestedPath is null
            || !StringComparer.OrdinalIgnoreCase.Equals(normalizedRequestedPath, activePath))
        {
            error = "The requested drawing_full_path does not match the active document full path.";
            return false;
        }

        error = string.Empty;
        return true;
    }

    private IpcResult Failure(
        IpcRequest request,
        IEnumerable<string> errors,
        DateTimeOffset startedAt) =>
        CreateResult(
            request.RequestId is { Length: > 0 } requestId ? requestId : "invalid-request",
            GetResultOperation(request.Operation),
            NormalizePathOrNull(request.DrawingFullPath),
            success: false,
            changed: false,
            entityHandles: Array.Empty<string>(),
            warnings: Array.Empty<string>(),
            errors,
            CreateRequestedOperationPayload(request.Operation),
            startedAt);

    private IpcResult CreateResult(
        string requestId,
        string operation,
        string? drawingFullPath,
        bool success,
        bool changed,
        IEnumerable<string> entityHandles,
        IEnumerable<string> warnings,
        IEnumerable<string> errors,
        Dictionary<string, JsonElement> payload,
        DateTimeOffset startedAt) =>
        new()
        {
            RequestId = requestId,
            Success = success,
            Operation = operation,
            DrawingFullPath = drawingFullPath,
            Changed = changed,
            EntityHandles = entityHandles.ToList(),
            Warnings = warnings.ToList(),
            Errors = errors.ToList(),
            StartedAt = startedAt,
            CompletedAt = _context.Clock(),
            Payload = payload
        };

    private static Dictionary<string, JsonElement> CreateRequestedOperationPayload(string? operation)
    {
        var payload = new Dictionary<string, JsonElement>(StringComparer.Ordinal);
        if (!string.IsNullOrWhiteSpace(operation)
            && !ContractConstants.SupportedOperations.Contains(operation))
        {
            payload["requested_operation"] = JsonSerializer.SerializeToElement(operation);
        }

        return payload;
    }

    private static string GetResultOperation(string? operation) =>
        operation is not null && ContractConstants.SupportedOperations.Contains(operation)
            ? operation
            : "health";

    private static string? NormalizePathOrNull(string? path) =>
        path is not null && ContractValidator.TryNormalizeWindowsAbsolutePath(path, out var normalized)
            ? normalized
            : null;
}
