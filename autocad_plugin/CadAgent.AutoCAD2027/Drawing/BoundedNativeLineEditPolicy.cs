using CadAgent.AutoCAD2027.Ipc;

namespace CadAgent.AutoCAD2027.Drawing;

internal sealed record NativeLineEditObservation(
    string Handle,
    bool IsAcDbLine,
    bool IsDirectModelSpace,
    bool HasSharedDefinitionReachability,
    NativeLineGeometry Geometry,
    bool HasPersistentReactors = false);

internal static class BoundedNativeLineEditPolicy
{
    internal const double EndpointTolerance = ContractValidator.NativeLineEndpointTolerance;

    internal static void ValidateBeforeWrite(
        BoundedNativeLineEditRequest request,
        string candidatePath,
        string activeDocumentPath,
        string diskSha256,
        int dbmod,
        IReadOnlyCollection<NativeLineEditObservation> observations)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentNullException.ThrowIfNull(observations);
        if (!StringComparer.OrdinalIgnoreCase.Equals(candidatePath, activeDocumentPath))
        {
            throw new InvalidOperationException("active AutoCAD document is not the disposable candidate");
        }
        if (!string.Equals(request.DrawingSha256, diskSha256, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("fresh candidate disk SHA-256 does not match the request");
        }
        if (dbmod != 0)
        {
            throw new InvalidOperationException("active candidate DBMOD must be zero immediately before mutation");
        }

        var targetHandles = request.Targets
            .Select(target => target.Handle)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
        if (targetHandles.Count != request.Targets.Count
            || request.Protected.Select(entity => entity.Handle).Any(targetHandles.Contains))
        {
            throw new InvalidOperationException("target and protected native-line handles must be unique and disjoint");
        }

        var expectedCount = request.Targets.Count + request.Protected.Count;
        var byHandle = IndexObservations(observations);
        if (byHandle.Count != expectedCount)
        {
            throw new InvalidOperationException("could not resolve exactly the requested native-line handles");
        }

        foreach (var target in request.Targets)
        {
            var observed = RequireTargetLine(byHandle, target.Handle);
            if (!GeometryMatches(observed.Geometry, target.Before))
            {
                throw new InvalidOperationException(
                    $"target LINE {target.Handle} no longer matches its expected-before endpoints");
            }
        }
        foreach (var protectedEntity in request.Protected)
        {
            var observed = RequireDirectModelSpaceLine(byHandle, protectedEntity.Handle);
            if (!GeometryMatches(observed.Geometry, protectedEntity.Before))
            {
                throw new InvalidOperationException(
                    $"protected LINE {protectedEntity.Handle} no longer matches its expected-before endpoints");
            }
        }
    }

    internal static void ValidateReadback(
        BoundedNativeLineEditRequest request,
        IReadOnlyCollection<NativeLineEditObservation> before,
        IReadOnlyCollection<NativeLineEditObservation> after)
    {
        ArgumentNullException.ThrowIfNull(request);
        var beforeByHandle = IndexObservations(before);
        var afterByHandle = IndexObservations(after);
        if (beforeByHandle.Count != request.Targets.Count + request.Protected.Count
            || afterByHandle.Count != beforeByHandle.Count)
        {
            throw new InvalidOperationException("native-line readback did not resolve the exact authorized handle set");
        }

        foreach (var target in request.Targets)
        {
            _ = RequireTargetLine(beforeByHandle, target.Handle);
            var readback = RequireTargetLine(afterByHandle, target.Handle);
            if (!GeometryMatches(readback.Geometry, target.After))
            {
                throw new InvalidOperationException(
                    $"target LINE {target.Handle} readback does not match the requested after-state");
            }
        }
        foreach (var protectedEntity in request.Protected)
        {
            var original = RequireDirectModelSpaceLine(beforeByHandle, protectedEntity.Handle);
            var readback = RequireDirectModelSpaceLine(afterByHandle, protectedEntity.Handle);
            if (!GeometryMatches(original.Geometry, protectedEntity.Before)
                || !GeometryMatches(readback.Geometry, original.Geometry))
            {
                throw new InvalidOperationException(
                    $"protected LINE {protectedEntity.Handle} changed during native-line edit");
            }
        }
    }

    internal static void ValidateRollbackReadback(
        BoundedNativeLineEditRequest request,
        IReadOnlyCollection<NativeLineEditObservation> before,
        IReadOnlyCollection<NativeLineEditObservation> after)
    {
        ArgumentNullException.ThrowIfNull(request);
        var beforeByHandle = IndexObservations(before);
        var afterByHandle = IndexObservations(after);
        if (beforeByHandle.Count != request.Targets.Count + request.Protected.Count
            || afterByHandle.Count != beforeByHandle.Count)
        {
            throw new InvalidOperationException("rollback readback did not resolve the exact authorized handle set");
        }

        foreach (var target in request.Targets)
        {
            var original = RequireTargetLine(beforeByHandle, target.Handle);
            var restored = RequireTargetLine(afterByHandle, target.Handle);
            if (!GeometryMatches(original.Geometry, target.Before)
                || !GeometryMatches(restored.Geometry, original.Geometry))
            {
                throw new InvalidOperationException($"target LINE {target.Handle} rollback was not proven");
            }
        }
        foreach (var protectedEntity in request.Protected)
        {
            var original = RequireDirectModelSpaceLine(beforeByHandle, protectedEntity.Handle);
            var restored = RequireDirectModelSpaceLine(afterByHandle, protectedEntity.Handle);
            if (!GeometryMatches(original.Geometry, protectedEntity.Before)
                || !GeometryMatches(restored.Geometry, original.Geometry))
            {
                throw new InvalidOperationException($"protected LINE {protectedEntity.Handle} changed during rollback");
            }
        }
    }

    internal static string ResolveDurableState(
        bool saveCompleted,
        bool savedReadbackMatches,
        bool savedFileMatches,
        bool databaseClean,
        bool rollbackProven) =>
        saveCompleted && savedReadbackMatches && savedFileMatches && databaseClean
            ? "SAVED"
            : rollbackProven
                ? "ROLLED_BACK"
                : "UNCERTAIN";

    internal static bool GeometryMatches(NativeLineGeometry actual, NativeLineGeometry expected) =>
        PointMatches(actual.Start, expected.Start)
        && PointMatches(actual.End, expected.End);

    private static Dictionary<string, NativeLineEditObservation> IndexObservations(
        IEnumerable<NativeLineEditObservation> observations)
    {
        var result = new Dictionary<string, NativeLineEditObservation>(StringComparer.OrdinalIgnoreCase);
        foreach (var observation in observations)
        {
            if (string.IsNullOrWhiteSpace(observation.Handle)
                || !result.TryAdd(observation.Handle, observation))
            {
                throw new InvalidOperationException("native-line observations contain a missing or duplicate handle");
            }
        }
        return result;
    }

    private static NativeLineEditObservation RequireDirectModelSpaceLine(
        IReadOnlyDictionary<string, NativeLineEditObservation> observations,
        string handle)
    {
        if (!observations.TryGetValue(handle, out var observation))
        {
            throw new InvalidOperationException($"native LINE handle {handle} was not found");
        }
        if (!observation.IsAcDbLine
            || !observation.IsDirectModelSpace
            || observation.HasSharedDefinitionReachability)
        {
            throw new InvalidOperationException(
                $"native entity {handle} is not an isolated direct ModelSpace AcDbLine");
        }
        return observation;
    }

    private static NativeLineEditObservation RequireTargetLine(
        IReadOnlyDictionary<string, NativeLineEditObservation> observations,
        string handle)
    {
        var observation = RequireDirectModelSpaceLine(observations, handle);
        if (observation.HasPersistentReactors)
        {
            throw new InvalidOperationException(
                $"target LINE {handle} has persistent reactors; bounded native edit cannot prove associated state remains unchanged");
        }
        return observation;
    }

    private static bool PointMatches(IReadOnlyList<double> actual, IReadOnlyList<double> expected)
    {
        if (actual.Count != 3 || expected.Count != 3)
        {
            return false;
        }
        for (var index = 0; index < 3; index++)
        {
            if (!double.IsFinite(actual[index])
                || !double.IsFinite(expected[index])
                || Math.Abs(actual[index] - expected[index]) > EndpointTolerance)
            {
                return false;
            }
        }
        return true;
    }
}
