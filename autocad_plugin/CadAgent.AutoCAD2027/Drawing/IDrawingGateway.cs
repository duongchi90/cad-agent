using CadAgent.AutoCAD2027.Review;
using CadAgent.AutoCAD2027.DrawingSetup;

namespace CadAgent.AutoCAD2027.Drawing;

public interface IDrawingGateway
{
    string? ActiveDocumentFullPath { get; }

    IReadOnlyList<EntitySnapshot> ReadEntities(IReadOnlyCollection<string> handles);

    DrawingSetupSnapshot ReadDrawingSetup();

    VisualEvidenceSnapshot ReadVisualEvidence(VisualEvidenceRequest request);

    NativeRenderEvidenceSnapshot ReadNativeRenderEvidence(NativeRenderRequest request);

    ExactBaseXrefInspectionSnapshot ReadExactBaseXrefInspection(
        ExactBaseXrefInspectionParameters request) =>
        throw new InvalidOperationException(
            "This drawing gateway does not provide the live exact-base Xref inspection operation.");
}
