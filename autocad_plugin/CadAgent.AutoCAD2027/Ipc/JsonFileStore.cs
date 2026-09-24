using System.Text;
using System.Text.Json;
using System.Security.Cryptography;
using System.ComponentModel;
using Microsoft.Win32.SafeHandles;

namespace CadAgent.AutoCAD2027.Ipc;

public sealed class JsonFileStore
{
    private readonly bool _ipcDirectoryIsCanonical;

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
        _ipcDirectoryIsCanonical = ProtectedIpcDirectoryPolicy.IsCanonical(ipcDirectory, IpcDirectory);
        MaxReadBytes = maxReadBytes;
        Directory.CreateDirectory(IpcDirectory);
    }

    public string IpcDirectory { get; }

    public long MaxReadBytes { get; }

    public void EnsureProtectedForNativeEdit() =>
        ProtectedIpcDirectoryPolicy.EnsureProtected(IpcDirectory, _ipcDirectoryIsCanonical);

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
        return ReadRequestCore(requestId, captureFileIpcIdentity: false).Request;
    }

    internal IpcRequestReadSnapshot ReadRequestForDispatch(string requestId) =>
        ReadRequestCore(requestId, captureFileIpcIdentity: true);

    private IpcRequestReadSnapshot ReadRequestCore(string requestId, bool captureFileIpcIdentity)
    {
        ContractValidator.EnsureRequestId(requestId);
        var requestPath = GetRequestPath(requestId);
        SafeFileHandle? rootHandle = null;
        IpcFileIdentity? rootIdentity = null;
        if (captureFileIpcIdentity && OperatingSystem.IsWindows())
        {
            try
            {
                rootHandle = ProtectedIpcDirectoryPolicy.OpenDirectoryForObservation(IpcDirectory);
                if (TryCapturePathIdentity(rootHandle, IpcDirectory, directory: true, out var identity))
                {
                    rootIdentity = identity;
                }
                else
                {
                    rootHandle.Dispose();
                    rootHandle = null;
                }
            }
            catch (Exception exception) when (IsIdentityObservationFailure(exception))
            {
                rootHandle?.Dispose();
                rootHandle = null;
            }
        }

        using (rootHandle)
        using (var stream = new FileStream(requestPath, FileMode.Open, FileAccess.Read, FileShare.Read))
        {
            IpcFileIdentity? requestIdentity = null;
            var requestPathMatches = false;
            if (captureFileIpcIdentity && OperatingSystem.IsWindows())
            {
                requestPathMatches = TryCapturePathIdentity(
                    stream.SafeFileHandle,
                    requestPath,
                    directory: false,
                    out var identity);
                if (requestPathMatches)
                {
                    requestIdentity = identity;
                }
            }

            var json = ReadJson(stream, out var requestBytes);
            var request = ValidateRequestJson(requestId, json);
            var rootPathStable = rootHandle is not null
                && rootIdentity.HasValue
                && TryCapturePathIdentity(rootHandle, IpcDirectory, directory: true, out var currentRootIdentity)
                && currentRootIdentity == rootIdentity.Value;
            var requestPathStable = requestIdentity.HasValue
                && requestPathMatches
                && TryCapturePathIdentity(stream.SafeFileHandle, requestPath, directory: false, out var currentRequestIdentity)
                && currentRequestIdentity == requestIdentity.Value;
            var contentSha256 = rootPathStable && requestPathStable
                ? Convert.ToHexString(SHA256.HashData(requestBytes))
                : null;

            return new IpcRequestReadSnapshot(
                request,
                IpcDirectory,
                requestPath,
                rootPathStable ? rootIdentity : null,
                requestPathStable ? requestIdentity : null,
                contentSha256);
        }
    }

    private IpcRequest ValidateRequestJson(string requestId, string json)
    {
        var request = DeserializeRequest(json);
        EnsureMatchingRequestId(request.RequestId, requestId);
        var validation = ContractValidator.ValidateRequest(request);
        if (!validation.IsValid)
        {
            throw new InvalidDataException(string.Join("; ", validation.Errors));
        }

        return request;
    }

    internal NativeEditFileIpcCustody AcquireNativeEditCustody(IpcRequestReadSnapshot? requestRead)
    {
        if (requestRead?.RootIdentity is not { } expectedRootIdentity
            || requestRead.RequestIdentity is not { } expectedRequestIdentity
            || requestRead.ContentSha256 is null)
        {
            throw new InvalidDataException("Native edits require an identity-bound FileIPC request read.");
        }

        var requestId = requestRead.Request.RequestId
            ?? throw new InvalidDataException("The FileIPC request id is missing.");
        if (!ProtectedIpcDirectoryPolicy.PathsEqual(requestRead.IpcDirectory, IpcDirectory)
            || !ProtectedIpcDirectoryPolicy.PathsEqual(requestRead.RequestPath, GetRequestPath(requestId)))
        {
            throw new InvalidDataException("The FileIPC request path changed since it was read.");
        }

        var directoryCustody = ProtectedIpcDirectoryPolicy.AcquireProtectedDirectory(
            IpcDirectory,
            _ipcDirectoryIsCanonical);
        SafeFileHandle? requestHandle = null;
        FileStream? requestStream = null;
        try
        {
            if (directoryCustody.RootIdentity != expectedRootIdentity)
            {
                throw new InvalidDataException("The FileIPC root changed since the request was read.");
            }

            requestHandle = ProtectedIpcDirectoryPolicy.OpenRequestFileForCustody(requestRead.RequestPath);
            if (ProtectedIpcDirectoryPolicy.GetFileIdentity(requestHandle) != expectedRequestIdentity
                || !ProtectedIpcDirectoryPolicy.PathsEqual(
                    ProtectedIpcDirectoryPolicy.GetFinalPath(requestHandle),
                    requestRead.RequestPath))
            {
                throw new InvalidDataException("The FileIPC request changed since it was read.");
            }

            requestStream = new FileStream(requestHandle, FileAccess.Read, bufferSize: 4096, isAsync: false);
            requestHandle = null;
            var json = ReadJson(requestStream, out var requestBytes);
            if (!string.Equals(
                    Convert.ToHexString(SHA256.HashData(requestBytes)),
                    requestRead.ContentSha256,
                    StringComparison.Ordinal))
            {
                throw new InvalidDataException("The FileIPC request changed since it was read.");
            }

            var request = ValidateRequestJson(requestId, json);
            return new NativeEditFileIpcCustody(directoryCustody, requestStream, request);
        }
        catch
        {
            requestStream?.Dispose();
            requestHandle?.Dispose();
            directoryCustody.Dispose();
            throw;
        }
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

    private string ReadJson(FileStream stream, out byte[] rawBytes)
    {
        if (stream.Length > MaxReadBytes || stream.Length > int.MaxValue)
        {
            throw new InvalidDataException($"JSON exceeds the {MaxReadBytes}-byte limit.");
        }

        stream.Position = 0;
        rawBytes = new byte[(int)stream.Length];
        stream.ReadExactly(rawBytes);
        using var memory = new MemoryStream(rawBytes, writable: false);
        using var reader = new StreamReader(
            memory,
            new UTF8Encoding(encoderShouldEmitUTF8Identifier: false, throwOnInvalidBytes: true),
            detectEncodingFromByteOrderMarks: true);
        var json = reader.ReadToEnd();
        if (Encoding.UTF8.GetByteCount(json) > MaxReadBytes)
        {
            throw new InvalidDataException($"JSON exceeds the {MaxReadBytes}-byte limit.");
        }

        return json;
    }

    private static bool TryCapturePathIdentity(
        SafeFileHandle handle,
        string expectedPath,
        bool directory,
        out IpcFileIdentity identity)
    {
        identity = default;
        try
        {
            var attributes = ProtectedIpcDirectoryPolicy.GetFileAttributes(handle);
            if (((attributes & FileAttributes.Directory) != 0) != directory
                || (attributes & FileAttributes.ReparsePoint) != 0
                || !ProtectedIpcDirectoryPolicy.PathsEqual(
                    ProtectedIpcDirectoryPolicy.GetFinalPath(handle),
                    expectedPath))
            {
                return false;
            }

            identity = ProtectedIpcDirectoryPolicy.GetFileIdentity(handle);
            return true;
        }
        catch (Exception exception) when (IsIdentityObservationFailure(exception))
        {
            return false;
        }
    }

    private static bool IsIdentityObservationFailure(Exception exception) =>
        exception is IOException
            or UnauthorizedAccessException
            or Win32Exception
            or PlatformNotSupportedException;

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

internal sealed record IpcRequestReadSnapshot(
    IpcRequest Request,
    string IpcDirectory,
    string RequestPath,
    IpcFileIdentity? RootIdentity,
    IpcFileIdentity? RequestIdentity,
    string? ContentSha256);

internal sealed class NativeEditFileIpcCustody : IDisposable
{
    private readonly ProtectedIpcDirectoryCustody _directoryCustody;
    private readonly FileStream _requestStream;

    internal NativeEditFileIpcCustody(
        ProtectedIpcDirectoryCustody directoryCustody,
        FileStream requestStream,
        IpcRequest request)
    {
        _directoryCustody = directoryCustody;
        _requestStream = requestStream;
        Request = request;
    }

    internal IpcRequest Request { get; }

    public void Dispose()
    {
        _requestStream.Dispose();
        _directoryCustody.Dispose();
    }
}
