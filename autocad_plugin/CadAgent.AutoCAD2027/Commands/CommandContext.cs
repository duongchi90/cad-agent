using System.Globalization;
using System.Text.Json;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Geometry;
using CadAgent.AutoCAD2027.Drawing;
using CadAgent.AutoCAD2027.DrawingSetup;
using CadAgent.AutoCAD2027.Ipc;
using CadAgent.AutoCAD2027.Mechanical;
using CadAgent.AutoCAD2027.Review;
using AcadApplication = Autodesk.AutoCAD.ApplicationServices.Application;

namespace CadAgent.AutoCAD2027.Commands;

public sealed class CommandContext
{
    public const string IpcDirectoryEnvironmentVariable = "CAD_AGENT_DOTNET_IPC_DIR";
    public const string DefaultIpcDirectory = @"C:\temp";

    private readonly ICollection<string> _mechanicalWarnings;

    public CommandContext(
        JsonFileStore store,
        IDrawingGateway drawingGateway,
        Action closeWithoutSaving,
        Action<string>? report = null,
        Func<DateTimeOffset>? clock = null,
        IMechanicalAdapter? mechanicalAdapter = null,
        ICollection<string>? mechanicalWarnings = null,
        ExactBaseXrefPolicy? exactBaseXrefPolicy = null)
    {
        Store = store ?? throw new ArgumentNullException(nameof(store));
        DrawingGateway = drawingGateway ?? throw new ArgumentNullException(nameof(drawingGateway));
        CloseWithoutSaving = closeWithoutSaving ?? throw new ArgumentNullException(nameof(closeWithoutSaving));
        Report = report ?? (_ => { });
        Clock = clock ?? (() => DateTimeOffset.UtcNow);
        MechanicalAdapter = mechanicalAdapter ?? new NoOpMechanicalAdapter();
        _mechanicalWarnings = mechanicalWarnings ?? new List<string>();
        ExactBaseXrefPolicy = exactBaseXrefPolicy ?? ExactBaseXrefPolicy.FromEnvironment();
    }

    public JsonFileStore Store { get; }

    public IDrawingGateway DrawingGateway { get; }

    public IMechanicalAdapter MechanicalAdapter { get; }

    public ExactBaseXrefPolicy ExactBaseXrefPolicy { get; }

    public Action CloseWithoutSaving { get; }

    public Action<string> Report { get; }

    public Func<DateTimeOffset> Clock { get; }

    internal IReadOnlyList<string> MechanicalWarnings => _mechanicalWarnings.ToArray();

    internal void ClearMechanicalWarnings() => _mechanicalWarnings.Clear();

    public OperationDispatcher CreateDispatcher() => new(this);

    public IReadOnlyList<string> GetPendingRequestIds()
    {
        var requestIds = new List<string>();
        foreach (var path in Directory.EnumerateFiles(Store.IpcDirectory, "cadagent_dotnet_request_*.json"))
        {
            var fileName = Path.GetFileName(path);
            const string prefix = "cadagent_dotnet_request_";
            const string suffix = ".json";
            if (!fileName.StartsWith(prefix, StringComparison.Ordinal)
                || !fileName.EndsWith(suffix, StringComparison.Ordinal))
            {
                continue;
            }

            var requestId = fileName[prefix.Length..^suffix.Length];
            try
            {
                ContractValidator.EnsureRequestId(requestId);
                requestIds.Add(requestId);
            }
            catch (ArgumentException)
            {
                // Ignore files that cannot be a request for this contract.
            }
        }

        return requestIds.OrderBy(value => value, StringComparer.Ordinal).ToArray();
    }

    public static CommandContext CreateLive()
    {
        var document = AcadApplication.DocumentManager.MdiActiveDocument
            ?? throw new InvalidOperationException("No active AutoCAD document is available.");
        var editor = document.Editor;
        var mechanicalWarnings = new List<string>();
        var ipcDirectory = Environment.GetEnvironmentVariable(IpcDirectoryEnvironmentVariable);
        var store = new JsonFileStore(
            string.IsNullOrWhiteSpace(ipcDirectory) ? DefaultIpcDirectory : ipcDirectory);
        var gateway = new AutoCadDrawingGateway(document, mechanicalWarnings.Add, store.IpcDirectory);
        var closeScheduler = new OneShotIdleCloseScheduler(
            handler => AcadApplication.Idle += handler,
            handler => AcadApplication.Idle -= handler,
            document.CloseAndDiscard);

        return new CommandContext(
            store,
            gateway,
            // CADAGENT_DISPATCH persists the IPC result before invoking this scheduler.
            // AutoCAD raises Idle after the command has returned and released its
            // document-scoped lock, so the one-shot callback can close safely.
            closeScheduler.Schedule,
            message => editor.WriteMessage($"\n{message}"),
            mechanicalAdapter: new ManagedMechanicalAdapter(gateway),
            mechanicalWarnings: mechanicalWarnings,
            exactBaseXrefPolicy: ExactBaseXrefPolicy.FromEnvironment());
    }

    private sealed class AutoCadDrawingGateway : IDrawingGateway, IMechanicalDrawingGateway
    {
        private readonly Document _document;
        private readonly Action<string> _mechanicalWarning;
        private readonly string _ipcDirectory;

        public AutoCadDrawingGateway(
            Document document,
            Action<string> mechanicalWarning,
            string ipcDirectory)
        {
            _document = document ?? throw new ArgumentNullException(nameof(document));
            _mechanicalWarning = mechanicalWarning ?? throw new ArgumentNullException(nameof(mechanicalWarning));
            _ipcDirectory = string.IsNullOrWhiteSpace(ipcDirectory)
                ? throw new ArgumentException("The IPC directory is required.", nameof(ipcDirectory))
                : ipcDirectory;
        }

        public string? ActiveDocumentFullPath => _document.Database?.Filename;

        public IReadOnlyList<EntitySnapshot> ReadEntities(IReadOnlyCollection<string> handles)
        {
            ArgumentNullException.ThrowIfNull(handles);

            var snapshots = new List<EntitySnapshot>();
            using var transaction = _document.TransactionManager.StartOpenCloseTransaction();
            foreach (var handleText in handles)
            {
                if (!TryParseHandle(handleText, out var handle))
                {
                    continue;
                }

                try
                {
                    var objectId = _document.Database.GetObjectId(false, new Handle(handle), 0);
                    if (objectId.IsNull
                        || transaction.GetObject(objectId, OpenMode.ForRead, false) is not Entity entity)
                    {
                        continue;
                    }

                    snapshots.Add(CreateSnapshot(entity));
                }
                catch (System.Exception)
                {
                    // ReviewEngine turns an absent/unreadable handle into a warning.
                }
            }

            return snapshots;
        }

        public DrawingSetupSnapshot ReadDrawingSetup()
        {
            var database = _document.Database
                ?? throw new InvalidOperationException("The active document has no database.");
            var dbModBefore = Convert.ToInt32(ReadSystemNumber("DBMOD"));
            var variables = new Dictionary<string, double>(StringComparer.Ordinal)
            {
                ["INSUNITS"] = ReadSystemNumber("INSUNITS"),
                ["MEASUREMENT"] = ReadSystemNumber("MEASUREMENT"),
                ["LTSCALE"] = ReadSystemNumber("LTSCALE"),
                ["CELTSCALE"] = ReadSystemNumber("CELTSCALE"),
                ["PSLTSCALE"] = ReadSystemNumber("PSLTSCALE"),
                ["MSLTSCALE"] = ReadSystemNumber("MSLTSCALE"),
                ["DIMASSOC"] = ReadSystemNumber("DIMASSOC"),
                ["ANNOALLVISIBLE"] = ReadSystemNumber("ANNOALLVISIBLE")
            };
            var layers = new List<LayerSetupSnapshot>();
            var textStyles = new List<TextStyleSetupSnapshot>();
            var dimensionStyles = new List<string>();
            var layouts = new List<LayoutSetupSnapshot>();
            var missingFonts = new List<string>();
            var substitutedFonts = new List<string>();
            string currentLayer;
            string[] mLeaderStyles;
            string[] tableStyles;

            using (var transaction = _document.TransactionManager.StartOpenCloseTransaction())
            {
                var layerTable = (LayerTable)transaction.GetObject(
                    database.LayerTableId,
                    OpenMode.ForRead);
                foreach (ObjectId layerId in layerTable)
                {
                    var layer = (LayerTableRecord)transaction.GetObject(
                        layerId,
                        OpenMode.ForRead);
                    var linetype = (LinetypeTableRecord)transaction.GetObject(
                        layer.LinetypeObjectId,
                        OpenMode.ForRead);
                    layers.Add(new(layer.Name, linetype.Name, layer.IsPlottable));
                }

                var currentLayerRecord = (LayerTableRecord)transaction.GetObject(
                    database.Clayer,
                    OpenMode.ForRead);
                currentLayer = currentLayerRecord.Name;

                var textStyleTable = (TextStyleTable)transaction.GetObject(
                    database.TextStyleTableId,
                    OpenMode.ForRead);
                foreach (ObjectId textStyleId in textStyleTable)
                {
                    var textStyle = (TextStyleTableRecord)transaction.GetObject(
                        textStyleId,
                        OpenMode.ForRead);
                    var font = textStyle.FileName ?? string.Empty;
                    var bigFont = textStyle.BigFontFileName ?? string.Empty;
                    textStyles.Add(new(textStyle.Name, font, bigFont));
                    InspectDeclaredFont(font, database, missingFonts, substitutedFonts);
                    InspectDeclaredFont(bigFont, database, missingFonts, substitutedFonts);
                }

                var dimensionStyleTable = (DimStyleTable)transaction.GetObject(
                    database.DimStyleTableId,
                    OpenMode.ForRead);
                foreach (ObjectId dimensionStyleId in dimensionStyleTable)
                {
                    var dimensionStyle = (DimStyleTableRecord)transaction.GetObject(
                        dimensionStyleId,
                        OpenMode.ForRead);
                    dimensionStyles.Add(dimensionStyle.Name);
                }

                var layoutDictionary = (DBDictionary)transaction.GetObject(
                    database.LayoutDictionaryId,
                    OpenMode.ForRead);
                foreach (DBDictionaryEntry entry in layoutDictionary)
                {
                    var layout = (Layout)transaction.GetObject(entry.Value, OpenMode.ForRead);
                    if (layout.ModelType)
                    {
                        continue;
                    }

                    var viewportScales = new List<double>();
                    var viewportsLocked = true;
                    var paperSpaceViewportId = layout.GetViewports()
                        .Cast<ObjectId>()
                        .FirstOrDefault();
                    var layoutBlock = (BlockTableRecord)transaction.GetObject(
                        layout.BlockTableRecordId,
                        OpenMode.ForRead);
                    foreach (ObjectId entityId in layoutBlock)
                    {
                        if (entityId == paperSpaceViewportId
                            || transaction.GetObject(entityId, OpenMode.ForRead, false)
                            is not Viewport viewport
                            || viewport.CustomScale <= 0)
                        {
                            continue;
                        }

                        viewportScales.Add(viewport.CustomScale);
                        viewportsLocked &= viewport.Locked;
                    }

                    if (viewportScales.Count > 0)
                    {
                        layouts.Add(new(
                            layout.LayoutName,
                            viewportScales.OrderBy(scale => scale).ToArray(),
                            viewportsLocked));
                    }
                }

                mLeaderStyles = ReadDictionaryNames(
                    transaction,
                    database.MLeaderStyleDictionaryId);
                tableStyles = ReadDictionaryNames(
                    transaction,
                    database.TableStyleDictionaryId);
            }

            var customProperties = ReadCustomProperties(database);
            var dbModAfter = Convert.ToInt32(ReadSystemNumber("DBMOD"));
            if (dbModBefore != dbModAfter)
            {
                throw new InvalidOperationException(
                    $"Drawing setup audit changed DBMOD from {dbModBefore} to {dbModAfter}.");
            }

            return new DrawingSetupSnapshot(
                database.Filename,
                dbModBefore,
                dbModAfter,
                variables,
                currentLayer,
                customProperties,
                layers.OrderBy(layer => layer.Name, StringComparer.Ordinal).ToArray(),
                textStyles.OrderBy(style => style.Name, StringComparer.Ordinal).ToArray(),
                dimensionStyles.OrderBy(name => name, StringComparer.Ordinal).ToArray(),
                mLeaderStyles,
                tableStyles,
                layouts.OrderBy(layout => layout.Name, StringComparer.Ordinal).ToArray(),
                missingFonts.Distinct(StringComparer.Ordinal).OrderBy(name => name, StringComparer.Ordinal).ToArray(),
                substitutedFonts.Distinct(StringComparer.Ordinal).OrderBy(name => name, StringComparer.Ordinal).ToArray());
        }

        public VisualEvidenceSnapshot ReadVisualEvidence(VisualEvidenceRequest request) =>
            AutoCadVisualEvidenceReader.Export(_document, request, _ipcDirectory, DateTimeOffset.UtcNow);

        public NativeRenderEvidenceSnapshot ReadNativeRenderEvidence(NativeRenderRequest request) =>
            AutoCadNativeRenderReader.Capture(
                _document,
                request,
                _ipcDirectory,
                DateTimeOffset.UtcNow);

        public IReadOnlyList<MechanicalComponentSnapshot> ReadMechanicalComponents()
        {
            var snapshots = new List<MechanicalComponentSnapshot>();
            using var transaction = _document.TransactionManager.StartOpenCloseTransaction();
            var blockTable = (BlockTable)transaction.GetObject(
                _document.Database.BlockTableId,
                OpenMode.ForRead);
            var modelSpace = (BlockTableRecord)transaction.GetObject(
                blockTable[BlockTableRecord.ModelSpace],
                OpenMode.ForRead);

            foreach (ObjectId objectId in modelSpace)
            {
                try
                {
                    if (transaction.GetObject(objectId, OpenMode.ForRead, false)
                        is not BlockReference blockReference)
                    {
                        continue;
                    }

                    var attributes = new List<MechanicalAttributeSnapshot>();
                    foreach (ObjectId attributeId in blockReference.AttributeCollection)
                    {
                        try
                        {
                            if (transaction.GetObject(attributeId, OpenMode.ForRead, false)
                                is AttributeReference attributeReference)
                            {
                                attributes.Add(new(
                                    NormalizeMechanicalTag(attributeReference.Tag),
                                    attributeReference.TextString ?? string.Empty));
                            }
                        }
                        catch (System.Exception exception)
                            when (IsExpectedMechanicalObjectReadFailure(exception))
                        {
                            _mechanicalWarning(
                                $"Skipped unreadable direct attribute {attributeId} on insert {objectId}: "
                                + exception.Message);
                        }
                    }

                    snapshots.Add(new(
                        blockReference.Handle.ToString().ToUpperInvariant(),
                        blockReference.Name ?? string.Empty,
                        attributes
                            .OrderBy(attribute => attribute.Tag, StringComparer.Ordinal)
                            .ThenBy(attribute => attribute.Value, StringComparer.Ordinal)
                            .ToArray()));
                }
                catch (System.Exception exception)
                    when (IsExpectedMechanicalObjectReadFailure(exception))
                {
                    _mechanicalWarning(
                        $"Skipped unreadable direct ModelSpace insert {objectId}: "
                        + exception.Message);
                }
            }

            return snapshots
                .OrderBy(snapshot => snapshot.Handle, StringComparer.Ordinal)
                .ToArray();
        }

        private static bool IsExpectedMechanicalObjectReadFailure(System.Exception exception) =>
            exception is Autodesk.AutoCAD.Runtime.Exception
                or InvalidOperationException
                or ObjectDisposedException;

        private static string NormalizeMechanicalTag(string? tag) =>
            (tag ?? string.Empty).Trim().ToUpperInvariant();

        private static double ReadSystemNumber(string name) =>
            Convert.ToDouble(AcadApplication.GetSystemVariable(name), CultureInfo.InvariantCulture);

        private static string[] ReadDictionaryNames(
            Transaction transaction,
            ObjectId dictionaryId)
        {
            if (dictionaryId.IsNull)
            {
                return Array.Empty<string>();
            }

            var dictionary = (DBDictionary)transaction.GetObject(dictionaryId, OpenMode.ForRead);
            var names = new List<string>();
            foreach (DBDictionaryEntry entry in dictionary)
            {
                _ = transaction.GetObject(entry.Value, OpenMode.ForRead);
                names.Add(entry.Key);
            }

            return names.OrderBy(name => name, StringComparer.Ordinal).ToArray();
        }

        private static IReadOnlyDictionary<string, string> ReadCustomProperties(Database database)
        {
            var properties = new SortedDictionary<string, string>(StringComparer.Ordinal);
            var customProperties = database.SummaryInfo.CustomProperties;
            while (customProperties.MoveNext())
            {
                var key = Convert.ToString(customProperties.Key, CultureInfo.InvariantCulture);
                if (string.IsNullOrEmpty(key))
                {
                    continue;
                }

                properties[key] = Convert.ToString(customProperties.Value, CultureInfo.InvariantCulture)
                    ?? string.Empty;
            }

            return properties;
        }

        private static void InspectDeclaredFont(
            string declaredFont,
            Database database,
            ICollection<string> missingFonts,
            ICollection<string> substitutedFonts)
        {
            if (string.IsNullOrWhiteSpace(declaredFont))
            {
                return;
            }

            string? resolvedPath;
            try
            {
                resolvedPath = HostApplicationServices.Current.FindFile(
                    declaredFont,
                    database,
                    FindFileHint.Default);
            }
            catch (Autodesk.AutoCAD.Runtime.Exception)
            {
                missingFonts.Add(declaredFont);
                return;
            }

            if (string.IsNullOrWhiteSpace(resolvedPath))
            {
                missingFonts.Add(declaredFont);
                return;
            }

            var declaredName = Path.GetFileName(declaredFont);
            var resolvedName = Path.GetFileName(resolvedPath);
            if (!string.Equals(declaredName, resolvedName, StringComparison.OrdinalIgnoreCase))
            {
                substitutedFonts.Add($"{declaredFont} -> {resolvedName}");
            }
        }

        private static bool TryParseHandle(string? value, out long handle)
        {
            return long.TryParse(
                value?.Trim(),
                NumberStyles.HexNumber,
                CultureInfo.InvariantCulture,
                out handle);
        }

        private static EntitySnapshot CreateSnapshot(Entity entity)
        {
            var geometry = new Dictionary<string, JsonElement>(StringComparer.Ordinal);
            var type = entity switch
            {
                Line => ReviewEntityTypes.Line,
                Circle => ReviewEntityTypes.Circle,
                Arc => ReviewEntityTypes.Arc,
                DBText => ReviewEntityTypes.Text,
                Dimension => ReviewEntityTypes.Dimension,
                _ => entity.GetType().Name.ToUpperInvariant()
            };

            switch (entity)
            {
                case Line line:
                    AddPoint(geometry, "start", line.StartPoint);
                    AddPoint(geometry, "end", line.EndPoint);
                    break;
                case Circle circle:
                    AddPoint(geometry, "center", circle.Center);
                    geometry["radius"] = JsonSerializer.SerializeToElement(circle.Radius);
                    break;
                case Arc arc:
                    AddPoint(geometry, "center", arc.Center);
                    geometry["radius"] = JsonSerializer.SerializeToElement(arc.Radius);
                    geometry["start_angle"] = JsonSerializer.SerializeToElement(arc.StartAngle);
                    geometry["end_angle"] = JsonSerializer.SerializeToElement(arc.EndAngle);
                    break;
                case DBText text:
                    AddPoint(geometry, "position", text.Position);
                    geometry["height"] = JsonSerializer.SerializeToElement(text.Height);
                    geometry["text"] = JsonSerializer.SerializeToElement(text.TextString);
                    break;
                case Dimension dimension:
                    geometry["measurement"] = JsonSerializer.SerializeToElement(dimension.Measurement);
                    break;
            }

            return new EntitySnapshot(
                entity.Handle.ToString(),
                type,
                entity.Layer,
                geometry);
        }

        private static void AddPoint(
            IDictionary<string, JsonElement> geometry,
            string prefix,
            Point3d point)
        {
            geometry[$"{prefix}_x"] = JsonSerializer.SerializeToElement(point.X);
            geometry[$"{prefix}_y"] = JsonSerializer.SerializeToElement(point.Y);
        }
    }
}
