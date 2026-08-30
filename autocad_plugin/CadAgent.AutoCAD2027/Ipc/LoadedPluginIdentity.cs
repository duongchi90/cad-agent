using System.Reflection;
using System.Security.Cryptography;

namespace CadAgent.AutoCAD2027.Ipc;

internal sealed record LoadedPluginIdentitySnapshot(string BinaryPath, string Sha256);

internal static class LoadedPluginIdentity
{
    public static LoadedPluginIdentitySnapshot Capture(Assembly assembly)
    {
        ArgumentNullException.ThrowIfNull(assembly);

        if (string.IsNullOrWhiteSpace(assembly.Location))
        {
            throw new InvalidOperationException("The executing plugin assembly has no file location.");
        }

        return CaptureBinary(assembly.Location);
    }

    public static LoadedPluginIdentitySnapshot CaptureBinary(string binaryPath)
    {
        if (string.IsNullOrWhiteSpace(binaryPath))
        {
            throw new InvalidOperationException("The executing plugin binary path is empty.");
        }

        var fullPath = Path.GetFullPath(binaryPath);
        if (!File.Exists(fullPath))
        {
            throw new InvalidOperationException(
                $"The executing plugin binary does not exist: {fullPath}");
        }

        try
        {
            using var stream = new FileStream(
                fullPath,
                FileMode.Open,
                FileAccess.Read,
                FileShare.ReadWrite | FileShare.Delete);
            var sha256 = Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
            return new LoadedPluginIdentitySnapshot(fullPath, sha256);
        }
        catch (Exception exception) when (
            exception is IOException
            or UnauthorizedAccessException
            or NotSupportedException)
        {
            throw new InvalidOperationException(
                $"The executing plugin binary could not be read: {fullPath}",
                exception);
        }
    }
}
