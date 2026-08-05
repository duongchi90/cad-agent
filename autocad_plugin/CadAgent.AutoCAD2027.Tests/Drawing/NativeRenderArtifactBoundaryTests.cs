using System.Security.Cryptography;
using System.Text;
using CadAgent.AutoCAD2027.Drawing;
using Xunit;

namespace CadAgent.AutoCAD2027.Tests.Drawing;

public sealed class NativeRenderArtifactBoundaryTests
{
    [Fact]
    public void ReserveUsesTheRequestOwnedFinalPathAndExpectedSuffix()
    {
        var root = CreateRoot();
        try
        {
            using var reservation = new NativeRenderArtifactBoundary().Reserve(
                root,
                "render-request-001",
                "PNG");

            Assert.Equal(
                Path.Combine(root, "native-render", "render-request-001"),
                reservation.RequestDirectory);
            Assert.Equal(
                "native-render/render-request-001/artifact.png",
                reservation.RelativePath);
            Assert.EndsWith(".png", reservation.TemporaryPath, StringComparison.Ordinal);
            Assert.EndsWith("artifact.png", reservation.FinalPath, StringComparison.Ordinal);
        }
        finally
        {
            DeleteRoot(root);
        }
    }

    [Theory]
    [InlineData("")]
    [InlineData("../x")]
    [InlineData("x/y")]
    [InlineData("x\\y")]
    [InlineData("C:x")]
    [InlineData("C:\\x")]
    [InlineData("bad\0id")]
    public void ReserveRejectsUnsafeRequestIds(string requestId)
    {
        var root = CreateRoot();
        try
        {
            Assert.Throws<ArgumentException>(() => new NativeRenderArtifactBoundary().Reserve(
                root,
                requestId,
                "PNG"));
        }
        finally
        {
            DeleteRoot(root);
        }
    }

    [Fact]
    public void ReserveRejectsAnExistingRequestDirectory()
    {
        var root = CreateRoot();
        var requestDirectory = Path.Combine(root, "native-render", "render-request-001");
        Directory.CreateDirectory(requestDirectory);
        try
        {
            Assert.Throws<IOException>(() => new NativeRenderArtifactBoundary().Reserve(
                root,
                "render-request-001",
                "PDF"));
        }
        finally
        {
            DeleteRoot(root);
        }
    }

    [Fact]
    public async Task ReserveAllowsOnlyOneConcurrentRequestClaim()
    {
        var root = CreateRoot();
        try
        {
            var boundary = new NativeRenderArtifactBoundary();
            var attempts = Enumerable.Range(0, 2)
                .Select(_ => Task.Run(() => TryReserve(boundary, root)))
                .ToArray();
            var reservations = await Task.WhenAll(attempts);

            Assert.Single(reservations.OfType<NativeRenderArtifactReservation>());
            foreach (var reservation in reservations.OfType<NativeRenderArtifactReservation>())
            {
                reservation.Dispose();
            }
        }
        finally
        {
            DeleteRoot(root);
        }
    }

    [Theory]
    [InlineData(2480, 3508)]
    [InlineData(3508, 2480)]
    public void PublishReadsApprovedPngMetadataAndPublishesTheFinalSha256(
        int width,
        int height)
    {
        var root = CreateRoot();
        try
        {
            var boundary = new NativeRenderArtifactBoundary();
            using var reservation = boundary.Reserve(root, "render-request-001", "PNG");
            var bytes = MinimalPng(width, height);
            File.WriteAllBytes(reservation.TemporaryPath, bytes);

            var artifact = boundary.Publish(reservation);

            Assert.True(reservation.IsPublished);
            Assert.Equal("native-render/render-request-001/artifact.png", artifact.RelativePath);
            Assert.Equal(Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(), artifact.Sha256);
            Assert.Equal(width, artifact.Width);
            Assert.Equal(height, artifact.Height);
            Assert.Null(artifact.PageCount);
            Assert.True(File.Exists(reservation.FinalPath));
            Assert.False(File.Exists(reservation.TemporaryPath));
        }
        finally
        {
            DeleteRoot(root);
        }
    }

    [Fact]
    public void PublishReadsOnePagePdfAndRejectsOverwrite()
    {
        var root = CreateRoot();
        try
        {
            var boundary = new NativeRenderArtifactBoundary();
            using var reservation = boundary.Reserve(root, "render-request-001", "PDF");
            var bytes = MinimalPdf();
            File.WriteAllBytes(reservation.TemporaryPath, bytes);

            var artifact = boundary.Publish(reservation);

            Assert.Equal("native-render/render-request-001/artifact.pdf", artifact.RelativePath);
            Assert.Equal(1, artifact.PageCount);
            Assert.Null(artifact.Width);
            Assert.Null(artifact.Height);
            Assert.Throws<IOException>(() =>
            {
                using var stream = new FileStream(reservation.FinalPath, FileMode.CreateNew);
            });
        }
        finally
        {
            DeleteRoot(root);
        }
    }

    [Fact]
    public void PublishLeavesACompetingFinalArtifactUntouchedWhenMoveLosesTheRace()
    {
        var root = CreateRoot();
        try
        {
            var competingBytes = Encoding.ASCII.GetBytes("owned by another request");
            var boundary = new NativeRenderArtifactBoundary((source, destination) =>
            {
                File.WriteAllBytes(destination, competingBytes);
                throw new IOException("simulated final-path race");
            });
            using var reservation = boundary.Reserve(root, "render-request-001", "PDF");
            File.WriteAllBytes(reservation.TemporaryPath, MinimalPdf());

            Assert.Throws<IOException>(() => boundary.Publish(reservation));
            Assert.Equal(competingBytes, File.ReadAllBytes(reservation.FinalPath));
            Assert.False(reservation.IsPublished);
        }
        finally
        {
            DeleteRoot(root);
        }
    }

    [Fact]
    public void PublishRejectsPngThatDoesNotMatchTheApprovedA4ThreeHundredDpiPixels()
    {
        var root = CreateRoot();
        try
        {
            var boundary = new NativeRenderArtifactBoundary();
            using var reservation = boundary.Reserve(root, "render-request-001", "PNG");
            File.WriteAllBytes(reservation.TemporaryPath, MinimalPng(1600, 1200));

            Assert.Throws<InvalidDataException>(() => boundary.Publish(reservation));
            Assert.False(File.Exists(reservation.FinalPath));
        }
        finally
        {
            DeleteRoot(root);
        }
    }

    [Fact]
    public void PublishRejectsPdfWithoutACoherentCatalogPageTreeAndXref()
    {
        var root = CreateRoot();
        try
        {
            var boundary = new NativeRenderArtifactBoundary();
            using var reservation = boundary.Reserve(root, "render-request-001", "PDF");
            File.WriteAllBytes(reservation.TemporaryPath, MinimalPdfPlaceholder());

            Assert.Throws<InvalidDataException>(() => boundary.Publish(reservation));
            Assert.False(File.Exists(reservation.FinalPath));
        }
        finally
        {
            DeleteRoot(root);
        }
    }

    [Fact]
    public void FailedValidationLeavesNoFinalArtifact()
    {
        var root = CreateRoot();
        try
        {
            var boundary = new NativeRenderArtifactBoundary();
            using var reservation = boundary.Reserve(root, "render-request-001", "PNG");
            File.WriteAllBytes(reservation.TemporaryPath, Encoding.ASCII.GetBytes("not png"));

            Assert.Throws<InvalidDataException>(() => boundary.Publish(reservation));
            Assert.False(File.Exists(reservation.FinalPath));
            Assert.False(reservation.IsPublished);
        }
        finally
        {
            DeleteRoot(root);
        }
    }

    private static NativeRenderArtifactReservation? TryReserve(
        NativeRenderArtifactBoundary boundary,
        string root)
    {
        try
        {
            return boundary.Reserve(root, "render-request-001", "PNG");
        }
        catch (IOException)
        {
            return null;
        }
    }

    private static byte[] MinimalPng(int width, int height)
    {
        var bytes = new byte[45];
        new byte[] { 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A }
            .CopyTo(bytes, 0);
        bytes[11] = 13;
        Encoding.ASCII.GetBytes("IHDR").CopyTo(bytes, 12);
        WriteBigEndian(bytes, 16, width);
        WriteBigEndian(bytes, 20, height);
        bytes[24] = 8;
        bytes[25] = 2;
        Encoding.ASCII.GetBytes("IEND").CopyTo(bytes, 37);
        return bytes;
    }

    private static byte[] MinimalPdf()
    {
        var objects = new[]
        {
            "<< /Type /Catalog /Pages 2 0 R >>",
            "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << >> /Contents 4 0 R >>",
            "<< /Length 0 >>\nstream\nendstream"
        };
        var builder = new StringBuilder("%PDF-1.4\n");
        var offsets = new List<int> { 0 };
        for (var index = 0; index < objects.Length; index++)
        {
            offsets.Add(builder.Length);
            builder.Append(index + 1)
                .Append(" 0 obj\n")
                .Append(objects[index])
                .Append("\nendobj\n");
        }

        var xrefOffset = builder.Length;
        builder.Append("xref\n0 5\n0000000000 65535 f \n");
        for (var index = 1; index < offsets.Count; index++)
        {
            builder.Append(offsets[index].ToString("D10"))
                .Append(" 00000 n \n");
        }

        builder.Append("trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n")
            .Append(xrefOffset)
            .Append("\n%%EOF\n");
        return Encoding.ASCII.GetBytes(builder.ToString());
    }

    private static byte[] MinimalPdfPlaceholder() =>
        Encoding.ASCII.GetBytes(
            "%PDF-1.4\n1 0 obj\n<< /Type /Page >>\nendobj\n%%EOF\n");

    private static void WriteBigEndian(byte[] bytes, int offset, int value)
    {
        bytes[offset] = (byte)(value >> 24);
        bytes[offset + 1] = (byte)(value >> 16);
        bytes[offset + 2] = (byte)(value >> 8);
        bytes[offset + 3] = (byte)value;
    }

    private static string CreateRoot()
    {
        var root = Path.Combine(Path.GetTempPath(), "cad-agent-s2c-tests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        return root;
    }

    private static void DeleteRoot(string root)
    {
        if (Directory.Exists(root))
        {
            Directory.Delete(root, recursive: true);
        }
    }
}
