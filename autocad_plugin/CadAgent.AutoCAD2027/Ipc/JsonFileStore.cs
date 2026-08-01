using System.Text;
using System.Text.Json;

namespace CadAgent.AutoCAD2027.Ipc;

public sealed class JsonFileStore
{
    public JsonFileStore(
        string ipcDirectory,
        long maxReadBytes = ContractConstants.DefaultMaxReadBytes)
    {
        if (string.IsNullOrWhiteSpace(ipcDirectory))
        {
            throw new ArgumentException("The IPC directory is required.", nameof(ipcDirectory));
        }

        if (maxReadBytes <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(maxReadBytes));
        }

        IpcDirectory = Path.GetFullPath(ipcDirectory);
        MaxReadBytes = maxReadBytes;
        Directory.CreateDirectory(IpcDirectory);
    }

    public string IpcDirectory { get; }

    public long MaxReadBytes { get; }

    public static string GetRequestFileName(string requestId)
    {
        ContractValidator.EnsureRequestId(requestId);
        return $"cadagent_dotnet_request_{requestId}.json";
    }

    public static string GetResultFileName(string requestId)
    {
        ContractValidator.EnsureRequestId(requestId);
        return $"cadagent_dotnet_result_{requestId}.json";
    }

    public string GetRequestPath(string requestId) =>
        Path.Combine(IpcDirectory, GetRequestFileName(requestId));

    public string GetResultPath(string requestId) =>
        Path.Combine(IpcDirectory, GetResultFileName(requestId));

    public string GetRequestFilePath(string requestId) => GetRequestPath(requestId);

    public string GetResultFilePath(string requestId) => GetResultPath(requestId);

    public void WriteRequest(IpcRequest request)
    {
        var normalized = ContractValidator.NormalizeRequest(request);
        AtomicWrite(GetRequestPath(normalized.RequestId!), ContractJson.Serialize(normalized));
    }

    public void WriteResult(IpcResult result)
    {
        var normalized = ContractValidator.NormalizeResult(result);
        AtomicWrite(GetResultPath(normalized.RequestId!), ContractJson.Serialize(normalized));
    }

    public IpcRequest ReadRequest(string requestId)
    {
        ContractValidator.EnsureRequestId(requestId);
        var request = DeserializeRequest(ReadJson(GetRequestPath(requestId)));
        EnsureMatchingRequestId(request.RequestId, requestId);
        var validation = ContractValidator.ValidateRequest(request);
        if (!validation.IsValid)
        {
            throw new InvalidDataException(string.Join("; ", validation.Errors));
        }

        return request;
    }

    public IpcRequest? TryReadRequest(string requestId)
    {
        var path = GetRequestPath(requestId);
        return File.Exists(path) ? ReadRequest(requestId) : null;
    }

    public IpcResult ReadResult(string requestId)
    {
        ContractValidator.EnsureRequestId(requestId);
        var result = DeserializeResult(ReadJson(GetResultPath(requestId)));
        EnsureMatchingRequestId(result.RequestId, requestId);
        var validation = ContractValidator.ValidateResult(result);
        if (!validation.IsValid)
        {
            throw new InvalidDataException(string.Join("; ", validation.Errors));
        }

        return result;
    }

    public IpcResult? TryReadResult(string requestId)
    {
        var path = GetResultPath(requestId);
        return File.Exists(path) ? ReadResult(requestId) : null;
    }

    public void Cleanup(string requestId)
    {
        ContractValidator.EnsureRequestId(requestId);
        DeleteIfExists(GetRequestPath(requestId));
        DeleteIfExists(GetResultPath(requestId));
    }

    private void AtomicWrite(string destinationPath, string json)
    {
        var temporaryPath = $"{destinationPath}.{Guid.NewGuid():N}.tmp";
        try
        {
            var bytes = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false).GetBytes(json);
            if (bytes.LongLength > MaxReadBytes)
            {
                throw new InvalidDataException($"JSON exceeds the {MaxReadBytes}-byte limit.");
            }

            using (var stream = new FileStream(
                       temporaryPath,
                       FileMode.CreateNew,
                       FileAccess.Write,
                       FileShare.None,
                       bufferSize: 4096,
                       options: FileOptions.WriteThrough))
            {
                stream.Write(bytes, 0, bytes.Length);
                stream.Flush(flushToDisk: true);
            }

            if (File.Exists(destinationPath))
            {
                File.Replace(temporaryPath, destinationPath, destinationBackupFileName: null);
            }
            else
            {
                File.Move(temporaryPath, destinationPath);
            }
        }
        finally
        {
            DeleteIfExists(temporaryPath);
        }
    }

    private string ReadJson(string path)
    {
        using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read);
        if (stream.Length > MaxReadBytes)
        {
            throw new InvalidDataException($"JSON exceeds the {MaxReadBytes}-byte limit.");
        }

        using var reader = new StreamReader(
            stream,
            new UTF8Encoding(encoderShouldEmitUTF8Identifier: false, throwOnInvalidBytes: true),
            detectEncodingFromByteOrderMarks: true);
        var json = reader.ReadToEnd();
        if (Encoding.UTF8.GetByteCount(json) > MaxReadBytes)
        {
            throw new InvalidDataException($"JSON exceeds the {MaxReadBytes}-byte limit.");
        }

        return json;
    }

    private static IpcRequest DeserializeRequest(string json)
    {
        try
        {
            return ContractJson.DeserializeRequest(json);
        }
        catch (JsonException exception)
        {
            throw new InvalidDataException("The request JSON is invalid.", exception);
        }
    }

    private static IpcResult DeserializeResult(string json)
    {
        try
        {
            return ContractJson.DeserializeResult(json);
        }
        catch (JsonException exception)
        {
            throw new InvalidDataException("The result JSON is invalid.", exception);
        }
    }

    private static void EnsureMatchingRequestId(string? actualRequestId, string expectedRequestId)
    {
        if (!string.Equals(actualRequestId, expectedRequestId, StringComparison.Ordinal))
        {
            throw new InvalidDataException("The JSON request_id does not match the requested file.");
        }
    }

    private static void DeleteIfExists(string path)
    {
        if (File.Exists(path))
        {
            File.Delete(path);
        }
    }
}
