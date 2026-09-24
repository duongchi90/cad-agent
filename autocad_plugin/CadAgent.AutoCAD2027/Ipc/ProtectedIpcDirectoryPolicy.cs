using System.Security.AccessControl;
using System.Security.Principal;

namespace CadAgent.AutoCAD2027.Ipc;

// This boundary trusts the current Windows principal; it does not distinguish processes running as that principal.
internal static class ProtectedIpcDirectoryPolicy
{
    private const uint GenericWrite = 0x40000000;
    private const uint GenericAll = 0x10000000;

    private static readonly FileSystemRights WriteRights =
        FileSystemRights.Write
        | FileSystemRights.Delete
        | FileSystemRights.DeleteSubdirectoriesAndFiles
        | FileSystemRights.ChangePermissions
        | FileSystemRights.TakeOwnership
        | FileSystemRights.CreateFiles
        | FileSystemRights.CreateDirectories;

    private static readonly FileSystemRights PathReplacementRights =
        FileSystemRights.Delete
        | FileSystemRights.DeleteSubdirectoriesAndFiles
        | FileSystemRights.ChangePermissions
        | FileSystemRights.TakeOwnership;

    public static bool IsCanonical(string suppliedPath, string normalizedPath)
    {
        if (!Path.IsPathFullyQualified(suppliedPath))
        {
            return false;
        }

        return string.Equals(
            Path.TrimEndingDirectorySeparator(suppliedPath),
            Path.TrimEndingDirectorySeparator(normalizedPath),
            StringComparison.OrdinalIgnoreCase);
    }

    public static void EnsureProtected(string directoryPath, bool canonical)
    {
        if (!OperatingSystem.IsWindows())
        {
            throw new InvalidDataException("Native edits require a protected local Windows FileIPC directory.");
        }

        if (!canonical)
        {
            throw new InvalidDataException("The FileIPC directory path is not canonical.");
        }

        var fullPath = Path.GetFullPath(directoryPath);
        var volumeRoot = Path.GetPathRoot(fullPath);
        if (string.IsNullOrWhiteSpace(volumeRoot)
            || new DriveInfo(volumeRoot).DriveType != DriveType.Fixed)
        {
            throw new InvalidDataException("The FileIPC directory must be on a local fixed Windows volume.");
        }

        var currentUser = WindowsIdentity.GetCurrent().User
            ?? throw new InvalidDataException("The current Windows principal could not be identified.");
        var trustedSids = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            currentUser.Value,
            new SecurityIdentifier(WellKnownSidType.BuiltinAdministratorsSid, null).Value,
            new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null).Value
        };
        var trustedPathOwners = new HashSet<string>(trustedSids, StringComparer.OrdinalIgnoreCase);
        try
        {
            trustedPathOwners.Add(new NTAccount("NT SERVICE", "TrustedInstaller")
                .Translate(typeof(SecurityIdentifier))
                .Value);
        }
        catch (IdentityNotMappedException)
        {
            // A Windows image without this service may still use a path owned by another trusted SID.
        }

        var directories = GetExistingPathDirectories(fullPath);
        foreach (var directory in directories)
        {
            EnsureNotReparsePoint(directory);
        }

        EnsureProtectedRootAcl(directories[0], trustedSids);
        EnsureNoUntrustedPathReplacementRights(directories, trustedSids, trustedPathOwners);
    }

    private static IReadOnlyList<DirectoryInfo> GetExistingPathDirectories(string fullPath)
    {
        var directories = new List<DirectoryInfo>();
        for (var current = new DirectoryInfo(fullPath); current is not null; current = current.Parent)
        {
            if (!current.Exists)
            {
                throw new InvalidDataException("The FileIPC directory path contains a missing directory.");
            }

            directories.Add(current);
            if (current.Parent is null)
            {
                break;
            }
        }

        return directories;
    }

    private static void EnsureNotReparsePoint(DirectoryInfo directory)
    {
        if ((directory.Attributes & FileAttributes.ReparsePoint) != 0)
        {
            throw new InvalidDataException("The FileIPC directory path must not contain reparse points.");
        }
    }

    private static void EnsureNoUntrustedPathReplacementRights(
        IReadOnlyList<DirectoryInfo> directories,
        IReadOnlySet<string> trustedSids,
        IReadOnlySet<string> trustedPathOwners)
    {
        foreach (var directory in directories)
        {
            var security = directory.GetAccessControl(AccessControlSections.Access | AccessControlSections.Owner);
            var owner = security.GetOwner(typeof(SecurityIdentifier)) as SecurityIdentifier;
            if (owner is null || !trustedPathOwners.Contains(owner.Value))
            {
                throw new InvalidDataException(
                    "A FileIPC path directory is owned by an untrusted Windows principal.");
            }

            foreach (FileSystemAccessRule rule in security.GetAccessRules(
                         includeExplicit: true,
                         includeInherited: true,
                         targetType: typeof(SecurityIdentifier)))
            {
                var sid = ((SecurityIdentifier)rule.IdentityReference).Value;
                if (rule.AccessControlType == AccessControlType.Allow
                    && !trustedSids.Contains(sid)
                    && ((rule.FileSystemRights & PathReplacementRights) != 0
                        || HasGenericRight(rule.FileSystemRights, GenericAll)))
                {
                    throw new InvalidDataException(
                        "An untrusted Windows principal can replace part of the FileIPC directory path.");
                }
            }
        }
    }

    internal static void EnsureProtectedRootAcl(
        DirectoryInfo root,
        IReadOnlySet<string> trustedSids)
    {
        var security = root.GetAccessControl(AccessControlSections.Access | AccessControlSections.Owner);
        if (!security.AreAccessRulesProtected)
        {
            throw new InvalidDataException("The FileIPC directory ACL must be protected from inheritance.");
        }

        var owner = security.GetOwner(typeof(SecurityIdentifier)) as SecurityIdentifier;
        if (owner is null || !trustedSids.Contains(owner.Value))
        {
            throw new InvalidDataException("The FileIPC directory owner is not a trusted Windows principal.");
        }

        var fullControlSids = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (FileSystemAccessRule rule in security.GetAccessRules(
                     includeExplicit: true,
                     includeInherited: true,
                     targetType: typeof(SecurityIdentifier)))
        {
            var sid = ((SecurityIdentifier)rule.IdentityReference).Value;
            if (rule.AccessControlType == AccessControlType.Deny
                && HasWriteRights(rule.FileSystemRights))
            {
                throw new InvalidDataException(
                    "The FileIPC directory ACL denies write access needed by the trusted Windows principal.");
            }

            if (rule.AccessControlType == AccessControlType.Allow
                && HasWriteRights(rule.FileSystemRights)
                && !trustedSids.Contains(sid))
            {
                throw new InvalidDataException(
                    "An untrusted Windows principal has write access to the FileIPC directory.");
            }

            if (rule.AccessControlType == AccessControlType.Allow
                && (rule.PropagationFlags & PropagationFlags.InheritOnly) == 0
                && ((rule.FileSystemRights & FileSystemRights.FullControl) == FileSystemRights.FullControl
                    || HasGenericRight(rule.FileSystemRights, GenericAll)))
            {
                fullControlSids.Add(sid);
            }
        }

        foreach (var sid in trustedSids)
        {
            if (!fullControlSids.Contains(sid))
            {
                throw new InvalidDataException(
                    "The FileIPC directory must grant full control only to the current principal, Administrators, and SYSTEM.");
            }
        }
    }

    private static bool HasWriteRights(FileSystemRights rights) =>
        (rights & WriteRights) != 0
        || HasGenericRight(rights, GenericWrite)
        || HasGenericRight(rights, GenericAll);

    private static bool HasGenericRight(FileSystemRights rights, uint genericRight) =>
        (unchecked((uint)(int)rights) & genericRight) != 0;
}
