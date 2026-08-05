using System.Buffers.Binary;
using System.Security.Cryptography;
using System.Text;
using CadAgent.AutoCAD2027.Ipc;

namespace CadAgent.AutoCAD2027.Drawing;

public sealed class NativeRenderArtifactBoundary
{
    private const string NativeRenderDirectoryName = "native-render";
    private const string ClaimFileName = ".claim";
    private const int MaxPngDimension = 100_000;
    private const long MaxPngPixels = 100_000_000;
    private const long MaxArtifactBytes = 256L * 1024 * 1024;
    private static readonly byte[] PngSignature =
    {
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A
    };

    public NativeRenderArtifactReservation Reserve(
        string ipcRoot,
        string requestId,
        string artifactKind)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(ipcRoot);
        ContractValidator.EnsureRequestId(requestId);
        ValidateRequestIdForPath(requestId);
        var suffix = artifactKind switch
        {
            "PNG" => ".png",
            "PDF" => ".pdf",
            _ => throw new ArgumentException("artifact_kind must be PNG or PDF.", nameof(artifactKind))
        };

        var normalizedRoot = Path.GetFullPath(ipcRoot);
        Directory.CreateDirectory(normalizedRoot);
        RejectReparsePoint(normalizedRoot);

        var nativeRoot = Path.GetFullPath(Path.Combine(normalizedRoot, NativeRenderDirectoryName));
        EnsureWithin(normalizedRoot, nativeRoot);
        Directory.CreateDirectory(nativeRoot);
        RejectReparsePoint(nativeRoot);

        var requestDirectory = Path.GetFullPath(Path.Combine(nativeRoot, requestId));
        EnsureWithin(nativeRoot, requestDirectory);
        if (Directory.Exists(requestDirectory) || File.Exists(requestDirectory))
        {
            throw new IOException("The native render request directory already exists.");
        }

        Directory.CreateDirectory(requestDirectory);
        try
        {
            RejectReparsePoint(requestDirectory);
            var claimPath = Path.Combine(requestDirectory, ClaimFileName);
            var claim = new FileStream(
                claimPath,
                FileMode.CreateNew,
                FileAccess.Write,
                FileShare.None,
                128,
                FileOptions.WriteThrough);
            try
            {
                var claimBytes = Encoding.UTF8.GetBytes(requestId);
                claim.Write(claimBytes, 0, claimBytes.Length);
                claim.Flush(flushToDisk: true);
            }
            catch
            {
                claim.Dispose();
                DeleteIfExists(claimPath);
                throw;
            }

            var finalPath = Path.Combine(requestDirectory, $"artifact{suffix}");
            var temporaryPath = Path.Combine(
                requestDirectory,
                $".artifact.{Guid.NewGuid():N}.tmp{suffix}");
            EnsureWithin(requestDirectory, finalPath);
            EnsureWithin(requestDirectory, temporaryPath);
            if (File.Exists(finalPath))
            {
                claim.Dispose();
                DeleteIfExists(claimPath);
                throw new IOException("The native render artifact already exists.");
            }

            return new NativeRenderArtifactReservation(
                requestDirectory,
                temporaryPath,
                finalPath,
                Path.Combine(NativeRenderDirectoryName, requestId, $"artifact{suffix}")
                    .Replace(Path.DirectorySeparatorChar, '/'),
                claimPath,
                claim,
                artifactKind);
        }
        catch
        {
            // The request directory is deliberately retained. It prevents a
            // retry from silently taking ownership of a failed request.
            throw;
        }
    }

    public NativeRenderArtifact Publish(NativeRenderArtifactReservation reservation)
    {
        ArgumentNullException.ThrowIfNull(reservation);
        reservation.ThrowIfDisposed();
        if (reservation.IsPublished)
        {
            throw new InvalidOperationException("The native render artifact is already published.");
        }

        if (!File.Exists(reservation.TemporaryPath))
        {
            throw new InvalidDataException("The native render temporary artifact does not exist.");
        }

        var temporaryInfo = new FileInfo(reservation.TemporaryPath);
        if (temporaryInfo.Length <= 0 || temporaryInfo.Length > MaxArtifactBytes)
        {
            throw new InvalidDataException("The native render temporary artifact has an invalid size.");
        }

        var temporaryBytes = File.ReadAllBytes(reservation.TemporaryPath);
        if (temporaryBytes.LongLength != temporaryInfo.Length)
        {
            throw new InvalidDataException("The native render temporary artifact changed while reading.");
        }

        var metadata = ValidateBytes(temporaryBytes, reservation.ArtifactKind);
        var temporaryHash = Hash(temporaryBytes);

        if (File.Exists(reservation.FinalPath))
        {
            throw new IOException("The native render final artifact already exists.");
        }

        reservation.ReleaseClaim();
        try
        {
            File.Move(reservation.TemporaryPath, reservation.FinalPath, overwrite: false);
            var finalBytes = File.ReadAllBytes(reservation.FinalPath);
            var finalHash = Hash(finalBytes);
            if (!string.Equals(temporaryHash, finalHash, StringComparison.Ordinal))
            {
                DeleteIfExists(reservation.FinalPath);
                throw new InvalidDataException("The native render final artifact hash changed after publication.");
            }

            reservation.MarkPublished();
            return new NativeRenderArtifact(
                reservation.RelativePath,
                finalHash,
                metadata.Width,
                metadata.Height,
                metadata.PageCount);
        }
        catch
        {
            if (!reservation.IsPublished)
            {
                DeleteIfExists(reservation.FinalPath);
            }

            throw;
        }
    }

    private static ArtifactMetadata ValidateBytes(byte[] bytes, string artifactKind) =>
        artifactKind switch
        {
            "PNG" => ValidatePng(bytes),
            "PDF" => ValidatePdf(bytes),
            _ => throw new InvalidDataException("The native render artifact kind is unsupported.")
        };

    private static ArtifactMetadata ValidatePng(byte[] bytes)
    {
        if (bytes.Length < 45 || !bytes.AsSpan(0, PngSignature.Length).SequenceEqual(PngSignature))
        {
            throw new InvalidDataException("The native render PNG signature is invalid.");
        }

        var offset = PngSignature.Length;
        var sawHeader = false;
        var sawEnd = false;
        long width = 0;
        long height = 0;
        while (offset + 12 <= bytes.Length)
        {
            var chunkLength = BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(offset, 4));
            if (chunkLength > int.MaxValue || offset + 12L + chunkLength > bytes.Length)
            {
                throw new InvalidDataException("The native render PNG contains a truncated chunk.");
            }

            var chunkType = Encoding.ASCII.GetString(bytes, offset + 4, 4);
            if (!sawHeader && chunkType != "IHDR")
            {
                throw new InvalidDataException("The native render PNG is missing its IHDR chunk.");
            }

            if (chunkType == "IHDR")
            {
                if (sawHeader || offset != PngSignature.Length || chunkLength != 13)
                {
                    throw new InvalidDataException("The native render PNG IHDR chunk is invalid.");
                }

                width = BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(offset + 8, 4));
                height = BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(offset + 12, 4));
                if (width is < 1 or > MaxPngDimension
                    || height is < 1 or > MaxPngDimension
                    || width * height > MaxPngPixels)
                {
                    throw new InvalidDataException("The native render PNG dimensions are invalid.");
                }

                sawHeader = true;
            }

            offset += checked((int)(12 + chunkLength));
            if (chunkType == "IEND")
            {
                if (chunkLength != 0 || offset != bytes.Length)
                {
                    throw new InvalidDataException("The native render PNG IEND chunk is invalid.");
                }

                sawEnd = true;
                break;
            }
        }

        if (!sawHeader || !sawEnd)
        {
            throw new InvalidDataException("The native render PNG is incomplete.");
        }

        return new ArtifactMetadata(width, height, null);
    }

    private static ArtifactMetadata ValidatePdf(byte[] bytes)
    {
        if (bytes.Length < 16
            || !Encoding.ASCII.GetString(bytes, 0, 5).Equals("%PDF-", StringComparison.Ordinal))
        {
            throw new InvalidDataException("The native render PDF header is invalid.");
        }

        var tailStart = Math.Max(0, bytes.Length - 1024);
        var tail = Encoding.ASCII.GetString(bytes, tailStart, bytes.Length - tailStart);
        if (!tail.Contains("%%EOF", StringComparison.Ordinal))
        {
            throw new InvalidDataException("The native render PDF is missing its EOF trailer.");
        }

        var text = Encoding.Latin1.GetString(bytes);
        var pageCount = CountPdfPages(text);
        if (pageCount != 1)
        {
            throw new InvalidDataException("The native render PDF must contain exactly one page.");
        }

        return new ArtifactMetadata(null, null, pageCount);
    }

    private static int CountPdfPages(string text)
    {
        var count = 0;
        var offset = 0;
        while (offset < text.Length)
        {
            var typeIndex = text.IndexOf("/Type", offset, StringComparison.Ordinal);
            if (typeIndex < 0)
            {
                break;
            }

            var valueIndex = typeIndex + "/Type".Length;
            while (valueIndex < text.Length && char.IsWhiteSpace(text[valueIndex]))
            {
                valueIndex++;
            }

            if (text.AsSpan(valueIndex).StartsWith("/Page", StringComparison.Ordinal))
            {
                var end = valueIndex + "/Page".Length;
                if (end == text.Length || !char.IsLetterOrDigit(text[end]))
                {
                    count++;
                }
            }

            offset = valueIndex + 1;
        }

        return count;
    }

    private static void ValidateRequestIdForPath(string requestId)
    {
        if (requestId.Any(char.IsControl)
            || requestId.Contains('/', StringComparison.Ordinal)
            || requestId.Contains('\\', StringComparison.Ordinal)
            || requestId.Contains(':', StringComparison.Ordinal)
            || requestId.Contains("..", StringComparison.Ordinal)
            || Path.IsPathRooted(requestId)
            || (requestId.Length >= 2 && char.IsLetter(requestId[0]) && requestId[1] == ':'))
        {
            throw new ArgumentException(
                "request_id contains unsafe path characters.",
                nameof(requestId));
        }
    }

    private static void EnsureWithin(string root, string candidate)
    {
        var normalizedRoot = Path.GetFullPath(root).TrimEnd(
                Path.DirectorySeparatorChar,
                Path.AltDirectorySeparatorChar)
            + Path.DirectorySeparatorChar;
        var normalizedCandidate = Path.GetFullPath(candidate).TrimEnd(
                Path.DirectorySeparatorChar,
                Path.AltDirectorySeparatorChar)
            + Path.DirectorySeparatorChar;
        if (!normalizedCandidate.StartsWith(normalizedRoot, StringComparison.OrdinalIgnoreCase))
        {
            throw new IOException("The native render path escapes its owner directory.");
        }
    }

    private static void RejectReparsePoint(string path)
    {
        var attributes = File.GetAttributes(path);
        if ((attributes & FileAttributes.ReparsePoint) != 0)
        {
            throw new IOException("Reparse points are not allowed in native render paths.");
        }
    }

    private static string Hash(byte[] bytes) =>
        Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();

    private static void DeleteIfExists(string path)
    {
        if (File.Exists(path))
        {
            File.Delete(path);
        }
    }

    private sealed record ArtifactMetadata(long? Width, long? Height, long? PageCount);
}

public sealed class NativeRenderArtifactReservation : IDisposable
{
    private FileStream? _claim;
    private bool _disposed;

    internal NativeRenderArtifactReservation(
        string requestDirectory,
        string temporaryPath,
        string finalPath,
        string relativePath,
        string claimPath,
        FileStream claim,
        string artifactKind)
    {
        RequestDirectory = requestDirectory;
        TemporaryPath = temporaryPath;
        FinalPath = finalPath;
        RelativePath = relativePath;
        ClaimPath = claimPath;
        _claim = claim;
        ArtifactKind = artifactKind;
    }

    public string RequestDirectory { get; }

    public string TemporaryPath { get; }

    public string FinalPath { get; }

    public string RelativePath { get; }

    public bool IsPublished { get; private set; }

    internal string ClaimPath { get; }

    internal string ArtifactKind { get; }

    internal void ThrowIfDisposed()
    {
        if (_disposed)
        {
            throw new ObjectDisposedException(nameof(NativeRenderArtifactReservation));
        }
    }

    internal void ReleaseClaim()
    {
        _claim?.Dispose();
        _claim = null;
        if (File.Exists(ClaimPath))
        {
            File.Delete(ClaimPath);
        }
    }

    internal void MarkPublished() => IsPublished = true;

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        try
        {
            if (!IsPublished && File.Exists(TemporaryPath))
            {
                File.Delete(TemporaryPath);
            }
        }
        finally
        {
            _claim?.Dispose();
            _claim = null;
            if (File.Exists(ClaimPath))
            {
                File.Delete(ClaimPath);
            }

            _disposed = true;
        }
    }
}
