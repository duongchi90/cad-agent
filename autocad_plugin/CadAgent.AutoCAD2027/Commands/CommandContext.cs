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
        var exactBaseXrefPolicy = ExactBaseXrefPolicy.FromEnvironment();
        var gateway = new AutoCadDrawingGateway(
            document,
            mechanicalWarnings.Add,
            store.IpcDirectory,
            exactBaseXrefPolicy);
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
            exactBaseXrefPolicy: exactBaseXrefPolicy);
    }

    private sealed class AutoCadDrawingGateway : IDrawingGateway, IMechanicalDrawingGateway
    {
        private readonly Document _document;
        private readonly Action<string> _mechanicalWarning;
        private readonly string _ipcDirectory;
        private readonly AutoCadExactBaseXrefReader _exactBaseXrefReader;

        public AutoCadDrawingGateway(
            Document document,
            Action<string> mechanicalWarning,
            string ipcDirectory,
            ExactBaseXrefPolicy exactBaseXrefPolicy)
        {
            _document = document ?? throw new ArgumentNullException(nameof(document));
            _mechanicalWarning = mechanicalWarning ?? throw new ArgumentNullException(nameof(mechanicalWarning));
            _ipcDirectory = string.IsNullOrWhiteSpace(ipcDirectory)
                ? throw new ArgumentException("The IPC directory is required.", nameof(ipcDirectory))
                : ipcDirectory;
            _exactBaseXrefReader = new AutoCadExactBaseXrefReader(
                new AutoCadExactBaseXrefDatabase(_document),
                exactBaseXrefPolicy ?? throw new ArgumentNullException(nameof(exactBaseXrefPolicy)));
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

        public BoundedNativeLineEditSnapshot ApplyBoundedNativeLineEdit(
            BoundedNativeLineEditRequest request)
        {
            ArgumentNullException.ThrowIfNull(request);
            var database = _document.Database
                ?? throw new InvalidOperationException("The active document has no database.");
            var activePath = ActiveDocumentFullPath;
            var dbmodBefore = Convert.ToInt32(ReadSystemNumber("DBMOD"));
            var targetBefore = Array.Empty<NativeLineState>();
            var protectedBefore = Array.Empty<NativeLineState>();

            using (var transaction = _document.TransactionManager.StartOpenCloseTransaction())
            {
                targetBefore = request.TargetHandles
                    .Select(handle => ReadNativeLineState(database, transaction, handle))
                    .ToArray();
                protectedBefore = request.ProtectedCompetingHandles
                    .Select(handle => ReadNativeLineState(database, transaction, handle))
                    .ToArray();

                var preconditions = ValidateNativeLineEditPreconditions(
                    request,
                    targetBefore,
                    protectedBefore);
                if (preconditions.Count != 0)
                {
                    return FailureWithEvidence(
                        activePath,
                        dbmodBefore,
                        preconditions,
                        targetBefore,
                        protectedBefore,
                        targetBefore,
                        protectedBefore);
                }

                foreach (var lineState in targetBefore)
                {
                    var line = (Line)transaction.GetObject(lineState.ObjectId, OpenMode.ForWrite, false);
                    line.EndPoint = new Point3d(
                        line.StartPoint.X,
                        line.StartPoint.Y + request.TargetAfterLength,
                        line.StartPoint.Z);
                }

                transaction.Commit();
            }

            var targetAfter = ReadNativeLineStates(database, request.TargetHandles);
            var protectedAfter = ReadNativeLineStates(database, request.ProtectedCompetingHandles);
            var readbackErrors = ValidateNativeLineReadback(
                request,
                targetBefore,
                protectedBefore,
                targetAfter,
                protectedAfter);
            if (readbackErrors.Count != 0)
            {
                RestoreNativeLines(database, targetBefore);
                return FailureWithEvidence(
                    activePath,
                    dbmodBefore,
                    readbackErrors,
                    targetBefore,
                    protectedBefore,
                    ReadNativeLineStates(database, request.TargetHandles),
                    ReadNativeLineStates(database, request.ProtectedCompetingHandles));
            }

            var savePerformed = false;
            try
            {
                if (request.Save)
                {
                    database.SaveAs(
                        database.Filename,
                        true,
                        DwgVersion.Current,
                        database.SecurityParameters);
                    savePerformed = true;
                }
            }
            catch (System.Exception exception)
            {
                var rollbackPersisted = TryRestoreAndPersistNativeLines(
                    database,
                    targetBefore,
                    out var rollbackError);
                var errors = new List<string>
                {
                    $"native line edit save failed: {exception.Message}"
                };
                if (rollbackPersisted)
                {
                    errors.Add("native line edit rollback persisted after save failure");
                }
                else
                {
                    errors.Add(
                        $"DURABLE_STATE_UNCERTAIN: native line edit rollback could not be persisted: {rollbackError}");
                }

                return FailureWithEvidence(
                    activePath,
                    dbmodBefore,
                    errors,
                    targetBefore,
                    protectedBefore,
                    ReadNativeLineStates(database, request.TargetHandles),
                    ReadNativeLineStates(database, request.ProtectedCompetingHandles),
                    BoundedNativeLineEditDurableStates.ResolveAfterSaveFailure(rollbackPersisted));
            }

            var targetAfterSave = ReadNativeLineStates(database, request.TargetHandles);
            var protectedAfterSave = ReadNativeLineStates(database, request.ProtectedCompetingHandles);
            var savedReadbackErrors = ValidateNativeLineReadback(
                request,
                targetBefore,
                protectedBefore,
                targetAfterSave,
                protectedAfterSave);
            if (savedReadbackErrors.Count != 0)
            {
                var rollbackPersisted = TryRestoreAndPersistNativeLines(
                    database,
                    targetBefore,
                    out var rollbackError);
                var errors = savedReadbackErrors.ToList();
                if (!rollbackPersisted)
                {
                    errors.Add(
                        $"DURABLE_STATE_UNCERTAIN: native line edit rollback could not be persisted: {rollbackError}");
                }
                else if (savePerformed)
                {
                    errors.Add("native line edit rollback persisted after readback failure");
                }

                return FailureWithEvidence(
                    activePath,
                    dbmodBefore,
                    errors,
                    targetBefore,
                    protectedBefore,
                    ReadNativeLineStates(database, request.TargetHandles),
                    ReadNativeLineStates(database, request.ProtectedCompetingHandles),
                    BoundedNativeLineEditDurableStates.ResolveAfterSaveFailure(rollbackPersisted));
            }

            return new BoundedNativeLineEditSnapshot(
                Success: true,
                DrawingFullPath: activePath,
                Changed: true,
                EntityHandles: request.TargetHandles.ToArray(),
                Warnings: Array.Empty<string>(),
                Errors: Array.Empty<string>(),
                DbmodBefore: dbmodBefore,
                DbmodAfter: Convert.ToInt32(ReadSystemNumber("DBMOD")),
                SavePerformed: savePerformed,
                DurableState: BoundedNativeLineEditDurableStates.Changed,
                TargetEntities: BuildNativeLineEvidence(targetBefore, targetAfterSave, protectedBefore),
                ProtectedEntities: BuildNativeLineEvidence(protectedBefore, protectedAfterSave, targetBefore));
        }

        private NativeLineState[] ReadNativeLineStates(
            Database database,
            IReadOnlyList<string> handles)
        {
            using var transaction = _document.TransactionManager.StartOpenCloseTransaction();
            return handles
                .Select(handle => ReadNativeLineState(database, transaction, handle))
                .ToArray();
        }

        private static NativeLineState ReadNativeLineState(
            Database database,
            Transaction transaction,
            string handleText)
        {
            if (!TryParseHandle(handleText, out var handle))
            {
                throw new InvalidOperationException($"Invalid native line handle '{handleText}'.");
            }

            var objectId = database.GetObjectId(false, new Handle(handle), 0);
            if (objectId.IsNull
                || transaction.GetObject(objectId, OpenMode.ForRead, false) is not Line line)
            {
                throw new InvalidOperationException($"Native line handle '{handleText}' was not found.");
            }

            var owner = transaction.GetObject(line.OwnerId, OpenMode.ForRead, false) as BlockTableRecord
                ?? throw new InvalidOperationException($"Native line handle '{handleText}' has no readable owner.");
            var references = ReadReferenceHandles(database, transaction, line.OwnerId);
            return new NativeLineState(
                handleText.Trim().ToUpperInvariant(),
                objectId,
                line.Layer,
                owner.Handle.ToString().ToUpperInvariant(),
                owner.Name ?? string.Empty,
                references,
                line.StartPoint,
                line.EndPoint);
        }

        private static IReadOnlyList<string> ReadReferenceHandles(
            Database database,
            Transaction transaction,
            ObjectId definitionId)
        {
            var references = new List<string>();
            var blockTable = (BlockTable)transaction.GetObject(database.BlockTableId, OpenMode.ForRead);
            foreach (ObjectId blockTableRecordId in blockTable)
            {
                if (transaction.GetObject(blockTableRecordId, OpenMode.ForRead, false)
                    is not BlockTableRecord blockTableRecord)
                {
                    continue;
                }

                foreach (ObjectId objectId in blockTableRecord)
                {
                    if (transaction.GetObject(objectId, OpenMode.ForRead, false)
                        is BlockReference blockReference
                        && blockReference.BlockTableRecord == definitionId)
                    {
                        references.Add(blockReference.Handle.ToString().ToUpperInvariant());
                    }
                }
            }

            return references.OrderBy(value => value, StringComparer.Ordinal).ToArray();
        }

        private static IReadOnlyList<string> ValidateNativeLineEditPreconditions(
            BoundedNativeLineEditRequest request,
            IReadOnlyList<NativeLineState> target,
            IReadOnlyList<NativeLineState> protectedLines)
        {
            var errors = new List<string>();
            if (target.Count != request.TargetHandles.Count
                || protectedLines.Count != request.ProtectedCompetingHandles.Count)
            {
                errors.Add("native line edit could not resolve every authorized handle");
                return errors;
            }

            if (target.Select(line => line.OwnerHandle).Distinct(StringComparer.OrdinalIgnoreCase).Count() != 1)
            {
                errors.Add("native line edit target handles do not share one owner container");
            }

            if (target.Any(line => line.ReferenceHandles.Count != 0)
                || protectedLines.Any(line => line.ReferenceHandles.Count != 0))
            {
                errors.Add("native line edit is not isolated from block-reference reachability");
            }

            var protectedByHandle = protectedLines.ToDictionary(
                line => line.Handle,
                StringComparer.OrdinalIgnoreCase);
            foreach (var line in target)
            {
                if (line.Type != ReviewEntityTypes.Line)
                {
                    errors.Add($"native line edit handle '{line.Handle}' is not a LINE");
                    continue;
                }

                if (Math.Abs(line.Length - request.ExpectedBeforeLength) > request.LengthTolerance
                    || Math.Abs(line.EndPoint.X - line.StartPoint.X) > request.LengthTolerance
                    || line.EndPoint.Y <= line.StartPoint.Y)
                {
                    errors.Add($"native line edit handle '{line.Handle}' does not match the expected positive-Y 490 geometry");
                }

                if (protectedByHandle.ContainsKey(line.Handle))
                {
                    errors.Add($"native line edit handle '{line.Handle}' overlaps the protected occurrence");
                }
            }

            if (protectedLines.Any(line => line.Type != ReviewEntityTypes.Line))
            {
                errors.Add("the protected competing occurrence must contain only LINE entities");
            }

            return errors;
        }

        private static IReadOnlyList<string> ValidateNativeLineReadback(
            BoundedNativeLineEditRequest request,
            IReadOnlyList<NativeLineState> targetBefore,
            IReadOnlyList<NativeLineState> protectedBefore,
            IReadOnlyList<NativeLineState> targetAfter,
            IReadOnlyList<NativeLineState> protectedAfter)
        {
            var errors = new List<string>();
            if (targetAfter.Count != targetBefore.Count || protectedAfter.Count != protectedBefore.Count)
            {
                errors.Add("native line edit readback did not return every authorized handle");
                return errors;
            }

            for (var index = 0; index < targetBefore.Count; index++)
            {
                if (Math.Abs(targetAfter[index].Length - request.TargetAfterLength) > request.LengthTolerance)
                {
                    errors.Add($"native line edit readback length mismatch for '{targetBefore[index].Handle}'");
                }

                if (!SamePoint(targetBefore[index].StartPoint, targetAfter[index].StartPoint, request.LengthTolerance)
                    || Math.Abs(targetAfter[index].EndPoint.Y - targetBefore[index].StartPoint.Y
                        - request.TargetAfterLength) > request.LengthTolerance)
                {
                    errors.Add($"native line edit readback endpoint mismatch for '{targetBefore[index].Handle}'");
                }
            }

            for (var index = 0; index < protectedBefore.Count; index++)
            {
                if (!SamePoint(protectedBefore[index].StartPoint, protectedAfter[index].StartPoint, request.LengthTolerance)
                    || !SamePoint(protectedBefore[index].EndPoint, protectedAfter[index].EndPoint, request.LengthTolerance))
                {
                    errors.Add($"protected competing handle '{protectedBefore[index].Handle}' changed during native line edit");
                }
            }

            return errors;
        }

        private void RestoreNativeLines(Database database, IReadOnlyList<NativeLineState> states)
        {
            using var transaction = _document.TransactionManager.StartOpenCloseTransaction();
            foreach (var state in states)
            {
                if (transaction.GetObject(state.ObjectId, OpenMode.ForWrite, false) is Line line)
                {
                    line.StartPoint = state.StartPoint;
                    line.EndPoint = state.EndPoint;
                }
            }

            transaction.Commit();
        }

        private bool TryRestoreAndPersistNativeLines(
            Database database,
            IReadOnlyList<NativeLineState> states,
            out string? error)
        {
            try
            {
                RestoreNativeLines(database, states);
                database.SaveAs(
                    database.Filename,
                    true,
                    DwgVersion.Current,
                    database.SecurityParameters);
                error = null;
                return true;
            }
            catch (System.Exception exception)
            {
                error = exception.Message;
                return false;
            }
        }

        private static IReadOnlyList<BoundedNativeLineEditEntityEvidence> BuildNativeLineEvidence(
            IReadOnlyList<NativeLineState> before,
            IReadOnlyList<NativeLineState> after,
            IReadOnlyList<NativeLineState> competing)
        {
            var afterByHandle = after.ToDictionary(state => state.Handle, StringComparer.OrdinalIgnoreCase);
            var competingReferences = competing
                .SelectMany(state => state.ReferenceHandles)
                .ToHashSet(StringComparer.OrdinalIgnoreCase);
            return before.Select(state =>
            {
                var afterState = afterByHandle[state.Handle];
                var shared = state.ReferenceHandles.Any(competingReferences.Contains);
                return new BoundedNativeLineEditEntityEvidence(
                    state.Handle,
                    state.Type,
                    state.Layer,
                    state.OwnerHandle,
                    state.OwnerName,
                    state.ReferenceHandles,
                    shared,
                    state.Length,
                    afterState.Length,
                    state.StartPoint.X,
                    state.StartPoint.Y,
                    state.EndPoint.X,
                    state.EndPoint.Y,
                    afterState.StartPoint.X,
                    afterState.StartPoint.Y,
                    afterState.EndPoint.X,
                    afterState.EndPoint.Y);
            }).ToArray();
        }

        private static BoundedNativeLineEditSnapshot FailureWithEvidence(
            string? drawingPath,
            int dbmodBefore,
            IEnumerable<string> errors,
            IReadOnlyList<NativeLineState> targetBefore,
            IReadOnlyList<NativeLineState> protectedBefore,
            IReadOnlyList<NativeLineState> targetAfter,
            IReadOnlyList<NativeLineState> protectedAfter,
            string durableState = BoundedNativeLineEditDurableStates.Unchanged) =>
            new(
                Success: false,
                DrawingFullPath: drawingPath,
                Changed: false,
                EntityHandles: Array.Empty<string>(),
                Warnings: Array.Empty<string>(),
                Errors: errors.ToArray(),
                DbmodBefore: dbmodBefore,
                DbmodAfter: Convert.ToInt32(ReadSystemNumber("DBMOD")),
                SavePerformed: false,
                DurableState: durableState,
                TargetEntities: BuildNativeLineEvidence(targetBefore, targetAfter, protectedBefore),
                ProtectedEntities: BuildNativeLineEvidence(protectedBefore, protectedAfter, targetBefore));

        private static bool SamePoint(Point3d left, Point3d right, double tolerance) =>
            left.DistanceTo(right) <= tolerance;

        private sealed record NativeLineState(
            string Handle,
            ObjectId ObjectId,
            string Layer,
            string OwnerHandle,
            string OwnerName,
            IReadOnlyList<string> ReferenceHandles,
            Point3d StartPoint,
            Point3d EndPoint)
        {
            public string Type => ReviewEntityTypes.Line;

            public double Length => StartPoint.DistanceTo(EndPoint);
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

        public ExactBaseXrefInspectionSnapshot ReadExactBaseXrefInspection(
            ExactBaseXrefInspectionParameters request) =>
            _exactBaseXrefReader.Read(request);

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
