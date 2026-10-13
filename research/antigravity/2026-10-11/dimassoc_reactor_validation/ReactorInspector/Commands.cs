using System;
using System.IO;
using System.Collections.Generic;
using Autodesk.AutoCAD.Runtime;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.ApplicationServices;

namespace ReactorInspector;

public enum LineReactorClassification
{
    NoReactor,
    KnownDimAssocReactor,
    UnknownOtherReactor,
    MixedReactors
}

public class Commands
{
    private static string LogPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "inspection_result.txt");

    public static void SetLogPath(string path)
    {
        LogPath = path;
    }

    private static void Log(string msg)
    {
        try
        {
            File.AppendAllText(LogPath, msg + "\n");
        }
        catch
        {
            // fallback
        }
        var doc = Application.DocumentManager.MdiActiveDocument;
        doc?.Editor?.WriteMessage("\n" + msg);
    }

    [CommandMethod("INSPECT_DIFFERENTIAL")]
    public static void InspectDifferential()
    {
        string? customLog = Environment.GetEnvironmentVariable("REACTOR_INSPECTOR_LOG");
        if (!string.IsNullOrEmpty(customLog))
        {
            LogPath = customLog;
        }

        File.WriteAllText(LogPath, "### DIFFERENTIAL MANAGED OBJECT GRAPH LOG ###\n\n");

        string baseDir = AppDomain.CurrentDomain.BaseDirectory;
        string fixtureA = Environment.GetEnvironmentVariable("FIXTURE_A_PATH") 
            ?? Path.Combine(baseDir, "fixture_a_dimassoc1.dwg");
        string fixtureB = Environment.GetEnvironmentVariable("FIXTURE_B_PATH") 
            ?? Path.Combine(baseDir, "fixture_b_dimassoc2.dwg");

        Log("#################################################################");
        Log("### STARTING DIFFERENTIAL MANAGED OBJECT GRAPH INSPECTION ###");
        Log("#################################################################\n");

        InspectFixture("FIXTURE_A (DIMASSOC=1)", fixtureA);
        InspectFixture("FIXTURE_B (DIMASSOC=2)", fixtureB);

        RunOracleAdversarialTests(fixtureA, fixtureB);

        Log("#################################################################");
        Log("### DIFFERENTIAL INSPECTION FINISHED ###");
        Log("#################################################################\n");
    }

    public static LineReactorClassification ClassifyReactorCollection(
        ObjectIdCollection? reactorIds,
        out List<ObjectId> dimAssocReactors,
        out List<ObjectId> otherReactors)
    {
        dimAssocReactors = new List<ObjectId>();
        otherReactors = new List<ObjectId>();

        if (reactorIds == null || reactorIds.Count == 0)
        {
            return LineReactorClassification.NoReactor;
        }

        foreach (ObjectId id in reactorIds)
        {
            if (!id.IsValid) continue;
            if (string.Equals(id.ObjectClass.DxfName, "DIMASSOC", StringComparison.OrdinalIgnoreCase))
            {
                dimAssocReactors.Add(id);
            }
            else
            {
                otherReactors.Add(id);
            }
        }

        if (dimAssocReactors.Count > 0 && otherReactors.Count == 0)
        {
            return LineReactorClassification.KnownDimAssocReactor;
        }
        if (dimAssocReactors.Count == 0 && otherReactors.Count > 0)
        {
            return LineReactorClassification.UnknownOtherReactor;
        }
        if (dimAssocReactors.Count > 0 && otherReactors.Count > 0)
        {
            return LineReactorClassification.MixedReactors;
        }

        return LineReactorClassification.NoReactor;
    }

    public static void RunOracleAdversarialTests(string fixtureAPath, string fixtureBPath)
    {
        Log("\n=================================================================");
        Log("### RUNNING ORACLE ADVERSARIAL TESTS (CONTROLS 1..4) ###");
        Log("=================================================================");

        // Load Fixture B to get exact real DIMASSOC and Other ObjectIds
        using var dbB = new Database(false, true);
        dbB.ReadDwgFile(fixtureBPath, FileOpenMode.OpenForReadAndAllShare, false, string.Empty);
        using var trB = dbB.TransactionManager.StartTransaction();
        var btB = (BlockTable)trB.GetObject(dbB.BlockTableId, OpenMode.ForRead);
        var msB = (BlockTableRecord)trB.GetObject(btB[BlockTableRecord.ModelSpace], OpenMode.ForRead);

        Line? lineB = null;
        Dimension? dimB = null;
        foreach (ObjectId id in msB)
        {
            var ent = trB.GetObject(id, OpenMode.ForRead);
            if (ent is Line l) lineB = l;
            if (ent is Dimension d) dimB = d;
        }

        if (lineB == null || dimB == null)
        {
            Log("ERROR: Line or Dimension not found in Fixture B!");
            return;
        }

        var realDimAssocReactors = lineB.GetPersistentReactorIds();
        ObjectId realDimAssocId = realDimAssocReactors[0];
        ObjectId realOtherId = dimB.ObjectId; // A valid ObjectId whose DxfName is "DIMENSION", not "DIMASSOC"

        // CONTROL 1: No reactors
        var col1 = new ObjectIdCollection();
        var res1 = ClassifyReactorCollection(col1, out var da1, out var ot1);
        Log($"CONTROL_1 (No reactors): Result={res1} (Expected={LineReactorClassification.NoReactor}) -> PASS={res1 == LineReactorClassification.NoReactor}");

        // CONTROL 2: Exact DIMASSOC reactor only
        var col2 = new ObjectIdCollection { realDimAssocId };
        var res2 = ClassifyReactorCollection(col2, out var da2, out var ot2);
        Log($"CONTROL_2 (DIMASSOC reactor): Result={res2} (Expected={LineReactorClassification.KnownDimAssocReactor}) -> PASS={res2 == LineReactorClassification.KnownDimAssocReactor}");
        Log($"   Observed DxfName={da2[0].ObjectClass.DxfName}, ClassName={da2[0].ObjectClass.Name}");

        // CONTROL 3: Unrelated persistent reactor only (DxfName != "DIMASSOC")
        var col3 = new ObjectIdCollection { realOtherId };
        var res3 = ClassifyReactorCollection(col3, out var da3, out var ot3);
        Log($"CONTROL_3 (Unrelated persistent reactor): Result={res3} (Expected={LineReactorClassification.UnknownOtherReactor}) -> PASS={res3 == LineReactorClassification.UnknownOtherReactor}");
        Log($"   Observed DxfName={ot3[0].ObjectClass.DxfName}, ClassName={ot3[0].ObjectClass.Name}");

        // CONTROL 4: Multiple reactors including DIMASSOC and an unrelated reactor
        var col4 = new ObjectIdCollection { realDimAssocId, realOtherId };
        var res4 = ClassifyReactorCollection(col4, out var da4, out var ot4);
        Log($"CONTROL_4 (Multiple mixed reactors): Result={res4} (Expected={LineReactorClassification.MixedReactors}) -> PASS={res4 == LineReactorClassification.MixedReactors}");
        Log($"   DIMASSOC count={da4.Count}, Other count={ot4.Count}");

        // PROVING EXACT DIMENSION <-> LINE PAIRING
        Log("\n--- PROVING EXACT DIMENSION <-> LINE ASSOCIATION PAIRING ---");
        var dimBReactors = dimB.GetPersistentReactorIds();
        bool dimSharesReactor = dimBReactors != null && dimBReactors.Contains(realDimAssocId);
        Log($"1. Dimension {dimB.Handle} GetPersistentReactorIds() contains shared reactor {realDimAssocId}: {dimSharesReactor}");

        ObjectId extDictId = dimB.ExtensionDictionary;
        var extDict = (DBDictionary)trB.GetObject(extDictId, OpenMode.ForRead);
        bool dictContainsDimAssoc = extDict.Contains("ACAD_DIMASSOC");
        ObjectId dictValId = extDict.GetAt("ACAD_DIMASSOC");
        bool dictPointsToSame = (dictValId == realDimAssocId);
        Log($"2. Dimension ExtensionDictionary has 'ACAD_DIMASSOC' pointing to exact shared reactor {realDimAssocId}: {dictPointsToSame}");

        // Check the AcDbDimAssoc object itself
        var dimAssocObj = trB.GetObject(realDimAssocId, OpenMode.ForRead);
        Log($"3. AcDbDimAssoc Object OwnerId: {dimAssocObj.OwnerId} (Matches Dimension ExtensionDictId {extDictId}: {dimAssocObj.OwnerId == extDictId})");

        trB.Commit();
    }

    private static void InspectFixture(string label, string path)
    {
        Log("=================================================================");
        Log($"FIXTURE: {label}");
        Log($"PATH: {path}");
        Log("=================================================================");

        if (!File.Exists(path))
        {
            Log("ERROR: File not found!");
            return;
        }

        using var db = new Database(false, true);
        db.ReadDwgFile(path, FileOpenMode.OpenForReadAndAllShare, false, string.Empty);

        using var tr = db.TransactionManager.StartTransaction();
        var bt = (BlockTable)tr.GetObject(db.BlockTableId, OpenMode.ForRead);
        var ms = (BlockTableRecord)tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForRead);

        foreach (ObjectId id in ms)
        {
            var entity = (Entity)tr.GetObject(id, OpenMode.ForRead);
            string typeName = entity.GetType().Name;
            string dxfName = id.ObjectClass.DxfName;
            string className = id.ObjectClass.Name;
            string handle = entity.Handle.ToString();

            Log($"\n--- ENTITY: {typeName} ---");
            Log($"  HANDLE: {handle}");
            Log($"  OBJECT_ID: {id}");
            Log($"  OBJECT_CLASS: {className}");
            Log($"  DXF_NAME: {dxfName}");

            var reactorIds = entity.GetPersistentReactorIds();
            int reactorCount = reactorIds == null ? 0 : reactorIds.Count;
            Log($"  HAS_PERSISTENT_REACTOR_COUNT: {reactorCount}");

            if (reactorIds != null && reactorIds.Count > 0)
            {
                foreach (ObjectId rId in reactorIds)
                {
                    bool hasSpecificReactor = entity.HasPersistentReactor(rId);
                    Log($"  -> PERSISTENT_REACTOR_ID: {rId}");
                    Log($"     HAS_THIS_REACTOR: {hasSpecificReactor}");
                    if (rId.IsValid)
                    {
                        var rObj = tr.GetObject(rId, OpenMode.ForRead, false);
                        Log($"     REACTOR_CLASS_NAME: {rId.ObjectClass.Name}");
                        Log($"     REACTOR_DXF_NAME: {rId.ObjectClass.DxfName}");
                        Log($"     REACTOR_OWNER_ID: {rObj.OwnerId}");
                        Log($"     REACTOR_IS_ERASED: {rObj.IsErased}");
                        Log($"     REACTOR_PROXY_STATUS: {rObj.IsAProxy}");
                        Log($"     REACTOR_HANDLE: {rObj.Handle}");
                    }
                    else
                    {
                        Log("     REACTOR_IS_VALID: FALSE");
                    }
                }
            }

            ObjectId extDictId = entity.ExtensionDictionary;
            Log($"  EXTENSION_DICTIONARY_ID: {extDictId}");
            if (!extDictId.IsNull && extDictId.IsValid)
            {
                var extDict = (DBDictionary)tr.GetObject(extDictId, OpenMode.ForRead);
                Log($"  EXTENSION_DICTIONARY_COUNT: {extDict.Count}");
                foreach (DBDictionaryEntry entry in extDict)
                {
                    Log($"     KEY: \"{entry.Key}\" -> VALUE_OBJECT_ID: {entry.Value}");
                    if (entry.Value.IsValid)
                    {
                        var valObj = tr.GetObject(entry.Value, OpenMode.ForRead, false);
                        Log($"         VALUE_CLASS_NAME: {entry.Value.ObjectClass.Name}");
                        Log($"         VALUE_DXF_NAME: {entry.Value.ObjectClass.DxfName}");
                        Log($"         VALUE_HANDLE: {valObj.Handle}");
                    }
                }
            }
            else
            {
                Log("  EXTENSION_DICTIONARY_KEYS: NONE");
            }

            if (entity is Dimension dim)
            {
                Log($"  DIMENSION_MEASUREMENT: {dim.Measurement}");
                Log($"  DIMENSION_TEXT: \"{dim.DimensionText}\"");
                Log($"  DIMENSION_BLOCK_ID: {dim.DimBlockId}");
            }
            else if (entity is Line line)
            {
                Log($"  LINE_START: {line.StartPoint}");
                Log($"  LINE_END: {line.EndPoint}");
                Log($"  LINE_LENGTH: {line.Length}");
            }
        }

        tr.Commit();
    }
}
