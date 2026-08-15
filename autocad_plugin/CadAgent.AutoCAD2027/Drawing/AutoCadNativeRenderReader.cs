using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
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

    private sealed record CameraWindow(
        IReadOnlyList<double>? RequestedWcsBbox,
        IReadOnlyList<double>? ObservedWcsBbox,
        IReadOnlyList<double> ViewCenter,
        double ViewWidth,
        double ViewHeight,
        Extents2d PlotWindow);

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
        CameraWindow? cameraWindow = null;

        try
        {
            AcadApplication.SetSystemVariable("BACKGROUNDPLOT", 0);
            cameraWindow = PlotLayout(document, request, reservation.TemporaryPath);
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
        var receipt = CreateCameraReceipt(
            request,
            cameraWindow,
            artifact,
            captureTimestamp.ToUniversalTime(),
            sessionStateRestored);
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
            Array.Empty<string>(),
            receipt);
    }

    private static CameraWindow? PlotLayout(
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
        CameraWindow? cameraWindow;
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
                throw new InvalidDataException(
                    $"{NativeRenderPolicy.LayoutNotFoundErrorCode}: "
                    + "The requested paper-space layout was not found uniquely.");
            }

            layoutId = matches[0].Id;
            cameraWindow = request.RenderOptions.Camera is null
                ? null
                : BuildCanonicalCameraWindow(
                    document,
                    transaction,
                    matches[0].Layout,
                    request.RenderOptions.Camera);
            plotSettings = new PlotSettings(matches[0].Layout.ModelType);
            plotSettings.CopyFrom(matches[0].Layout);
            ConfigurePlotSettings(plotSettings, request, cameraWindow);
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

        return cameraWindow;
    }

    private static CameraWindow BuildCanonicalCameraWindow(
        Document document,
        Transaction transaction,
        Layout layout,
        NativeRenderCamera camera)
    {
        NativeRenderPolicy.EnsureCameraSupported(camera);
        IReadOnlyList<double>? requested = null;
        double minX;
        double minY;
        double maxX;
        double maxY;

        if (camera.CaptureClass == "GLOBAL")
        {
            var extents = ReadLayoutExtents(transaction, layout);
            minX = extents.MinPoint.X;
            minY = extents.MinPoint.Y;
            maxX = extents.MaxPoint.X;
            maxY = extents.MaxPoint.Y;
        }
        else
        {
            var bbox = camera.WcsBbox
                ?? throw new InvalidDataException("WINDOW canonical camera requires wcs_bbox.");
            requested = bbox.ToArray();
            minX = bbox[0];
            minY = bbox[1];
            maxX = bbox[2];
            maxY = bbox[3];
        }

        var rawWidth = maxX - minX;
        var rawHeight = maxY - minY;
        if (!double.IsFinite(rawWidth)
            || !double.IsFinite(rawHeight)
            || rawWidth <= 0
            || rawHeight <= 0)
        {
            throw new InvalidDataException("The canonical camera extents are degenerate.");
        }

        var centerX = (minX + maxX) / 2.0;
        var centerY = (minY + maxY) / 2.0;
        var viewWidth = rawWidth * (1.0 + 2.0 * camera.MarginRatio);
        var viewHeight = rawHeight * (1.0 + 2.0 * camera.MarginRatio);
        if (!double.IsFinite(viewWidth)
            || !double.IsFinite(viewHeight)
            || viewWidth <= 0
            || viewHeight <= 0)
        {
            throw new InvalidDataException("The canonical camera margin produced invalid extents.");
        }

        var halfWidth = viewWidth / 2.0;
        var halfHeight = viewHeight / 2.0;
        var wcsMinX = centerX - halfWidth;
        var wcsMinY = centerY - halfHeight;
        var wcsMaxX = centerX + halfWidth;
        var wcsMaxY = centerY + halfHeight;
        var plotWindow = TransformWcsWindowToDcs(
            document,
            wcsMinX,
            wcsMinY,
            wcsMaxX,
            wcsMaxY);
        return new CameraWindow(
            requested,
            requested?.ToArray(),
            new[] { centerX, centerY },
            viewWidth,
            viewHeight,
            plotWindow);
    }

    private static Extents2d TransformWcsWindowToDcs(
        Document document,
        double minX,
        double minY,
        double maxX,
        double maxY)
    {
        using var view = document.Editor.GetCurrentView();
        var wcsToDcs = Matrix3d.PlaneToWorld(view.ViewDirection);
        wcsToDcs = Matrix3d.Displacement(view.Target - Point3d.Origin) * wcsToDcs;
        wcsToDcs = Matrix3d.Rotation(
            -view.ViewTwist,
            view.ViewDirection,
            view.Target) * wcsToDcs;
        wcsToDcs = wcsToDcs.Inverse();

        var corners = new[]
        {
            new Point3d(minX, minY, 0).TransformBy(wcsToDcs),
            new Point3d(minX, maxY, 0).TransformBy(wcsToDcs),
            new Point3d(maxX, minY, 0).TransformBy(wcsToDcs),
            new Point3d(maxX, maxY, 0).TransformBy(wcsToDcs)
        };
        var dcsMinX = corners.Min(point => point.X);
        var dcsMinY = corners.Min(point => point.Y);
        var dcsMaxX = corners.Max(point => point.X);
        var dcsMaxY = corners.Max(point => point.Y);
        return new Extents2d(
            new Point2d(dcsMinX, dcsMinY),
            new Point2d(dcsMaxX, dcsMaxY));
    }

    private static Extents3d ReadLayoutExtents(Transaction transaction, Layout layout)
    {
        var blockRecord = (BlockTableRecord)transaction.GetObject(
            layout.BlockTableRecordId,
            OpenMode.ForRead);
        Extents3d? combined = null;
        foreach (ObjectId objectId in blockRecord)
        {
            if (!objectId.IsValid || objectId.IsErased)
            {
                continue;
            }

            var entity = transaction.GetObject(objectId, OpenMode.ForRead, false) as Entity;
            if (entity is null)
            {
                continue;
            }

            try
            {
                var extents = entity.GeometricExtents;
                if (combined is null)
                {
                    combined = extents;
                }
                else
                {
                    var value = combined.Value;
                    value.AddExtents(extents);
                    combined = value;
                }
            }
            catch (Autodesk.AutoCAD.Runtime.Exception)
            {
                // Some non-graphical/empty entities do not expose extents. They cannot
                // define visual framing and are intentionally ignored.
            }
        }

        return combined
            ?? throw new InvalidDataException(
                "GLOBAL canonical camera could not derive non-degenerate layout extents.");
    }

    private static NativeRenderCameraReceipt? CreateCameraReceipt(
        NativeRenderRequest request,
        CameraWindow? cameraWindow,
        NativeRenderArtifact artifact,
        DateTimeOffset captureTimestamp,
        bool transientStateRestored)
    {
        var camera = request.RenderOptions.Camera;
        if (camera is null)
        {
            if (cameraWindow is not null)
            {
                throw new InvalidDataException("Legacy native render unexpectedly produced camera state.");
            }
            return null;
        }
        if (cameraWindow is null)
        {
            throw new InvalidDataException("Canonical camera render did not produce observed camera state.");
        }
        if (!artifact.Width.HasValue || !artifact.Height.HasValue)
        {
            throw new InvalidDataException("Canonical camera render requires PNG artifact dimensions.");
        }

        return new NativeRenderCameraReceipt(
            "visual-capture-receipt-1.0",
            $"receipt-{camera.CaptureId}",
            camera.CaptureId,
            request.RunId,
            camera.ScopeId,
            camera.RegionId,
            camera.ViewId,
            camera.SheetId,
            camera.LayoutId,
            camera.CandidateRevisionSha256,
            camera.CandidateStateSha256,
            request.LatestMutationSha256,
            camera.VisualCapturePlanSha256,
            camera.CaptureClass,
            camera.ZoomMode,
            cameraWindow.RequestedWcsBbox,
            cameraWindow.ObservedWcsBbox,
            cameraWindow.ViewCenter,
            cameraWindow.ViewWidth,
            cameraWindow.ViewHeight,
            camera.ViewDirection,
            camera.Ucs,
            camera.VisualStyle,
            artifact.Sha256,
            artifact.Width.Value,
            artifact.Height.Value,
            captureTimestamp,
            transientStateRestored);
    }

    private static void ConfigurePlotSettings(
        PlotSettings plotSettings,
        NativeRenderRequest request,
        CameraWindow? cameraWindow)
    {
        var validator = PlotSettingsValidator.Current;
        var device = request.ArtifactKind == "PNG" ? PngDevice : PdfDevice;
        string[] mediaNames;
        try
        {
            validator.SetPlotConfigurationName(plotSettings, device, null);
            validator.RefreshLists(plotSettings);
            mediaNames = validator.GetCanonicalMediaNameList(plotSettings)
                .Cast<string>()
                .Where(name => !string.IsNullOrWhiteSpace(name))
                .Distinct(StringComparer.Ordinal)
                .ToArray();
        }
        catch (Autodesk.AutoCAD.Runtime.Exception exception)
        {
            throw new InvalidDataException(
                $"{NativeRenderPolicy.DeviceUnavailableErrorCode}: "
                + $"The approved {request.ArtifactKind} device could not be configured.",
                exception);
        }

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
                $"{NativeRenderPolicy.MediaUnavailableErrorCode}: "
                + (request.ArtifactKind == "PNG"
                    ? "The approved PNG device does not expose exactly one approved A4 pixel media."
                    : "The approved PDF device does not expose exactly one approved A4 media."));
        }

        try
        {
            validator.SetCanonicalMediaName(plotSettings, approvedMediaNames[0]);
        }
        catch (Autodesk.AutoCAD.Runtime.Exception exception)
        {
            throw new InvalidDataException(
                $"{NativeRenderPolicy.MediaUnavailableErrorCode}: "
                + "The approved media could not be selected.",
                exception);
        }

        if (request.RenderOptions.Camera is null)
        {
            validator.SetPlotType(plotSettings, Autodesk.AutoCAD.DatabaseServices.PlotType.Layout);
        }
        else
        {
            if (cameraWindow is null)
            {
                throw new InvalidDataException("Canonical camera plot window is missing.");
            }
            validator.SetPlotType(plotSettings, Autodesk.AutoCAD.DatabaseServices.PlotType.Window);
            validator.SetPlotWindowArea(plotSettings, cameraWindow.PlotWindow);
        }
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
