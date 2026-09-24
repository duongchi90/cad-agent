using System.Globalization;
using System.Security.Cryptography;
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
        private readonly ExactBaseXrefPolicy _exactBaseXrefPolicy;

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
            _exactBaseXrefPolicy = exactBaseXrefPolicy ?? throw new ArgumentNullException(nameof(exactBaseXrefPolicy));
            _exactBaseXrefReader = new AutoCadExactBaseXrefReader(
                new AutoCadExactBaseXrefDatabase(_document),
                _exactBaseXrefPolicy);
        }

        public string? ActiveDocumentFullPath => _document.Database?.Filename;

        public BoundedNativeLineEditSnapshot ApplyBoundedNativeLineEdit(
            BoundedNativeLineEditRequest request)
        {
            ArgumentNullException.ThrowIfNull(request);
            var database = _document.Database
                ?? throw new InvalidOperationException("The active document has no database.");
            var drawingSha256Before = request.DrawingSha256;
            var dbmodBefore = -1;
            NativeLineEditObservation[] before = Array.Empty<NativeLineEditObservation>();
            var mutationStarted = false;
            var committed = false;
            string? candidatePath = null;
            string? rollbackExpectedDiskSha256 = null;

            try
            {
                using var documentLock = _document.LockDocument();
                EnsureActiveDocument();
                candidatePath = _exactBaseXrefPolicy.ValidateNativeEditCandidate(
                    request.DrawingFullPath,
                    database.Filename);
                drawingSha256Before = ComputeSha256(candidatePath);
                rollbackExpectedDiskSha256 = drawingSha256Before;
                dbmodBefore = Convert.ToInt32(ReadSystemNumber("DBMOD"));

                using (var transaction = _document.TransactionManager.StartTransaction())
                {
                    var modelSpaceId = GetModelSpaceId(database, transaction);
                    var targetLines = new Dictionary<string, Line>(StringComparer.OrdinalIgnoreCase);
                    before = ReadNativeLineObservations(
                        database,
                        transaction,
                        modelSpaceId,
                        request,
                        targetLines);
                    BoundedNativeLineEditPolicy.ValidateBeforeWrite(
                        request,
                        candidatePath,
                        candidatePath,
                        drawingSha256Before,
                        dbmodBefore,
                        before);

                    EnsureActiveDocument();
                    candidatePath = _exactBaseXrefPolicy.ValidateNativeEditCandidate(
                        request.DrawingFullPath,
                        database.Filename);
                    var freshSha256 = ComputeSha256(candidatePath);
                    var freshDbmod = Convert.ToInt32(ReadSystemNumber("DBMOD"));
                    BoundedNativeLineEditPolicy.ValidateBeforeWrite(
                        request,
                        candidatePath,
                        candidatePath,
                        freshSha256,
                        freshDbmod,
                        before);

                    mutationStarted = true;
                    foreach (var target in request.Targets)
                    {
                        var line = targetLines[target.Handle];
                        line.UpgradeOpen();
                        line.StartPoint = ToPoint3d(target.After.Start);
                        line.EndPoint = ToPoint3d(target.After.End);
                    }

                    var afterInTransaction = ReadNativeLineObservations(
                        database,
                        transaction,
                        modelSpaceId,
                        request,
                        targetLines: null);
                    BoundedNativeLineEditPolicy.ValidateReadback(
                        request,
                        before,
                        afterInTransaction);
                    transaction.Commit();
                    committed = true;
                }

                var activeAfterCommit = ReadNativeLineObservations(database, request);
                BoundedNativeLineEditPolicy.ValidateReadback(request, before, activeAfterCommit);

                EnsureActiveDocument();
                candidatePath = _exactBaseXrefPolicy.ValidateNativeEditCandidate(
                    request.DrawingFullPath,
                    database.Filename);
                if (!string.Equals(ComputeSha256(candidatePath), drawingSha256Before, StringComparison.Ordinal))
                {
                    var restored = TryRestoreNativeLineEditInMemory(
                        database,
                        request,
                        before,
                        out var restoreError);
                    var error = restored
                        ? "candidate disk SHA changed before save; in-memory edit was restored without overwriting the changed file"
                        : $"candidate disk SHA changed before save and in-memory rollback was not proven: {restoreError}";
                    return NativeLineEditFailure(
                        request,
                        drawingSha256Before,
                        TryComputeSha256(candidatePath),
                        BoundedNativeLineEditPolicy.ResolveDurableState(
                            saveCompleted: false,
                            savedReadbackMatches: false,
                            savedFileMatches: false,
                            databaseClean: false,
                            rollbackProven: false),
                        savePerformed: false,
                        before,
                        null,
                        new[] { $"DURABLE_STATE_UNCERTAIN: {error}" });
                }

                database.SaveAs(
                    candidatePath,
                    true,
                    DwgVersion.Current,
                    database.SecurityParameters);

                var drawingSha256After = ComputeSha256(candidatePath);
                rollbackExpectedDiskSha256 = drawingSha256After;
                var activeAfterSave = ReadNativeLineObservations(database, request);
                var reopenedAfterSave = ReadSavedNativeLineObservations(candidatePath, request);
                BoundedNativeLineEditPolicy.ValidateReadback(request, before, activeAfterSave);
                BoundedNativeLineEditPolicy.ValidateReadback(request, before, reopenedAfterSave);
                var dbmodAfter = Convert.ToInt32(ReadSystemNumber("DBMOD"));
                var durableState = BoundedNativeLineEditPolicy.ResolveDurableState(
                    saveCompleted: true,
                    savedReadbackMatches: true,
                    savedFileMatches: File.Exists(candidatePath)
                        && drawingSha256After != drawingSha256Before,
                    databaseClean: dbmodAfter == 0,
                    rollbackProven: false);
                if (durableState != "SAVED")
                {
                    throw new InvalidOperationException(
                        "saved candidate did not pass reopened-drawing SHA-256 and DBMOD checks");
                }

                return NativeLineEditSuccess(
                    request,
                    drawingSha256Before,
                    drawingSha256After,
                    before,
                    reopenedAfterSave);
            }
            catch (System.Exception exception)
            {
                if (!mutationStarted)
                {
                    return NativeLineEditFailure(
                        request,
                        drawingSha256Before,
                        TryComputeSha256(candidatePath),
                        "UNCHANGED",
                        savePerformed: false,
                        before,
                        before,
                        new[] { exception.Message });
                }

                if (!committed)
                {
                    var unchanged = TryVerifyNativeLineEditUnchanged(
                        database,
                        request,
                        candidatePath,
                        drawingSha256Before,
                        before,
                        out var unchangedError);
                    return NativeLineEditFailure(
                        request,
                        drawingSha256Before,
                        TryComputeSha256(candidatePath),
                        unchanged ? "UNCHANGED" : "UNCERTAIN",
                        savePerformed: false,
                        before,
                        unchanged ? before : null,
                        unchanged
                            ? new[] { exception.Message }
                            : new[]
                            {
                                $"DURABLE_STATE_UNCERTAIN: {exception.Message}; rollback verification failed: {unchangedError}"
                            });
                }

                string? rollbackSha256 = null;
                var rollbackError = "candidate path was unavailable";
                var rollbackPersisted = candidatePath is not null
                    && TryRestoreAndPersistNativeLineEdit(
                        database,
                        request,
                        candidatePath,
                        rollbackExpectedDiskSha256,
                        before,
                        out rollbackSha256,
                        out rollbackError);
                var rollbackState = BoundedNativeLineEditPolicy.ResolveDurableState(
                    saveCompleted: false,
                    savedReadbackMatches: false,
                    savedFileMatches: false,
                    databaseClean: false,
                    rollbackProven: rollbackPersisted);
                return NativeLineEditFailure(
                    request,
                    drawingSha256Before,
                    rollbackSha256 ?? TryComputeSha256(candidatePath),
                    rollbackState,
                    savePerformed: rollbackPersisted,
                    before,
                    rollbackPersisted ? before : null,
                    rollbackPersisted
                        ? new[] { $"native-line edit failed and was durably rolled back: {exception.Message}" }
                        : new[]
                        {
                            $"DURABLE_STATE_UNCERTAIN: {exception.Message}; rollback persistence was not proven: {rollbackError}"
                        });
            }
        }

        private void EnsureActiveDocument()
        {
            if (!ReferenceEquals(AcadApplication.DocumentManager.MdiActiveDocument, _document))
            {
                throw new InvalidOperationException("the active AutoCAD document changed during native-line edit");
            }
        }

        private static ObjectId GetModelSpaceId(Database database, Transaction transaction)
        {
            var blockTable = (BlockTable)transaction.GetObject(database.BlockTableId, OpenMode.ForRead);
            return blockTable[BlockTableRecord.ModelSpace];
        }

        private static NativeLineEditObservation[] ReadNativeLineObservations(
            Database database,
            Transaction transaction,
            ObjectId modelSpaceId,
            BoundedNativeLineEditRequest request,
            IDictionary<string, Line>? targetLines)
        {
            var targets = request.Targets
                .Select(target => target.Handle)
                .ToHashSet(StringComparer.OrdinalIgnoreCase);
            var handles = request.Targets.Select(target => target.Handle)
                .Concat(request.Protected.Select(entity => entity.Handle))
                .ToArray();
            if (handles.Distinct(StringComparer.OrdinalIgnoreCase).Count() != handles.Length)
            {
                throw new InvalidOperationException("target and protected handles must be unique and disjoint");
            }

            var observations = new List<NativeLineEditObservation>(handles.Length);
            foreach (var handleText in handles)
            {
                if (!TryParseHandle(handleText, out var handle))
                {
                    throw new InvalidOperationException($"native LINE handle '{handleText}' is invalid");
                }
                var objectId = database.GetObjectId(false, new Handle(handle), 0);
                if (objectId.IsNull
                    || transaction.GetObject(objectId, OpenMode.ForRead, false) is not Line line)
                {
                    throw new InvalidOperationException(
                        $"native entity '{handleText}' is missing or is not an AcDbLine");
                }

                var directModelSpace = line.OwnerId == modelSpaceId;
                var hasPersistentReactors = targets.Contains(handleText)
                    && line.GetPersistentReactorIds().Count > 0;
                observations.Add(new NativeLineEditObservation(
                    handleText.Trim().ToUpperInvariant(),
                    IsAcDbLine: true,
                    IsDirectModelSpace: directModelSpace,
                    HasSharedDefinitionReachability: !directModelSpace,
                    ToNativeLineGeometry(line),
                    HasPersistentReactors: hasPersistentReactors));
                if (targetLines is not null && targets.Contains(handleText))
                {
                    targetLines.Add(handleText, line);
                }
            }
            return observations.ToArray();
        }

        private static NativeLineEditObservation[] ReadNativeLineObservations(
            Database database,
            BoundedNativeLineEditRequest request)
        {
            using var transaction = database.TransactionManager.StartOpenCloseTransaction();
            var modelSpaceId = GetModelSpaceId(database, transaction);
            return ReadNativeLineObservations(
                database,
                transaction,
                modelSpaceId,
                request,
                targetLines: null);
        }

        private static NativeLineEditObservation[] ReadSavedNativeLineObservations(
            string drawingPath,
            BoundedNativeLineEditRequest request)
        {
            using var savedDatabase = new Database(false, true);
            savedDatabase.ReadDwgFile(
                drawingPath,
                FileOpenMode.OpenForReadAndAllShare,
                allowCPConversion: false,
                password: string.Empty);
            return ReadNativeLineObservations(savedDatabase, request);
        }

        private static NativeLineGeometry ToNativeLineGeometry(Line line) => new(
            [line.StartPoint.X, line.StartPoint.Y, line.StartPoint.Z],
            [line.EndPoint.X, line.EndPoint.Y, line.EndPoint.Z]);

        private static Point3d ToPoint3d(IReadOnlyList<double> coordinates)
        {
            if (coordinates.Count != 3 || coordinates.Any(value => !double.IsFinite(value)))
            {
                throw new InvalidOperationException("native LINE endpoint must contain three finite coordinates");
            }
            return new Point3d(coordinates[0], coordinates[1], coordinates[2]);
        }

        private bool TryVerifyNativeLineEditUnchanged(
            Database database,
            BoundedNativeLineEditRequest request,
            string? candidatePath,
            string drawingSha256Before,
            IReadOnlyCollection<NativeLineEditObservation> before,
            out string error)
        {
            error = string.Empty;
            if (candidatePath is null)
            {
                error = "candidate path was unavailable";
                return false;
            }
            try
            {
                using var documentLock = _document.LockDocument();
                EnsureActiveDocument();
                var canonicalCandidate = _exactBaseXrefPolicy.ValidateNativeEditCandidate(
                    request.DrawingFullPath,
                    database.Filename);
                if (!string.Equals(ComputeSha256(canonicalCandidate), drawingSha256Before, StringComparison.Ordinal)
                    || Convert.ToInt32(ReadSystemNumber("DBMOD")) != 0)
                {
                    error = "disk SHA or DBMOD no longer proves the pre-write state";
                    return false;
                }
                BoundedNativeLineEditPolicy.ValidateRollbackReadback(
                    request,
                    before,
                    ReadNativeLineObservations(database, request));
                return true;
            }
            catch (System.Exception exception)
            {
                error = exception.Message;
                return false;
            }
        }

        private bool TryRestoreNativeLineEditInMemory(
            Database database,
            BoundedNativeLineEditRequest request,
            IReadOnlyCollection<NativeLineEditObservation> before,
            out string error)
        {
            error = string.Empty;
            try
            {
                using var transaction = _document.TransactionManager.StartTransaction();
                var modelSpaceId = GetModelSpaceId(database, transaction);
                var targetLines = new Dictionary<string, Line>(StringComparer.OrdinalIgnoreCase);
                _ = ReadNativeLineObservations(
                    database,
                    transaction,
                    modelSpaceId,
                    request,
                    targetLines);
                var beforeByHandle = before.ToDictionary(
                    observation => observation.Handle,
                    StringComparer.OrdinalIgnoreCase);
                foreach (var target in request.Targets)
                {
                    if (!beforeByHandle.TryGetValue(target.Handle, out var original))
                    {
                        throw new InvalidOperationException($"pre-write LINE {target.Handle} was not captured");
                    }
                    var line = targetLines[target.Handle];
                    line.UpgradeOpen();
                    line.StartPoint = ToPoint3d(original.Geometry.Start);
                    line.EndPoint = ToPoint3d(original.Geometry.End);
                }

                var restored = ReadNativeLineObservations(
                    database,
                    transaction,
                    modelSpaceId,
                    request,
                    targetLines: null);
                BoundedNativeLineEditPolicy.ValidateRollbackReadback(request, before, restored);
                transaction.Commit();
                return true;
            }
            catch (System.Exception exception)
            {
                error = exception.Message;
                return false;
            }
        }

        private bool TryRestoreAndPersistNativeLineEdit(
            Database database,
            BoundedNativeLineEditRequest request,
            string candidatePath,
            string? expectedDiskSha256,
            IReadOnlyCollection<NativeLineEditObservation> before,
            out string? drawingSha256After,
            out string error)
        {
            drawingSha256After = null;
            error = string.Empty;
            try
            {
                using var documentLock = _document.LockDocument();
                EnsureActiveDocument();
                var canonicalCandidate = _exactBaseXrefPolicy.ValidateNativeEditCandidate(
                    request.DrawingFullPath,
                    database.Filename);
                if (!StringComparer.OrdinalIgnoreCase.Equals(canonicalCandidate, candidatePath))
                {
                    throw new InvalidOperationException("candidate identity changed before rollback persistence");
                }
                if (!TryRestoreNativeLineEditInMemory(database, request, before, out error))
                {
                    return false;
                }

                var rollbackPersisted = BoundedNativeLineEditPolicy.TryPersistRollbackIfDiskCurrent(
                    expectedDiskSha256 ?? string.Empty,
                    ComputeSha256(canonicalCandidate),
                    () => database.SaveAs(
                        canonicalCandidate,
                        true,
                        DwgVersion.Current,
                        database.SecurityParameters));
                if (!rollbackPersisted)
                {
                    throw new InvalidOperationException(
                        string.IsNullOrWhiteSpace(expectedDiskSha256)
                            ? "no trusted candidate disk SHA was captured before rollback persistence"
                            : "candidate disk SHA changed before rollback persistence");
                }
                drawingSha256After = ComputeSha256(canonicalCandidate);
                var reopened = ReadSavedNativeLineObservations(canonicalCandidate, request);
                BoundedNativeLineEditPolicy.ValidateRollbackReadback(request, before, reopened);
                if (Convert.ToInt32(ReadSystemNumber("DBMOD")) != 0)
                {
                    throw new InvalidOperationException("DBMOD is not zero after rollback save");
                }
                return true;
            }
            catch (System.Exception exception)
            {
                error = string.IsNullOrEmpty(error) ? exception.Message : $"{error}; {exception.Message}";
                return false;
            }
        }

        private static BoundedNativeLineEditSnapshot NativeLineEditSuccess(
            BoundedNativeLineEditRequest request,
            string drawingSha256Before,
            string drawingSha256After,
            IReadOnlyCollection<NativeLineEditObservation> before,
            IReadOnlyCollection<NativeLineEditObservation> after)
        {
            var beforeByHandle = before.ToDictionary(
                observation => observation.Handle,
                StringComparer.OrdinalIgnoreCase);
            var afterByHandle = after.ToDictionary(
                observation => observation.Handle,
                StringComparer.OrdinalIgnoreCase);
            var targetStates = request.Targets
                .Select(target => new BoundedNativeLineEditState(
                    target.Handle,
                    CloneGeometry(beforeByHandle[target.Handle].Geometry),
                    CloneGeometry(afterByHandle[target.Handle].Geometry)))
                .ToArray();
            var protectedStates = request.Protected
                .Select(entity => new BoundedNativeLineEditState(
                    entity.Handle,
                    CloneGeometry(beforeByHandle[entity.Handle].Geometry),
                    CloneGeometry(afterByHandle[entity.Handle].Geometry)))
                .ToArray();
            return new BoundedNativeLineEditSnapshot(
                true,
                "SAVED",
                true,
                drawingSha256Before,
                drawingSha256After,
                targetStates,
                protectedStates,
                Array.Empty<string>(),
                Array.Empty<string>());
        }

        private static BoundedNativeLineEditSnapshot NativeLineEditFailure(
            BoundedNativeLineEditRequest request,
            string? drawingSha256Before,
            string? drawingSha256After,
            string durableState,
            bool savePerformed,
            IReadOnlyCollection<NativeLineEditObservation> before,
            IReadOnlyCollection<NativeLineEditObservation>? after,
            IReadOnlyList<string> errors)
        {
            var beforeByHandle = before
                .GroupBy(observation => observation.Handle, StringComparer.OrdinalIgnoreCase)
                .Where(group => group.Count() == 1)
                .ToDictionary(group => group.Key, group => group.Single(), StringComparer.OrdinalIgnoreCase);
            var afterByHandle = (after ?? Array.Empty<NativeLineEditObservation>())
                .GroupBy(observation => observation.Handle, StringComparer.OrdinalIgnoreCase)
                .Where(group => group.Count() == 1)
                .ToDictionary(group => group.Key, group => group.Single(), StringComparer.OrdinalIgnoreCase);
            NativeLineGeometry BeforeFor(string handle, NativeLineGeometry fallback) =>
                CloneGeometry(beforeByHandle.TryGetValue(handle, out var original)
                    ? original.Geometry
                    : fallback);
            NativeLineGeometry AfterFor(string handle, NativeLineGeometry fallback) =>
                CloneGeometry(afterByHandle.TryGetValue(handle, out var observed)
                    ? observed.Geometry
                    : beforeByHandle.TryGetValue(handle, out var original)
                        ? original.Geometry
                        : fallback);
            var targetStates = request.Targets
                .Select(target => new BoundedNativeLineEditState(
                    target.Handle,
                    BeforeFor(target.Handle, target.Before),
                    AfterFor(target.Handle, target.Before)))
                .ToArray();
            var protectedStates = request.Protected
                .Select(entity => new BoundedNativeLineEditState(
                    entity.Handle,
                    BeforeFor(entity.Handle, entity.Before),
                    AfterFor(entity.Handle, entity.Before)))
                .ToArray();
            return new BoundedNativeLineEditSnapshot(
                false,
                durableState,
                savePerformed,
                drawingSha256Before ?? string.Empty,
                drawingSha256After,
                targetStates,
                protectedStates,
                Array.Empty<string>(),
                errors);
        }

        private static NativeLineGeometry CloneGeometry(NativeLineGeometry geometry) =>
            new((double[])geometry.Start.Clone(), (double[])geometry.End.Clone());

        private static string ComputeSha256(string path)
        {
            using var stream = new FileStream(
                path,
                FileMode.Open,
                FileAccess.Read,
                FileShare.ReadWrite | FileShare.Delete);
            return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
        }

        private static string? TryComputeSha256(string? path)
        {
            if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            {
                return null;
            }
            try
            {
                return ComputeSha256(path);
            }
            catch (System.Exception)
            {
                return null;
            }
        }

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
