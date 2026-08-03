using CadAgent.AutoCAD2027.Review;

namespace CadAgent.AutoCAD2027.Drawing;

public interface IDrawingGateway
{
    string? ActiveDocumentFullPath { get; }

    IReadOnlyList<EntitySnapshot> ReadEntities(IReadOnlyCollection<string> handles);

    DrawingSetupSnapshot ReadDrawingSetup() =>
        throw new NotSupportedException("Drawing setup audit is not supported by this gateway.");
}
