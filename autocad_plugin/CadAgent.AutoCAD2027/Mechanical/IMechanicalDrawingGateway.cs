namespace CadAgent.AutoCAD2027.Mechanical;

public interface IMechanicalDrawingGateway
{
    IReadOnlyList<MechanicalComponentSnapshot> ReadMechanicalComponents();
}
