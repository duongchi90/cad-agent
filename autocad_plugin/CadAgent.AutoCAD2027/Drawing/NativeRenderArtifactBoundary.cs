using System.Buffers.Binary;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
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

    private readonly Action<string, string> _moveFinal;
    private readonly Action<string> _deleteClaim;

    public NativeRenderArtifactBoundary()
        : this(
            (source, destination) => File.Move(source, destination, overwrite: false),
            File.Delete)
    {
    }

    internal NativeRenderArtifactBoundary(Action<string, string> moveFinal)
        : this(moveFinal, File.Delete)
    {
    }

    internal NativeRenderArtifactBoundary(
        Action<string, string> moveFinal,
        Action<string> deleteClaim)
    {
        _moveFinal = moveFinal ?? throw new ArgumentNullException(nameof(moveFinal));
        _deleteClaim = deleteClaim ?? throw new ArgumentNullException(nameof(deleteClaim));
    }

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
            throw new IOException(
                $"{NativeRenderPolicy.DuplicateRequestErrorCode}: "
                + "The native render request directory already exists.");
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
                throw new IOException(
                    $"{NativeRenderPolicy.DuplicateArtifactErrorCode}: "
                    + "The native render artifact already exists.");
            }

            return new NativeRenderArtifactReservation(
                requestDirectory,
                temporaryPath,
                finalPath,
                Path.Combine(NativeRenderDirectoryName, requestId, $"artifact{suffix}")
                    .Replace(Path.DirectorySeparatorChar, '/'),
                claimPath,
                claim,
                _deleteClaim,
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

        try
        {
            _moveFinal(reservation.TemporaryPath, reservation.FinalPath);
            reservation.MarkFinalCreated();
            reservation.MarkPublished();
            return new NativeRenderArtifact(
                reservation.RelativePath,
                temporaryHash,
                metadata.Width,
                metadata.Height,
                metadata.PageCount);
        }
        catch
        {
            DeleteOwnedFinalIfUnchanged(reservation, temporaryHash);

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
        if (bytes.Length < PngSignature.Length
            || !bytes.AsSpan(0, PngSignature.Length).SequenceEqual(PngSignature))
        {
            throw new InvalidDataException("The native render PNG signature is invalid.");
        }

        var offset = PngSignature.Length;
        var sawHeader = false;
        var sawImageData = false;
        var sawPalette = false;
        var sawEnd = false;
        long width = 0;
        long height = 0;
        byte bitDepth = 0;
        byte colorType = 0;
        using var imageData = new MemoryStream();
        while (offset < bytes.Length)
        {
            if (bytes.Length - offset < 12)
            {
                throw new InvalidDataException("The native render PNG contains a truncated chunk.");
            }

            var chunkLength = BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(offset, 4));
            if (chunkLength > int.MaxValue || offset + 12L + chunkLength > bytes.Length)
            {
                throw new InvalidDataException("The native render PNG contains a truncated chunk.");
            }

            var chunkTypeBytes = bytes.AsSpan(offset + 4, 4);
            foreach (var byteValue in chunkTypeBytes)
            {
                if ((byteValue is < (byte)'A' or > (byte)'Z')
                    && (byteValue is < (byte)'a' or > (byte)'z'))
                {
                    throw new InvalidDataException("The native render PNG chunk type is invalid.");
                }
            }

            var chunkType = Encoding.ASCII.GetString(chunkTypeBytes);
            var chunkData = bytes.AsSpan(offset + 8, checked((int)chunkLength));
            var expectedCrc = BinaryPrimitives.ReadUInt32BigEndian(
                bytes.AsSpan(offset + 8 + checked((int)chunkLength), 4));
            if (ComputePngCrc(chunkTypeBytes, chunkData) != expectedCrc)
            {
                throw new InvalidDataException($"The native render PNG {chunkType} CRC is invalid.");
            }

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

                if (!NativeRenderPolicy.IsApprovedPngDimensions(width, height))
                {
                    throw new InvalidDataException(
                        "The native render PNG dimensions do not match the approved A4 300 DPI profile.");
                }

                bitDepth = chunkData[8];
                colorType = chunkData[9];
                if (!IsValidPngIhdr(
                        bitDepth,
                        colorType,
                        chunkData[10],
                        chunkData[11],
                        chunkData[12]))
                {
                    throw new InvalidDataException("The native render PNG IHDR fields are invalid.");
                }

                sawHeader = true;
            }

            if (chunkType == "PLTE")
            {
                if (sawImageData
                    || chunkLength < 3
                    || chunkLength > 768
                    || chunkLength % 3 != 0)
                {
                    throw new InvalidDataException("The native render PNG palette chunk is invalid.");
                }

                sawPalette = true;
            }

            if (chunkType == "IDAT")
            {
                if (chunkLength == 0)
                {
                    throw new InvalidDataException("The native render PNG IDAT chunk is empty.");
                }

                sawImageData = true;
                imageData.Write(chunkData);
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

        if (!sawHeader || !sawImageData || !sawEnd)
        {
            throw new InvalidDataException("The native render PNG is missing coherent image data.");
        }

        if (colorType == 3 && !sawPalette)
        {
            throw new InvalidDataException("The native render PNG palette is missing.");
        }

        ValidatePngImageData(imageData.ToArray(), width, height, bitDepth, colorType);

        return new ArtifactMetadata(width, height, null);
    }

    private static bool IsValidPngIhdr(
        byte bitDepth,
        byte colorType,
        byte compressionMethod,
        byte filterMethod,
        byte interlaceMethod)
    {
        if (compressionMethod != 0 || filterMethod != 0 || interlaceMethod != 0)
        {
            return false;
        }

        return colorType switch
        {
            0 => bitDepth is 1 or 2 or 4 or 8 or 16,
            2 => bitDepth is 8 or 16,
            3 => bitDepth is 1 or 2 or 4 or 8,
            4 => bitDepth is 8 or 16,
            6 => bitDepth is 8 or 16,
            _ => false
        };
    }

    private static void ValidatePngImageData(
        byte[] compressedBytes,
        long width,
        long height,
        byte bitDepth,
        byte colorType)
    {
        var channelCount = colorType switch
        {
            0 or 3 => 1,
            2 => 3,
            4 => 2,
            6 => 4,
            _ => throw new InvalidDataException("The native render PNG color type is invalid.")
        };
        var bitsPerPixel = checked(channelCount * bitDepth);
        var rowBytes = checked((width * bitsPerPixel + 7) / 8);
        var scanlineLength = checked((int)(rowBytes + 1));
        var decodedLength = checked(height * (rowBytes + 1));
        if (decodedLength <= 0 || decodedLength > MaxArtifactBytes)
        {
            throw new InvalidDataException("The native render PNG decoded image is too large.");
        }

        try
        {
            using var compressed = new MemoryStream(compressedBytes, writable: false);
            using var zlib = new ZLibStream(compressed, CompressionMode.Decompress);
            var scanline = new byte[scanlineLength];
            for (var row = 0L; row < height; row++)
            {
                ReadPngExactly(zlib, scanline);
                if (scanline[0] > 4)
                {
                    throw new InvalidDataException("The native render PNG scanline filter is invalid.");
                }
            }

            if (zlib.ReadByte() != -1)
            {
                throw new InvalidDataException("The native render PNG has trailing scanline data.");
            }
        }
        catch (InvalidDataException exception)
        {
            throw new InvalidDataException(
                "The native render PNG IDAT stream cannot be decoded.",
                exception);
        }
        catch (IOException exception)
        {
            throw new InvalidDataException(
                "The native render PNG IDAT stream cannot be decoded.",
                exception);
        }
    }

    private static void ReadPngExactly(Stream stream, Span<byte> buffer)
    {
        while (!buffer.IsEmpty)
        {
            var read = stream.Read(buffer);
            if (read <= 0)
            {
                throw new InvalidDataException("The native render PNG scanlines are truncated.");
            }

            buffer = buffer[read..];
        }
    }

    private static uint ComputePngCrc(ReadOnlySpan<byte> chunkType, ReadOnlySpan<byte> chunkData)
    {
        var crc = 0xFFFFFFFFu;
        foreach (var value in chunkType)
        {
            crc = UpdatePngCrc(crc, value);
        }

        foreach (var value in chunkData)
        {
            crc = UpdatePngCrc(crc, value);
        }

        return ~crc;
    }

    private static uint UpdatePngCrc(uint crc, byte value)
    {
        crc ^= value;
        for (var bit = 0; bit < 8; bit++)
        {
            crc = (crc & 1) != 0
                ? (crc >> 1) ^ 0xEDB88320u
                : crc >> 1;
        }

        return crc;
    }

    private static ArtifactMetadata ValidatePdf(byte[] bytes)
    {
        if (bytes.Length < 16
            || !Encoding.ASCII.GetString(bytes, 0, 5).Equals("%PDF-", StringComparison.Ordinal))
        {
            throw new InvalidDataException("The native render PDF header is invalid.");
        }

        var text = Encoding.Latin1.GetString(bytes);
        var eofIndex = text.LastIndexOf("%%EOF", StringComparison.Ordinal);
        if (eofIndex < 0
            || text[(eofIndex + "%%EOF".Length)..].Any(character => !char.IsWhiteSpace(character)))
        {
            throw new InvalidDataException("The native render PDF is missing its EOF trailer.");
        }

        var startxrefIndex = text.LastIndexOf("startxref", eofIndex, StringComparison.Ordinal);
        if (startxrefIndex < 0)
        {
            throw new InvalidDataException("The native render PDF is missing startxref.");
        }

        var numberStart = startxrefIndex + "startxref".Length;
        while (numberStart < text.Length && char.IsWhiteSpace(text[numberStart]))
        {
            numberStart++;
        }

        var numberEnd = numberStart;
        while (numberEnd < text.Length && char.IsDigit(text[numberEnd]))
        {
            numberEnd++;
        }

        if (numberStart == numberEnd
            || !long.TryParse(text[numberStart..numberEnd], out var xrefOffset)
            || xrefOffset < 0
            || xrefOffset > int.MaxValue
            || xrefOffset >= text.Length
            || !text.AsSpan((int)xrefOffset).StartsWith("xref", StringComparison.Ordinal))
        {
            throw new InvalidDataException("The native render PDF xref offset is invalid.");
        }

        var objects = ParsePdfObjects(text);
        var trailer = ParsePdfTrailer(text, (int)xrefOffset);
        var fileSize = ReadPdfInteger(trailer, "/Size");
        if (fileSize <= 0 || fileSize > int.MaxValue)
        {
            throw new InvalidDataException("The native render PDF trailer size is invalid.");
        }

        var xrefEntries = ParsePdfXref(text, (int)xrefOffset, (int)fileSize);
        var rootId = ReadPdfReference(trailer, "/Root");
        var catalog = GetPdfObject(objects, rootId, "catalog");
        RequirePdfType(catalog, "Catalog", "catalog");
        var pagesId = ReadPdfReference(catalog, "/Pages");
        var pages = GetPdfObject(objects, pagesId, "page tree");
        RequirePdfType(pages, "Pages", "page tree");
        if (ReadPdfInteger(pages, "/Count") != 1)
        {
            throw new InvalidDataException("The native render PDF must contain exactly one page.");
        }

        var pageIds = ReadPdfReferencesArray(pages, "/Kids");
        if (pageIds.Count != 1)
        {
            throw new InvalidDataException("The native render PDF page tree must contain one page.");
        }

        var page = GetPdfObject(objects, pageIds[0], "page");
        RequirePdfType(page, "Page", "page");
        if (ReadPdfReference(page, "/Parent") != pagesId
            || !Regex.IsMatch(page, @"/MediaBox\s*\[[^\]]+\]", RegexOptions.CultureInvariant))
        {
            throw new InvalidDataException("The native render PDF page tree is incoherent.");
        }

        foreach (var objectId in new[] { rootId, pagesId, pageIds[0] })
        {
            if (!xrefEntries.TryGetValue(objectId, out var entry)
                || entry.Kind != 'n'
                || !IsPdfObjectDeclarationAt(text, entry.Offset, objectId))
            {
                throw new InvalidDataException("The native render PDF xref does not bind its page tree.");
            }
        }

        return new ArtifactMetadata(null, null, 1);
    }

    private static Dictionary<int, string> ParsePdfObjects(string text)
    {
        var objects = new Dictionary<int, string>();
        var matches = Regex.Matches(
            text,
            @"(?ms)(?<!\d)(?<id>\d+)\s+\d+\s+obj\s*(?<body>.*?)\s*endobj",
            RegexOptions.CultureInvariant);
        foreach (Match match in matches)
        {
            var id = int.Parse(match.Groups["id"].Value, System.Globalization.CultureInfo.InvariantCulture);
            if (!objects.TryAdd(id, match.Groups["body"].Value))
            {
                throw new InvalidDataException("The native render PDF contains duplicate object numbers.");
            }
        }

        return objects;
    }

    private static string ParsePdfTrailer(string text, int xrefOffset)
    {
        var matches = Regex.Matches(
            text,
            @"(?s)trailer\s*<<(?<dictionary>.*?)>>",
            RegexOptions.CultureInvariant);
        var trailer = matches
            .Cast<Match>()
            .LastOrDefault(match => match.Index > xrefOffset);
        return trailer?.Groups["dictionary"].Value
            ?? throw new InvalidDataException("The native render PDF trailer is missing.");
    }

    private static Dictionary<int, PdfXrefEntry> ParsePdfXref(
        string text,
        int xrefOffset,
        int expectedSize)
    {
        var entries = new Dictionary<int, PdfXrefEntry>();
        var cursor = xrefOffset;
        if (!string.Equals(ReadPdfLine(text, ref cursor), "xref", StringComparison.Ordinal))
        {
            throw new InvalidDataException("The native render PDF xref table is invalid.");
        }

        while (true)
        {
            var subsection = ReadPdfLine(text, ref cursor);
            if (subsection is null || string.Equals(subsection, "trailer", StringComparison.Ordinal))
            {
                break;
            }

            var parts = subsection.Split(' ', StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length != 2
                || !int.TryParse(parts[0], out var firstId)
                || !int.TryParse(parts[1], out var count)
                || firstId < 0
                || count <= 0
                || firstId > expectedSize - count)
            {
                throw new InvalidDataException("The native render PDF xref subsection is invalid.");
            }

            for (var id = firstId; id < firstId + count; id++)
            {
                var entryLine = ReadPdfLine(text, ref cursor);
                if (entryLine is null)
                {
                    throw new InvalidDataException("The native render PDF xref entries are incomplete.");
                }

                var entryParts = entryLine.Split(' ', StringSplitOptions.RemoveEmptyEntries);
                if (entryParts.Length != 3
                    || !long.TryParse(entryParts[0], out var objectOffset)
                    || !int.TryParse(entryParts[1], out var generation)
                    || entryParts[2] is not ("n" or "f"))
                {
                    throw new InvalidDataException("The native render PDF xref entry is invalid.");
                }

                if (!entries.TryAdd(id, new PdfXrefEntry(objectOffset, generation, entryParts[2][0])))
                {
                    throw new InvalidDataException("The native render PDF xref repeats an object number.");
                }
            }
        }

        if (!entries.TryGetValue(0, out var freeEntry)
            || freeEntry.Kind != 'f'
            || entries.Count != expectedSize)
        {
            throw new InvalidDataException("The native render PDF xref table is incomplete.");
        }

        return entries;
    }

    private static string? ReadPdfLine(string text, ref int cursor)
    {
        if (cursor >= text.Length)
        {
            return null;
        }

        var lineStart = cursor;
        var end = text.IndexOf('\n', cursor);
        if (end < 0)
        {
            end = text.Length;
            cursor = text.Length;
        }
        else
        {
            cursor = end + 1;
        }

        return text[lineStart..end].TrimEnd('\r');
    }

    private static int ReadPdfInteger(string dictionary, string name)
    {
        var match = Regex.Match(
            dictionary,
            $@"{Regex.Escape(name)}\s+(?<value>\d+)\b",
            RegexOptions.CultureInvariant);
        return match.Success && int.TryParse(match.Groups["value"].Value, out var value)
            ? value
            : throw new InvalidDataException($"The native render PDF dictionary is missing {name}.");
    }

    private static int ReadPdfReference(string dictionary, string name)
    {
        var match = Regex.Match(
            dictionary,
            $@"{Regex.Escape(name)}\s+(?<id>\d+)\s+\d+\s+R\b",
            RegexOptions.CultureInvariant);
        return match.Success && int.TryParse(match.Groups["id"].Value, out var value)
            ? value
            : throw new InvalidDataException($"The native render PDF dictionary is missing {name}.");
    }

    private static IReadOnlyList<int> ReadPdfReferencesArray(string dictionary, string name)
    {
        var match = Regex.Match(
            dictionary,
            $@"{Regex.Escape(name)}\s*\[(?<items>[^\]]*)\]",
            RegexOptions.CultureInvariant);
        if (!match.Success)
        {
            throw new InvalidDataException($"The native render PDF dictionary is missing {name}.");
        }

        return Regex.Matches(
                match.Groups["items"].Value,
                @"(?<id>\d+)\s+\d+\s+R\b",
                RegexOptions.CultureInvariant)
            .Cast<Match>()
            .Select(item => int.Parse(
                item.Groups["id"].Value,
                System.Globalization.CultureInfo.InvariantCulture))
            .ToArray();
    }

    private static string GetPdfObject(
        IReadOnlyDictionary<int, string> objects,
        int id,
        string description) =>
        objects.TryGetValue(id, out var body)
            ? body
            : throw new InvalidDataException($"The native render PDF {description} object is missing.");

    private static void RequirePdfType(string dictionary, string expected, string description)
    {
        var match = Regex.Match(
            dictionary,
            @"/Type\s*/(?<type>[A-Za-z]+)\b",
            RegexOptions.CultureInvariant);
        if (!match.Success || !string.Equals(match.Groups["type"].Value, expected, StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                $"The native render PDF {description} object has an invalid type.");
        }
    }

    private static bool IsPdfObjectDeclarationAt(string text, long offset, int id)
    {
        if (offset < 0 || offset > int.MaxValue || offset >= text.Length)
        {
            return false;
        }

        var regex = new Regex(
            $@"\G{id}\s+\d+\s+obj\b",
            RegexOptions.CultureInvariant,
            TimeSpan.FromSeconds(1));
        return regex.Match(text, (int)offset).Success;
    }

    private readonly record struct PdfXrefEntry(long Offset, int Generation, char Kind);

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

    private static void DeleteOwnedFinalIfUnchanged(
        NativeRenderArtifactReservation reservation,
        string expectedHash)
    {
        if (!reservation.FinalCreatedByReservation || !File.Exists(reservation.FinalPath))
        {
            return;
        }

        try
        {
            var finalBytes = File.ReadAllBytes(reservation.FinalPath);
            if (string.Equals(Hash(finalBytes), expectedHash, StringComparison.Ordinal))
            {
                File.Delete(reservation.FinalPath);
            }
        }
        catch (IOException)
        {
            // Leave an artifact we cannot prove is still owned by this reservation.
        }
        catch (UnauthorizedAccessException)
        {
            // Leave an artifact we cannot prove is still owned by this reservation.
        }
    }

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
    private readonly Action<string> _deleteClaim;
    private bool _disposed;

    internal NativeRenderArtifactReservation(
        string requestDirectory,
        string temporaryPath,
        string finalPath,
        string relativePath,
        string claimPath,
        FileStream claim,
        Action<string> deleteClaim,
        string artifactKind)
    {
        RequestDirectory = requestDirectory;
        TemporaryPath = temporaryPath;
        FinalPath = finalPath;
        RelativePath = relativePath;
        ClaimPath = claimPath;
        _claim = claim;
        _deleteClaim = deleteClaim ?? throw new ArgumentNullException(nameof(deleteClaim));
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

    internal bool FinalCreatedByReservation { get; private set; }

    internal void MarkFinalCreated() => FinalCreatedByReservation = true;

    internal void MarkPublished() => IsPublished = true;

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        TryDelete(TemporaryPath, deleteWhenPublished: false);
        try
        {
            _claim?.Dispose();
        }
        catch (IOException)
        {
            // Cleanup must not mask the operation result. Leave the claim marker.
        }
        catch (UnauthorizedAccessException)
        {
            // Cleanup must not mask the operation result. Leave the claim marker.
        }
        finally
        {
            _claim = null;
            TryDelete(ClaimPath, deleteWhenPublished: true);
            _disposed = true;
        }
    }

    private void TryDelete(string path, bool deleteWhenPublished)
    {
        if (deleteWhenPublished || !IsPublished)
        {
            try
            {
                if (File.Exists(path))
                {
                    if (string.Equals(path, ClaimPath, StringComparison.Ordinal))
                    {
                        _deleteClaim(path);
                    }
                    else
                    {
                        File.Delete(path);
                    }
                }
            }
            catch (IOException)
            {
                // A stale marker/temp is safer than a cleanup exception escaping.
            }
            catch (UnauthorizedAccessException)
            {
                // A stale marker/temp is safer than a cleanup exception escaping.
            }
        }
    }
}
