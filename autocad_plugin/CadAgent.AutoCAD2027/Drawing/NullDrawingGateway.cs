using CadAgent.AutoCAD2027.Review;

namespace CadAgent.AutoCAD2027.Drawing;

public sealed class NullDrawingGateway : IDrawingGateway
{
    public string? ActiveDocumentFullPath => null;

    public IReadOnlyList<EntitySnapshot> ReadEntities(IReadOnlyCollection<string> handles)
    {
        ArgumentNullException.ThrowIfNull(handles);
        return Array.Empty<EntitySnapshot>();
    }
}
