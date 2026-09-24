using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;
using Microsoft.Win32.SafeHandles;

namespace CadAgent.AutoCAD2027.Ipc;

// This boundary trusts the current Windows principal; it does not distinguish processes running as that principal.
internal static class ProtectedIpcDirectoryPolicy
{
    private const uint GenericWrite = 0x40000000;
    private const uint GenericAll = 0x10000000;
    private const uint FileReadAttributes = 0x00000080;
    private const uint ReadControl = 0x00020000;
    private const uint GenericRead = 0x80000000;
    private const uint ShareRead = 0x00000001;
    private const uint ShareWrite = 0x00000002;
    private const uint ShareDelete = 0x00000004;
    private const uint OpenExisting = 3;
    private const uint FileFlagOpenReparsePoint = 0x00200000;
    private const uint FileFlagBackupSemantics = 0x02000000;
    private const int FileIdInfoClass = 18;

    private static readonly FileSystemRights WriteRights =
        FileSystemRights.Write
        | FileSystemRights.Delete
        | FileSystemRights.DeleteSubdirectoriesAndFiles
        | FileSystemRights.ChangePermissions
        | FileSystemRights.TakeOwnership
        | FileSystemRights.CreateFiles
        | FileSystemRights.CreateDirectories;

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
        using var custody = AcquireProtectedDirectory(directoryPath, canonical);
    }

    internal static ProtectedIpcDirectoryCustody AcquireProtectedDirectory(
        string directoryPath,
        bool canonical)
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

        var directories = GetExistingPathDirectories(fullPath);
        var handles = new List<SafeFileHandle>(directories.Count);
        try
        {
            foreach (var directory in directories.Reverse())
            {
                var isRoot = string.Equals(directory.FullName, fullPath, StringComparison.OrdinalIgnoreCase);
                var handle = OpenDirectoryHandle(directory.FullName, holdCustody: true, readControl: isRoot);
                handles.Add(handle);
                EnsureDirectoryHandleMatchesPath(handle, directory.FullName);
            }

            var currentUser = WindowsIdentity.GetCurrent().User
                ?? throw new InvalidDataException("The current Windows principal could not be identified.");
            var trustedSids = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            {
                currentUser.Value,
                new SecurityIdentifier(WellKnownSidType.BuiltinAdministratorsSid, null).Value,
                new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null).Value
            };
            EnsureProtectedRootAcl(new DirectoryInfo(fullPath), trustedSids);
            return new ProtectedIpcDirectoryCustody(handles, GetFileIdentity(handles[^1]));
        }
        catch
        {
            DisposeHandles(handles);
            throw;
        }
    }

    internal static SafeFileHandle OpenDirectoryForObservation(string directoryPath) =>
        OpenDirectoryHandle(directoryPath, holdCustody: false, readControl: false);

    internal static SafeFileHandle OpenRequestFileForCustody(string requestPath)
    {
        var handle = CreateFileHandle(
            requestPath,
            GenericRead,
            ShareRead,
            FileFlagOpenReparsePoint);
        try
        {
            var attributes = GetFileAttributes(handle);
            if ((attributes & (FileAttributes.Directory | FileAttributes.ReparsePoint)) != 0)
            {
                throw new InvalidDataException("The FileIPC request must be a regular, non-reparse file.");
            }

            return handle;
        }
        catch
        {
            handle.Dispose();
            throw;
        }
    }

    internal static IpcFileIdentity GetFileIdentity(SafeFileHandle handle)
    {
        if (!GetFileInformationByHandleEx(handle, FileIdInfoClass, out var information,
                (uint)Marshal.SizeOf<FileIdInfo>()))
        {
            throw new Win32Exception(Marshal.GetLastWin32Error(), "The Windows file identity could not be read.");
        }

        return new IpcFileIdentity(
            information.VolumeSerialNumber,
            information.FileId.Low,
            information.FileId.High);
    }

    internal static FileAttributes GetFileAttributes(SafeFileHandle handle)
    {
        if (!GetFileInformationByHandle(handle, out var information))
        {
            throw new Win32Exception(Marshal.GetLastWin32Error(), "The Windows file attributes could not be read.");
        }

        return (FileAttributes)information.FileAttributes;
    }

    internal static string GetFinalPath(SafeFileHandle handle)
    {
        var buffer = new StringBuilder(32768);
        var length = GetFinalPathNameByHandle(handle, buffer, (uint)buffer.Capacity, 0);
        if (length == 0 || length >= buffer.Capacity)
        {
            throw new Win32Exception(Marshal.GetLastWin32Error(), "The Windows file path could not be verified.");
        }

        var path = buffer.ToString();
        if (path.StartsWith("\\\\?\\UNC\\", StringComparison.OrdinalIgnoreCase))
        {
            return "\\\\" + path[8..];
        }

        return path.StartsWith("\\\\?\\", StringComparison.OrdinalIgnoreCase)
            ? path[4..]
            : path;
    }

    internal static bool PathsEqual(string left, string right) =>
        string.Equals(
            Path.TrimEndingDirectorySeparator(left),
            Path.TrimEndingDirectorySeparator(right),
            StringComparison.OrdinalIgnoreCase);

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

    private static void EnsureDirectoryHandleMatchesPath(SafeFileHandle handle, string expectedPath)
    {
        var attributes = GetFileAttributes(handle);
        if ((attributes & FileAttributes.Directory) == 0)
        {
            throw new InvalidDataException("The FileIPC directory path contains a non-directory component.");
        }

        if ((attributes & FileAttributes.ReparsePoint) != 0)
        {
            throw new InvalidDataException("The FileIPC directory path must not contain reparse points.");
        }

        if (!PathsEqual(GetFinalPath(handle), expectedPath))
        {
            throw new InvalidDataException("The FileIPC directory path changed while custody was being acquired.");
        }
    }

    internal static void EnsureProtectedRootAcl(
        DirectoryInfo root,
        IReadOnlySet<string> trustedSids)
    {
        var security = root.GetAccessControl(AccessControlSections.Access | AccessControlSections.Owner);
        EnsureProtectedRootAcl(security, trustedSids);
    }

    private static void EnsureProtectedRootAcl(FileSystemSecurity security, IReadOnlySet<string> trustedSids)
    {
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

    private static SafeFileHandle OpenDirectoryHandle(string path, bool holdCustody, bool readControl)
    {
        var shareMode = ShareRead | ShareWrite | (holdCustody ? 0u : ShareDelete);
        var desiredAccess = FileReadAttributes | (readControl ? ReadControl : 0u);
        return CreateFileHandle(path, desiredAccess, shareMode,
            FileFlagBackupSemantics | FileFlagOpenReparsePoint);
    }

    private static SafeFileHandle CreateFileHandle(
        string path,
        uint desiredAccess,
        uint shareMode,
        uint flagsAndAttributes)
    {
        var handle = CreateFile(
            path,
            desiredAccess,
            shareMode,
            IntPtr.Zero,
            OpenExisting,
            flagsAndAttributes,
            IntPtr.Zero);
        if (handle.IsInvalid)
        {
            var error = Marshal.GetLastWin32Error();
            handle.Dispose();
            throw new Win32Exception(error, "The FileIPC path could not be opened for identity custody.");
        }

        return handle;
    }

    private static void DisposeHandles(IReadOnlyList<SafeFileHandle> handles)
    {
        for (var index = handles.Count - 1; index >= 0; index--)
        {
            handles[index].Dispose();
        }
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct FileId128
    {
        public ulong Low;
        public ulong High;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct FileIdInfo
    {
        public ulong VolumeSerialNumber;
        public FileId128 FileId;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct ByHandleFileInformation
    {
        public uint FileAttributes;
        public System.Runtime.InteropServices.ComTypes.FILETIME CreationTime;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastAccessTime;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastWriteTime;
        public uint VolumeSerialNumber;
        public uint FileSizeHigh;
        public uint FileSizeLow;
        public uint NumberOfLinks;
        public uint FileIndexHigh;
        public uint FileIndexLow;
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true, EntryPoint = "CreateFileW")]
    private static extern SafeFileHandle CreateFile(
        string fileName,
        uint desiredAccess,
        uint shareMode,
        IntPtr securityAttributes,
        uint creationDisposition,
        uint flagsAndAttributes,
        IntPtr templateFile);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetFileInformationByHandle(
        SafeFileHandle handle,
        out ByHandleFileInformation information);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetFileInformationByHandleEx(
        SafeFileHandle handle,
        int informationClass,
        out FileIdInfo information,
        uint bufferSize);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true, EntryPoint = "GetFinalPathNameByHandleW")]
    private static extern uint GetFinalPathNameByHandle(
        SafeFileHandle handle,
        StringBuilder path,
        uint pathLength,
        uint flags);
}

internal readonly record struct IpcFileIdentity(ulong VolumeSerialNumber, ulong FileIdLow, ulong FileIdHigh);

internal sealed class ProtectedIpcDirectoryCustody : IDisposable
{
    private readonly IReadOnlyList<SafeFileHandle> _handles;

    internal ProtectedIpcDirectoryCustody(
        IReadOnlyList<SafeFileHandle> handles,
        IpcFileIdentity rootIdentity)
    {
        _handles = handles;
        RootIdentity = rootIdentity;
    }

    internal IpcFileIdentity RootIdentity { get; }

    public void Dispose()
    {
        for (var index = _handles.Count - 1; index >= 0; index--)
        {
            _handles[index].Dispose();
        }
    }
}
