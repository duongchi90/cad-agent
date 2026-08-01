using System.Globalization;
using System.Text.Json;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Geometry;
using CadAgent.AutoCAD2027.Drawing;
using CadAgent.AutoCAD2027.Ipc;
using CadAgent.AutoCAD2027.Mechanical;
using CadAgent.AutoCAD2027.Review;
using AcadApplication = Autodesk.AutoCAD.ApplicationServices.Application;

namespace CadAgent.AutoCAD2027.Commands;

public sealed class CommandContext
{
    public const string IpcDirectoryEnvironmentVariable = "CAD_AGENT_DOTNET_IPC_DIR";
    public const string DefaultIpcDirectory = @"C:\temp";

    public CommandContext(
        JsonFileStore store,
        IDrawingGateway drawingGateway,
        Action closeWithoutSaving,
        Action<string>? report = null,
        Func<DateTimeOffset>? clock = null,
        IMechanicalAdapter? mechanicalAdapter = null)
    {
        Store = store ?? throw new ArgumentNullException(nameof(store));
        DrawingGateway = drawingGateway ?? throw new ArgumentNullException(nameof(drawingGateway));
        CloseWithoutSaving = closeWithoutSaving ?? throw new ArgumentNullException(nameof(closeWithoutSaving));
        Report = report ?? (_ => { });
        Clock = clock ?? (() => DateTimeOffset.UtcNow);
        MechanicalAdapter = mechanicalAdapter ?? new NoOpMechanicalAdapter();
    }

    public JsonFileStore Store { get; }

    public IDrawingGateway DrawingGateway { get; }

    public IMechanicalAdapter MechanicalAdapter { get; }

    public Action CloseWithoutSaving { get; }

    public Action<string> Report { get; }

    public Func<DateTimeOffset> Clock { get; }

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
        var gateway = new AutoCadDrawingGateway(document);
        var ipcDirectory = Environment.GetEnvironmentVariable(IpcDirectoryEnvironmentVariable);
        var store = new JsonFileStore(
            string.IsNullOrWhiteSpace(ipcDirectory) ? DefaultIpcDirectory : ipcDirectory);
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
            mechanicalAdapter: new ManagedMechanicalAdapter(gateway));
    }

    private sealed class AutoCadDrawingGateway : IDrawingGateway, IMechanicalDrawingGateway
    {
        private readonly Document _document;

        public AutoCadDrawingGateway(Document document)
        {
            _document = document ?? throw new ArgumentNullException(nameof(document));
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
                        catch (System.Exception)
                        {
                            // An unreadable direct attribute does not make the insert unreadable.
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
                catch (System.Exception)
                {
                    // Skip an unreadable direct ModelSpace insert and continue the read-only scan.
                }
            }

            return snapshots
                .OrderBy(snapshot => snapshot.Handle, StringComparer.Ordinal)
                .ToArray();
        }

        private static string NormalizeMechanicalTag(string? tag) =>
            (tag ?? string.Empty).Trim().ToUpperInvariant();

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
