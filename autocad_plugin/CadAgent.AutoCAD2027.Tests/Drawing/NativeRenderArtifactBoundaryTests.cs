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

    [Fact]
    public void PublishReadsPngMetadataAndPublishesTheFinalSha256()
    {
        var root = CreateRoot();
        try
        {
            var boundary = new NativeRenderArtifactBoundary();
            using var reservation = boundary.Reserve(root, "render-request-001", "PNG");
            var bytes = MinimalPng(2480, 3508);
            File.WriteAllBytes(reservation.TemporaryPath, bytes);

            var artifact = boundary.Publish(reservation);

            Assert.True(reservation.IsPublished);
            Assert.Equal("native-render/render-request-001/artifact.png", artifact.RelativePath);
            Assert.Equal(Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(), artifact.Sha256);
            Assert.Equal(2480, artifact.Width);
            Assert.Equal(3508, artifact.Height);
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

    private static byte[] MinimalPdf() =>
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
