using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.PlottingServices;
using CadAgent.AutoCAD2027.Ipc;
using AcadApplication = Autodesk.AutoCAD.ApplicationServices.Application;

namespace CadAgent.AutoCAD2027.Drawing;

public static class AutoCadNativeRenderReader
{
    private const string PdfDevice = "AutoCAD PDF (General Documentation).pc3";
    private const string PngDevice = "PublishToWeb PNG.pc3";
    private const string A4MediaName = "ISO_A4_(210.00_x_297.00_MM)";
    private const double A4WidthMillimeters = 210;
    private const double A4HeightMillimeters = 297;

    public static NativeRenderEvidenceSnapshot Capture(
        Document document,
        NativeRenderRequest request,
        string ipcDirectory,
        DateTimeOffset captureTimestamp)
    {
        ArgumentNullException.ThrowIfNull(document);
        ArgumentNullException.ThrowIfNull(request);
        NativeRenderPolicy.EnsureSupported(request);

        var database = document.Database
            ?? throw new InvalidOperationException("The active AutoCAD document has no database.");
        var activePath = NormalizePath(database.Filename);
        var requestedPath = NormalizePath(request.DrawingFullPath);
        if (!StringComparer.OrdinalIgnoreCase.Equals(activePath, requestedPath))
        {
            throw new InvalidDataException(
                "The requested drawing_full_path does not match the active document full path.");
        }

        var drawingHashBefore = HashFile(request.DrawingFullPath);
        if (!string.Equals(drawingHashBefore, request.DrawingSha256, StringComparison.Ordinal))
        {
            throw new InvalidDataException("The drawing hash does not match the request.");
        }

        var dbmodBefore = ReadDbMod();
        if (dbmodBefore < 0)
        {
            throw new InvalidDataException("DBMOD must be non-negative before native render capture.");
        }

        var boundary = new NativeRenderArtifactBoundary();
        using var reservation = boundary.Reserve(ipcDirectory, request.RequestId, request.ArtifactKind);
        var backgroundPlotBefore = AcadApplication.GetSystemVariable("BACKGROUNDPLOT");
        Exception? operationFailure = null;
        var sessionStateRestored = false;

        try
        {
            AcadApplication.SetSystemVariable("BACKGROUNDPLOT", 0);
            PlotLayout(document, request, reservation.TemporaryPath);
        }
        catch (Exception exception)
        {
            operationFailure = exception;
        }
        finally
        {
            try
            {
                AcadApplication.SetSystemVariable("BACKGROUNDPLOT", backgroundPlotBefore);
                sessionStateRestored = Equals(
                    AcadApplication.GetSystemVariable("BACKGROUNDPLOT"),
                    backgroundPlotBefore);
            }
            catch (Exception exception)
            {
                operationFailure ??= new InvalidOperationException(
                    "AutoCAD session state could not be restored after native render capture.",
                    exception);
            }
        }

        if (operationFailure is not null)
        {
            throw operationFailure;
        }

        var dbmodAfter = ReadDbMod();
        var drawingHashAfter = HashFile(request.DrawingFullPath);
        NativeRenderPolicy.EnsureReadOnly(
            dbmodBefore,
            dbmodAfter,
            drawingHashBefore,
            drawingHashAfter,
            sessionStateRestored);

        var artifact = boundary.Publish(reservation);
        return new NativeRenderEvidenceSnapshot(
            request.RequestId,
            request.RunId,
            request.DrawingSha256,
            request.LatestMutationSha256,
            request.VisualRunManifestSha256,
            request.Layout,
            request.ArtifactKind,
            request.RenderOptions,
            artifact,
            captureTimestamp.ToUniversalTime(),
            dbmodBefore,
            dbmodAfter,
            Array.Empty<string>());
    }

    private static void PlotLayout(
        Document document,
        NativeRenderRequest request,
        string outputPath)
    {
        if (PlotFactory.ProcessPlotState != ProcessPlotState.NotPlotting)
        {
            throw new InvalidOperationException("NATIVE_RENDER_PLOT_ALREADY_ACTIVE");
        }

        var database = document.Database
            ?? throw new InvalidOperationException("The active AutoCAD document has no database.");
        ObjectId layoutId;
        PlotSettings plotSettings;
        using (var transaction = database.TransactionManager.StartOpenCloseTransaction())
        {
            var layouts = (DBDictionary)transaction.GetObject(
                database.LayoutDictionaryId,
                OpenMode.ForRead);
            var matches = new List<(ObjectId Id, Layout Layout)>();
            foreach (DBDictionaryEntry entry in layouts)
            {
                var layout = (Layout)transaction.GetObject(entry.Value, OpenMode.ForRead);
                if (!layout.ModelType
                    && string.Equals(layout.LayoutName, request.Layout.Name, StringComparison.Ordinal))
                {
                    matches.Add((entry.Value, layout));
                }
            }

            if (matches.Count != 1)
            {
                throw new InvalidDataException("The requested paper-space layout was not found uniquely.");
            }

            layoutId = matches[0].Id;
            plotSettings = new PlotSettings(matches[0].Layout.ModelType);
            plotSettings.CopyFrom(matches[0].Layout);
            ConfigurePlotSettings(plotSettings, request);
        }

        using (plotSettings)
        {
            var plotInfo = new PlotInfo
            {
                Layout = layoutId,
                OverrideSettings = plotSettings
            };
            var plotInfoValidator = new PlotInfoValidator();
            plotInfoValidator.Validate(plotInfo);
            ExecutePlot(document, plotInfo, outputPath);
        }
    }

    private static void ConfigurePlotSettings(
        PlotSettings plotSettings,
        NativeRenderRequest request)
    {
        var validator = PlotSettingsValidator.Current;
        var device = request.ArtifactKind == "PNG" ? PngDevice : PdfDevice;
        validator.SetPlotConfigurationName(plotSettings, device, null);
        validator.RefreshLists(plotSettings);

        var mediaNames = validator.GetCanonicalMediaNameList(plotSettings)
            .Cast<string>()
            .Where(name => !string.IsNullOrWhiteSpace(name))
            .Distinct(StringComparer.Ordinal)
            .ToArray();

        var approvedMediaNames = new List<string>();
        foreach (var mediaName in mediaNames)
        {
            try
            {
                validator.SetCanonicalMediaName(plotSettings, mediaName);
            }
            catch (Autodesk.AutoCAD.Runtime.Exception)
            {
                continue;
            }

            var paperSize = plotSettings.PlotPaperSize;
            var isApproved = request.ArtifactKind == "PNG"
                ? plotSettings.PlotPaperUnits == PlotPaperUnit.Pixels
                    && ((
                        IsCloseTo(paperSize.X, NativeRenderPolicy.ApprovedPngWidth)
                        && IsCloseTo(paperSize.Y, NativeRenderPolicy.ApprovedPngHeight))
                        || (
                            IsCloseTo(paperSize.X, NativeRenderPolicy.ApprovedPngLandscapeWidth)
                            && IsCloseTo(paperSize.Y, NativeRenderPolicy.ApprovedPngLandscapeHeight)))
                : string.Equals(mediaName, A4MediaName, StringComparison.Ordinal)
                    && plotSettings.PlotPaperUnits == PlotPaperUnit.Millimeters
                    && IsCloseTo(paperSize.X, A4WidthMillimeters)
                    && IsCloseTo(paperSize.Y, A4HeightMillimeters);
            if (isApproved)
            {
                approvedMediaNames.Add(mediaName);
            }
        }

        if (approvedMediaNames.Count != 1)
        {
            throw new InvalidDataException(
                request.ArtifactKind == "PNG"
                    ? "The approved PNG device does not expose exactly one approved A4 pixel media."
                    : "The approved PDF device does not expose exactly one approved A4 media.");
        }

        validator.SetCanonicalMediaName(plotSettings, approvedMediaNames[0]);
        validator.SetPlotType(plotSettings, Autodesk.AutoCAD.DatabaseServices.PlotType.Layout);
        validator.SetUseStandardScale(plotSettings, true);
        validator.SetStdScaleType(plotSettings, StdScaleType.ScaleToFit);
        validator.SetCurrentStyleSheet(plotSettings, request.RenderOptions.PlotStyle);
    }

    private static bool IsCloseTo(double actual, double expected) =>
        Math.Abs(actual - expected) < 0.001;

    private static void ExecutePlot(
        Document document,
        PlotInfo plotInfo,
        string outputPath)
    {
        using var plotEngine = PlotFactory.CreatePublishEngine();
        using var progress = new PlotProgressDialog(false, 1, true);
        plotEngine.BeginPlot(progress, null);
        plotEngine.BeginDocument(plotInfo, document.Name, null, 1, true, outputPath);
        using (var pageInfo = new PlotPageInfo())
        {
            plotEngine.BeginPage(pageInfo, plotInfo, true, null);
            plotEngine.BeginGenerateGraphics(null);
            plotEngine.EndGenerateGraphics(null);
            plotEngine.EndPage(null);
        }

        plotEngine.EndDocument(null);
        plotEngine.EndPlot(null);
        progress.Destroy();
    }

    private static int ReadDbMod() =>
        Convert.ToInt32(
            AcadApplication.GetSystemVariable("DBMOD"),
            CultureInfo.InvariantCulture);

    private static string HashFile(string path)
    {
        using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }

    private static string NormalizePath(string path)
    {
        if (!ContractValidator.TryNormalizeWindowsAbsolutePath(path, out var normalized))
        {
            throw new InvalidDataException("The drawing path is not a valid absolute Windows path.");
        }

        return normalized;
    }
}
