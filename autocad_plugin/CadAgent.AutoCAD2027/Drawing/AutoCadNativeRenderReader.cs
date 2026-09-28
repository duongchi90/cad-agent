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

internal sealed record NativeRenderMediaObservation(
    string CanonicalMediaName,
    bool Selectable,
    string? Units,
    double? Width,
    double? Height);

internal sealed record NativeRenderMediaCensus(
    IReadOnlyList<NativeRenderMediaObservation> Observations,
    IReadOnlyList<string> ApprovedMediaNames)
{
    private const int MaxDiagnosticObservations = 64;
    private const int MaxDiagnosticFieldLength = 96;
    private const int MaxDiagnosticOutputLength = 8192;
    private const int DiagnosticSummaryReserveLength = 256;

    internal string FormatDiagnostic()
    {
        var diagnostic = new StringBuilder("Observed plot media: [");
        var displayedCount = 0;
        foreach (var item in Observations.Take(MaxDiagnosticObservations))
        {
            var observation =
                $"canonical={FormatDiagnosticField(item.CanonicalMediaName)};"
                + $"selectable={item.Selectable.ToString().ToLowerInvariant()};"
                + $"units={FormatDiagnosticField(item.Units)};"
                + $"size={FormatSize(item.Width, item.Height)};"
                + $"approved={ApprovedMediaNames.Contains(item.CanonicalMediaName, StringComparer.Ordinal).ToString().ToLowerInvariant()}";
            var separator = displayedCount == 0 ? string.Empty : " | ";
            if (diagnostic.Length + separator.Length + observation.Length + DiagnosticSummaryReserveLength
                > MaxDiagnosticOutputLength)
            {
                break;
            }

            diagnostic.Append(separator).Append(observation);
            displayedCount++;
        }

        var omittedCount = Observations.Count - displayedCount;
        var outputTruncated = (omittedCount > 0).ToString().ToLowerInvariant();
        var summary = $"]; observation_count={Observations.Count}; "
            + $"approved_count={ApprovedMediaNames.Count}; displayed_observations={displayedCount}; "
            + $"omitted_observations={omittedCount}; output_truncated={outputTruncated}.";
        diagnostic.Append(summary);
        return diagnostic.ToString();
    }

    private static string Format(double? value) =>
        value?.ToString("R", CultureInfo.InvariantCulture) ?? "unavailable";

    private static string FormatSize(double? width, double? height) =>
        !width.HasValue && !height.HasValue
            ? "unavailable"
            : $"{Format(width)}x{Format(height)}";

    private static string FormatDiagnosticField(string? value)
    {
        if (value is null)
        {
            return "unavailable";
        }

        var formatted = new StringBuilder(Math.Min(value.Length, MaxDiagnosticFieldLength));
        foreach (var character in value)
        {
            var fragment = char.IsControl(character)
                || char.IsSurrogate(character)
                || character is '\\' or ';' or '=' or '|' or '[' or ']' or ','
                ? $"\\u{(int)character:X4}"
                : character.ToString();
            if (formatted.Length + fragment.Length > MaxDiagnosticFieldLength - 1)
            {
                formatted.Append('…');
                break;
            }

            formatted.Append(fragment);
        }

        return formatted.ToString();
    }
}

public static class AutoCadNativeRenderReader
{
    private const string PdfDevice = "AutoCAD PDF (General Documentation).pc3";
    private const string PngDevice = "PublishToWeb PNG.pc3";
    private const string A4MediaName = "ISO_A4_(210.00_x_297.00_MM)";
    private const string PixelUnits = "Pixels";
    private const string MillimeterUnits = "Millimeters";
    private const double A4WidthMillimeters = 210;
    private const double A4HeightMillimeters = 297;
    private const double CameraStateTolerance = 1e-9;

    private sealed record ObservedCameraState(
        string ViewDirection,
        string Ucs,
        string VisualStyle);

    private sealed record CameraWindow(
        IReadOnlyList<double>? RequestedWcsBbox,
        IReadOnlyList<double>? ObservedWcsBbox,
        IReadOnlyList<double> ViewCenter,
        double ViewWidth,
        double ViewHeight,
        string ObservedViewDirection,
        string ObservedUcs,
        string ObservedVisualStyle,
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
        var receipt = request.ArtifactKind == "PNG"
            ? CreateCameraReceipt(
                request,
                cameraWindow,
                artifact,
                captureTimestamp.ToUniversalTime(),
                sessionStateRestored)
            : null;
        var cameraObservation = request.ArtifactKind == "PDF"
            ? CreateCameraObservation(
                request,
                cameraWindow,
                captureTimestamp.ToUniversalTime(),
                sessionStateRestored)
            : null;
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
            receipt,
            cameraObservation);
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
                    request,
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
        NativeRenderRequest request,
        NativeRenderCamera camera)
    {
        NativeRenderPolicy.EnsureCameraSupported(camera);
        using var currentView = document.Editor.GetCurrentView();
        var observedCameraState = EnsureObservedCanonicalCameraState(
            request,
            camera,
            currentView);

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
            currentView,
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
            observedCameraState.ViewDirection,
            observedCameraState.Ucs,
            observedCameraState.VisualStyle,
            plotWindow);
    }

    private static ObservedCameraState EnsureObservedCanonicalCameraState(
        NativeRenderRequest request,
        NativeRenderCamera camera,
        ViewTableRecord currentView)
    {
        var currentLayout = Convert.ToString(
            AcadApplication.GetSystemVariable("CTAB"),
            CultureInfo.InvariantCulture) ?? string.Empty;
        if (!string.Equals(currentLayout, request.Layout.Name, StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                "NATIVE_RENDER_CAMERA_LAYOUT_NOT_ACTIVE: "
                + "The requested camera layout is not the active AutoCAD layout.");
        }

        var currentViewport = Convert.ToInt32(
            AcadApplication.GetSystemVariable("CVPORT"),
            CultureInfo.InvariantCulture);
        if (currentViewport != 1)
        {
            throw new InvalidDataException(
                "NATIVE_RENDER_CAMERA_LAYOUT_NOT_ACTIVE: "
                + "Canonical camera rendering requires the paper-space viewport for the active layout.");
        }

        var worldUcs = Convert.ToInt32(
            AcadApplication.GetSystemVariable("WORLDUCS"),
            CultureInfo.InvariantCulture);
        if (worldUcs != 1)
        {
            throw new InvalidDataException(
                "NATIVE_RENDER_CAMERA_STATE_MISMATCH: The active UCS is not WORLD.");
        }

        if (AcadApplication.GetSystemVariable("VIEWDIR") is not Point3d observedViewDirection
            || !IsTopDirection(
                observedViewDirection.X,
                observedViewDirection.Y,
                observedViewDirection.Z)
            || !IsTopDirection(
                currentView.ViewDirection.X,
                currentView.ViewDirection.Y,
                currentView.ViewDirection.Z))
        {
            throw new InvalidDataException(
                "NATIVE_RENDER_CAMERA_STATE_MISMATCH: The active view direction is not TOP.");
        }

        var observedViewTwist = Convert.ToDouble(
            AcadApplication.GetSystemVariable("VIEWTWIST"),
            CultureInfo.InvariantCulture);
        if (Math.Abs(observedViewTwist) > CameraStateTolerance
            || Math.Abs(currentView.ViewTwist) > CameraStateTolerance
            || Math.Abs(observedViewTwist - currentView.ViewTwist) > CameraStateTolerance)
        {
            throw new InvalidDataException(
                "NATIVE_RENDER_CAMERA_STATE_MISMATCH: The active view has non-zero twist.");
        }

        var rawVisualStyle = ResolveVisualStyle(currentView.VisualStyleId);
        if (!string.Equals(rawVisualStyle, "2dWireframe", StringComparison.OrdinalIgnoreCase)
            && !string.Equals(rawVisualStyle, "2D Wireframe", StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidDataException(
                "NATIVE_RENDER_CAMERA_STATE_MISMATCH: The active visual style is not 2D Wireframe.");
        }

        var observed = new ObservedCameraState("TOP", "WORLD", "2D_WIREFRAME");
        if (!string.Equals(camera.ViewDirection, observed.ViewDirection, StringComparison.Ordinal)
            || !string.Equals(camera.Ucs, observed.Ucs, StringComparison.Ordinal)
            || !string.Equals(camera.VisualStyle, observed.VisualStyle, StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                "NATIVE_RENDER_CAMERA_STATE_MISMATCH: Requested and observed camera profiles differ.");
        }

        return observed;
    }

    private static string ResolveVisualStyle(ObjectId vsId)
    {
        using var transaction = vsId.Database.TransactionManager.StartOpenCloseTransaction();
        var record = (DBVisualStyle)transaction.GetObject(vsId, OpenMode.ForRead);
        return record.Name;
    }

    private static bool IsTopDirection(double x, double y, double z) =>
        Math.Abs(x) <= CameraStateTolerance
        && Math.Abs(y) <= CameraStateTolerance
        && Math.Abs(z - 1.0) <= CameraStateTolerance;

    private static Extents2d TransformWcsWindowToDcs(
        ViewTableRecord view,
        double minX,
        double minY,
        double maxX,
        double maxY)
    {
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
            cameraWindow.ObservedViewDirection,
            cameraWindow.ObservedUcs,
            cameraWindow.ObservedVisualStyle,
            artifact.Sha256,
            artifact.Width.Value,
            artifact.Height.Value,
            captureTimestamp,
            transientStateRestored);
    }

    private static NativeRenderCameraObservation CreateCameraObservation(
        NativeRenderRequest request,
        CameraWindow? cameraWindow,
        DateTimeOffset captureTimestamp,
        bool transientStateRestored)
    {
        var camera = request.RenderOptions.Camera
            ?? throw new InvalidDataException("Canonical camera PDF render requires camera context.");
        if (cameraWindow is null)
        {
            throw new InvalidDataException("Canonical camera PDF render did not produce observed camera state.");
        }

        return new NativeRenderCameraObservation(
            "native-camera-observation-1.0",
            $"observation-{camera.CaptureId}",
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
            cameraWindow.ObservedViewDirection,
            cameraWindow.ObservedUcs,
            cameraWindow.ObservedVisualStyle,
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

        var census = CensusPlotMedia(
            request.ArtifactKind,
            mediaNames,
            mediaName =>
            {
                try
                {
                    validator.SetCanonicalMediaName(plotSettings, mediaName);
                }
                catch (Autodesk.AutoCAD.Runtime.Exception)
                {
                    return new NativeRenderMediaObservation(
                        mediaName,
                        false,
                        null,
                        null,
                        null);
                }

                var paperSize = plotSettings.PlotPaperSize;
                return new NativeRenderMediaObservation(
                    mediaName,
                    true,
                    plotSettings.PlotPaperUnits.ToString(),
                    paperSize.X,
                    paperSize.Y);
            });
        var approvedMediaNames = census.ApprovedMediaNames;

        if (approvedMediaNames.Count != 1)
        {
            throw new InvalidDataException(
                $"{NativeRenderPolicy.MediaUnavailableErrorCode}: "
                + (request.ArtifactKind == "PNG"
                    ? "The approved PNG device does not expose exactly one approved A4 pixel media."
                    : "The approved PDF device does not expose exactly one approved A4 media.")
                + $" {census.FormatDiagnostic()}");
        }

        try
        {
            validator.SetCanonicalMediaName(plotSettings, approvedMediaNames[0]);
        }
        catch (Autodesk.AutoCAD.Runtime.Exception exception)
        {
            throw new InvalidDataException(
                $"{NativeRenderPolicy.MediaUnavailableErrorCode}: "
                + $"The approved media could not be selected. {census.FormatDiagnostic()}",
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
            validator.SetPlotWindowArea(plotSettings, cameraWindow.PlotWindow);
            validator.SetPlotType(plotSettings, Autodesk.AutoCAD.DatabaseServices.PlotType.Window);
        }
        validator.SetUseStandardScale(plotSettings, true);
        validator.SetStdScaleType(plotSettings, StdScaleType.ScaleToFit);
        validator.SetCurrentStyleSheet(plotSettings, request.RenderOptions.PlotStyle);
    }

    internal static NativeRenderMediaCensus CensusPlotMedia(
        string artifactKind,
        IEnumerable<string> canonicalMediaNames,
        Func<string, NativeRenderMediaObservation> observe)
    {
        ArgumentNullException.ThrowIfNull(artifactKind);
        ArgumentNullException.ThrowIfNull(canonicalMediaNames);
        ArgumentNullException.ThrowIfNull(observe);

        var observations = canonicalMediaNames
            .Where(name => !string.IsNullOrWhiteSpace(name))
            .Select(name => observe(name) with { CanonicalMediaName = name })
            .OrderBy(item => item.CanonicalMediaName, StringComparer.Ordinal)
            .ToArray();
        var approvedMediaNames = observations
            .Where(item => IsApprovedMedia(artifactKind, item))
            .Select(item => item.CanonicalMediaName)
            .ToArray();

        return new NativeRenderMediaCensus(observations, approvedMediaNames);
    }

    private static bool IsApprovedMedia(string artifactKind, NativeRenderMediaObservation media)
    {
        if (!media.Selectable || media.Units is null || media.Width is null || media.Height is null)
        {
            return false;
        }

        if (artifactKind == "PNG")
        {
            return string.Equals(media.Units, PixelUnits, StringComparison.Ordinal)
                && ((IsCloseTo(media.Width.Value, NativeRenderPolicy.ApprovedPngWidth)
                        && IsCloseTo(media.Height.Value, NativeRenderPolicy.ApprovedPngHeight))
                    || (IsCloseTo(media.Width.Value, NativeRenderPolicy.ApprovedPngLandscapeWidth)
                        && IsCloseTo(media.Height.Value, NativeRenderPolicy.ApprovedPngLandscapeHeight)));
        }

        return string.Equals(media.CanonicalMediaName, A4MediaName, StringComparison.Ordinal)
            && string.Equals(media.Units, MillimeterUnits, StringComparison.Ordinal)
            && IsCloseTo(media.Width.Value, A4WidthMillimeters)
            && IsCloseTo(media.Height.Value, A4HeightMillimeters);
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
