using System.Security.AccessControl;
using System.Security.Principal;
using CadAgent.AutoCAD2027.Drawing;
using Xunit;

namespace CadAgent.AutoCAD2027.Tests.Drawing;

public sealed class NativeLineEditOwnedSaveTests
{
    [Fact]
    public void OwnedSaveMayReplaceFileWhileSubsequentChecksUseNewIdentity()
    {
        using var fixture = new CandidateFixture();
        using var custody = BoundedNativeLineEditPolicy.AcquireCandidateCustody(fixture.Candidate);
        SaveLikeCurrentNativeOwner(custody, fixture.Candidate, () => fixture.ReplaceCandidate("saved native drawing"));
        custody.EnsureCandidatePathMatches(fixture.Candidate);
        Assert.Equal("saved native drawing", File.ReadAllText(fixture.Candidate));
        fixture.ReplaceCandidate("external replacement after save");
        Assert.Throws<InvalidDataException>(() => custody.EnsureCandidatePathMatches(fixture.Candidate));
    }

    [Fact]
    public void ExternalReplacementBeforeSaveNeverCallsSaveOrRefreshesCustody()
    {
        using var fixture = new CandidateFixture();
        using var custody = BoundedNativeLineEditPolicy.AcquireCandidateCustody(fixture.Candidate);
        fixture.ReplaceCandidate("external replacement before save");
        var saveCalled = false;
        Assert.Throws<InvalidDataException>(() => SaveLikeCurrentNativeOwner(custody,
            fixture.Candidate, () => saveCalled = true));
        Assert.False(saveCalled);
        Assert.Equal("external replacement before save", File.ReadAllText(fixture.Candidate));
    }

    [Fact]
    public void FailedSaveDoesNotAdmitReplacementAsTrustedOutput()
    {
        using var fixture = new CandidateFixture();
        using var custody = BoundedNativeLineEditPolicy.AcquireCandidateCustody(fixture.Candidate);
        Assert.Throws<IOException>(() => SaveLikeCurrentNativeOwner(custody, fixture.Candidate, () =>
        {
            fixture.ReplaceCandidate("partial save");
            throw new IOException("save failed");
        }));
        Assert.Throws<InvalidDataException>(() => custody.EnsureCandidatePathMatches(fixture.Candidate));
    }

    [Fact]
    public void OwnedSaveStillRejectsReplacementWithUntrustedWriteAcl()
    {
        using var fixture = new CandidateFixture();
        using var custody = BoundedNativeLineEditPolicy.AcquireCandidateCustody(fixture.Candidate);
        Assert.Throws<InvalidDataException>(() => SaveLikeCurrentNativeOwner(custody, fixture.Candidate, () =>
        {
            fixture.ReplaceCandidate("unsafe save output");
            var file = new FileInfo(fixture.Candidate);
            var security = file.GetAccessControl();
            security.AddAccessRule(new FileSystemAccessRule(
                new SecurityIdentifier(WellKnownSidType.WorldSid, null),
                FileSystemRights.Modify, AccessControlType.Allow));
            file.SetAccessControl(security);
        }));
        Assert.Throws<InvalidDataException>(() => custody.EnsureCandidatePathMatches(fixture.Candidate));
    }

    private static void SaveLikeCurrentNativeOwner(NativeLineEditCandidateCustody custody, string path, Action save)
    {
        custody.SaveOwnedCandidate(path, save);
    }

    private sealed class CandidateFixture : IDisposable
    {
        private readonly string _root = Path.Combine(Path.GetTempPath(), $"cadagent-owned-save-{Guid.NewGuid():N}");
        public string Candidate => Path.Combine(_root, "candidate.dwg");

        public CandidateFixture()
        {
            Directory.CreateDirectory(_root);
            var directory = new DirectoryInfo(_root);
            var security = directory.GetAccessControl();
            security.SetAccessRuleProtection(true, false);
            foreach (FileSystemAccessRule rule in security.GetAccessRules(true, false, typeof(SecurityIdentifier)))
                security.RemoveAccessRuleAll(rule);
            foreach (var sid in new[] { WindowsIdentity.GetCurrent().User!,
                         new SecurityIdentifier(WellKnownSidType.BuiltinAdministratorsSid, null),
                         new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null) })
                security.AddAccessRule(new FileSystemAccessRule(sid, FileSystemRights.FullControl,
                    InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit,
                    PropagationFlags.None, AccessControlType.Allow));
            directory.SetAccessControl(security);
            File.WriteAllText(Candidate, "original native drawing");
        }

        public void ReplaceCandidate(string content)
        {
            var staged = Path.Combine(_root, $"saved-{Guid.NewGuid():N}.dwg");
            File.WriteAllText(staged, content);
            File.Move(Candidate, Path.Combine(_root, $"backup-{Guid.NewGuid():N}.dwg"));
            File.Move(staged, Candidate);
        }

        public void Dispose() => Directory.Delete(_root, recursive: true);
    }
}
