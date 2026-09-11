# Plugin Availability Owner Inventory — Iteration 67

Date: 2026-09-11 (Asia/Saigon)
Branch: `codex/audit-text-style-compat-20260910`
Reviewed code head: `65fc23ba610091e236f19ee93f8cee69f96d4ce9`
Evidence/docs head before this record: `5649697519dff78b878ac24f37ed1cbeb0fb4a07`

## Authority and boundary

SOL's iteration-66 diagnosis was:

```text
VERDICT=MATERIAL_FINDING
FIRST_CAUSAL_BOUNDARY=PLUGIN_AVAILABILITY_BEFORE_SEMANTIC_DISPATCH_NOT_PROVEN
HUMAN_GATE=NO
```

The authorized single bounded action was a non-live reuse-first inventory of
the repository and installed AutoCAD 2027 configuration for an existing
supported CadAgent autoload/demand-load owner. The inventory did not install,
register, copy, or modify any plugin/configuration; it did not start AutoCAD,
retry NETLOAD/WM_CHAR, invoke `CADAGENT_DISPATCH`, touch FileIPC, mutate CAD,
or change production code.

## Repository result

The repository was searched for `PackageContents`, bundle metadata, add-in,
registry, and manifest files, plus explicit `ApplicationPlugins`,
`PackageContents`, autoload, demand-load, and registry-startup references in
the relevant code/docs surfaces.

```text
REPO_AUTOLOAD_METADATA=NONE
CADAGENT_PROJECT_FILES=
  autocad_plugin/CadAgent.AutoCAD2027/CadAgent.AutoCAD2027.csproj
  autocad_plugin/CadAgent.AutoCAD2027.Tests/CadAgent.AutoCAD2027.Tests.csproj
```

The project has build outputs for `CadAgent.AutoCAD2027.dll`, but no existing
CadAgent `ApplicationPlugins` bundle manifest or equivalent repository-owned
autoload owner.

## Installed AutoCAD configuration result

The scoped ApplicationPlugins locations were inspected read-only:

```text
C:/Program Files/Autodesk/ApplicationPlugins                         absent
C:/ProgramData/Autodesk/ApplicationPlugins                            present
C:/Users/dkv/AppData/Roaming/Autodesk/ApplicationPlugins              present
C:/Users/dkv/AppData/Local/Autodesk/ApplicationPlugins                absent
C:/Program Files/Autodesk/AutoCAD 2027/ApplicationPlugins             absent
```

The only CadAgent-named filesystem hits were the registry NetLoad dialog
MRU paths. They are history, not an autoload owner. No installed
`CadAgent.bundle` or `PackageContents.xml` was found.

An unrelated installed `CadMind.bundle` does provide an example of a
supported bundle owner. Its manifest contains `ComponentEntry` with
`LoadOnAutoCADStartup="True"` for CadMind's own DLLs. It is not a CadAgent
assembly and is not a valid semantic owner for this project; it was not
modified or reused.

Read-only registry searches under the current/user and machine Autodesk
AutoCAD roots found no CadAgent demand-load or startup registration. The only
CadAgent registry hits were the `NetLoadDialog` filename MRU entries for old
manual DLL selections.

## Smallest existing-owner proposal

No existing CadAgent autoload/demand-load owner was found. The smallest reuse
proposal is therefore conditional: preserve the existing
`CadAgent.AutoCAD2027` project and semantic .NET/FileIPC owner, and use the
already demonstrated Autodesk `ApplicationPlugins/PackageContents.xml`
`LoadOnAutoCADStartup` mechanism only if a separately authorized CadAgent
bundle/configuration is introduced. This inventory does not introduce it,
because that would be a production configuration change rather than
reuse-first inspection.

The installed CadMind bundle is evidence that AutoCAD's supported bundle
mechanism exists on this workstation, but it does not prove CadAgent
availability and cannot be treated as the owner of CadAgent commands.

## Exact causal oracle for the next authorized boundary

After an approved CadAgent autoload owner is available, the cheapest causal
oracle is one fresh disposable AutoCAD `/b` session that:

1. allows the existing supported bundle owner to load CadAgent;
2. waits for the owned document-ready boundary;
3. performs read-only module inspection of the exact owned PID and asserts the
   approved `CadAgent.AutoCAD2027.dll` path (and recorded SHA-256) is present;
4. closes the exact disposable PID without saving and verifies cleanup.

The oracle must run before any `CADAGENT_DISPATCH`, raw-LISP/WM_CHAR trigger,
FileIPC request, Task-6 action, source/candidate/DXF access, or production CAD
mutation. Iteration 66 is the negative control: the pre-QNEW `NETLOAD` script
reached document-ready but produced zero matching CadAgent modules.

## Evidence and safety

- No production code, repository configuration, installed configuration,
  source/customer drawing, candidate, DXF, or CAD process was modified.
- No new transport or second semantic owner was introduced.
- This inventory does not prove plugin availability; fresh SOL review is
  required before any installation/configuration or live causal oracle.
