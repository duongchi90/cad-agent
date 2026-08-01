# Task 3 Report — Mechanical Capability Boundary

## Status

NEEDS_CONTEXT: The Mechanical boundary and dependency-free assertions are implemented and compile, but the required `dotnet test` command cannot execute because the unchanged test project has no test SDK/package references and the generated testhost dependency is missing `testhost.dll`. No project-file change was made because project files are outside the T03 write-set.

## Commits

- Scoped task commit: pending at report creation; the final SHA is returned in the task handoff.

## Changed files

- `autocad_plugin/CadAgent.AutoCAD2027/Mechanical/IMechanicalAdapter.cs`
- `autocad_plugin/CadAgent.AutoCAD2027/Mechanical/MechanicalModels.cs`
- `autocad_plugin/CadAgent.AutoCAD2027/Mechanical/NoOpMechanicalAdapter.cs`
- `autocad_plugin/CadAgent.AutoCAD2027.Tests/Mechanical/NoOpMechanicalAdapterTests.cs`
- `.superpowers/sdd/2026-08-01-autocad-dotnet-plugin-option-a/task-3-report.md`

The production boundary exposes `IMechanicalAdapter`, `MechanicalCapabilityResult`, `MechanicalOperationRequest`, and `MechanicalOperationResult`. `NoOpMechanicalAdapter` is unavailable, reports zero supported operations, returns `not_supported`, preserves the requested operation name, and performs no drawing or Mechanical mutation.

## Tests and results

- RED phase: `dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64` failed as expected before implementation with `CS0234`: the `CadAgent.AutoCAD2027.Mechanical` namespace did not exist.
- Compile verification: `dotnet build autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64 -v:q` passed with exit code 0, 0 errors, and 3 existing `MSB3277` reference-conflict warnings.
- Required focused test: `dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64` restored and built both projects, then exited with code 1 when the testhost aborted: `testhost.deps.json` requires package `testhost` version `18.6.0-release-26270-133`, but `testhost.dll` was not found. Therefore no discovered test count is claimed.
- The dependency-free test source contains four assertions for unavailable state, zero supported operations, `not_supported`, and operation-name preservation; the runner infrastructure prevented runtime execution.

## Dependency inspection

- `dotnet list .../CadAgent.AutoCAD2027.csproj package --include-transitive`: no packages found.
- `dotnet list .../CadAgent.AutoCAD2027.Tests.csproj package --include-transitive`: no packages found.
- The plugin has no project-to-project references; the test project references only the plugin project.
- The unchanged plugin project declares only `AcCoreMgd`, `AcDbMgd`, and `AcMgd` managed AutoCAD references. No Mechanical SDK, COM/ActiveX interop, C++, or native ARX reference was added.
- A case-insensitive scan of the new Mechanical production/test files found no `ActiveX`, `COM`, `C++`, `native ARX`, `Mechanical SDK`, `Interop`, or Mechanical native assembly reference.

## Concerns

- The required focused test remains runner-blocked by the pre-existing test-project configuration. Resolving it would require a test SDK/adapter or project configuration change, which is explicitly forbidden for T03.
- The build emits existing Autodesk/framework assembly conflict warnings; none originate from the four T03 source/test files.

## Correction: discoverable xUnit v3 tests

The test-only correction replaces the static `RunAll` method and helper assertions with four public xUnit v3 `[Fact]` methods in `NoOpMechanicalAdapterTests`. The methods now use xUnit assertions and are discoverable once the shared test SDK/package foundation is available. No production file or project configuration was modified.

Current focused result after this correction: `dotnet test autocad_plugin/CadAgent.AutoCAD2027.Tests -c Release -p:Platform=x64` exits 1 during compilation with 9 `CS0246` errors for `Xunit`, `FactAttribute`, and `Fact`. The PO's T01 shared test SDK/package fix has not arrived in this worktree, so runtime discovery/execution cannot yet be verified and no pass count is claimed. This supersedes the earlier dependency-free/static-test wording above.
