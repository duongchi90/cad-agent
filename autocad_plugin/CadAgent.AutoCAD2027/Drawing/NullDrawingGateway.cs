using CadAgent.AutoCAD2027.Review;
using CadAgent.AutoCAD2027.DrawingSetup;

namespace CadAgent.AutoCAD2027.Drawing;

public sealed class NullDrawingGateway : IDrawingGateway
{
    public string? ActiveDocumentFullPath => null;

    public IReadOnlyList<EntitySnapshot> ReadEntities(IReadOnlyCollection<string> handles)
    {
        ArgumentNullException.ThrowIfNull(handles);
        return Array.Empty<EntitySnapshot>();
    }

    public DrawingSetupSnapshot ReadDrawingSetup() =>
        throw new InvalidOperationException("No active drawing is available for setup audit.");

    public VisualEvidenceSnapshot ReadVisualEvidence(VisualEvidenceRequest request) =>
        throw new InvalidOperationException("No active drawing is available for visual evidence export.");
}
