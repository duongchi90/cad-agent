from __future__ import annotations

import ast
import hashlib
import inspect
import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from cad_agent.drawing_contracts import canonical_json_sha256
import cad_agent.pc3_pmp_integrity as pc3_pmp_integrity


def _manifest(*roots: Path) -> dict[str, object]:
    return pc3_pmp_integrity.build_pc3_pmp_integrity_manifest(
        plotter_roots=roots,
    )


def _write(root: Path, relative_path: str, content: bytes) -> Path:
    path = root.joinpath(*relative_path.replace("\\", "/").split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _assert_public_result(result: dict[str, object], *, count: int) -> None:
    assert result["manifest_version"] == "pc3-pmp-integrity-manifest-1.0"
    assert result["count"] == count
    aggregate_sha256 = result["aggregate_sha256"]
    assert isinstance(aggregate_sha256, str)
    assert len(aggregate_sha256) == 64
    assert aggregate_sha256 == aggregate_sha256.lower()
    assert set(result) == {"manifest_version", "count", "aggregate_sha256"}


def _symlink_or_skip(link: Path, target: Path, *, is_directory: bool = False) -> None:
    try:
        link.symlink_to(target, target_is_directory=is_directory)
    except OSError as exc:
        pytest.skip(f"symlink support is unavailable for this test: {exc}")


def _with_windows_reparse_attribute(result: object) -> SimpleNamespace:
    attrs: dict[str, object] = {}
    for name in dir(result):
        if name.startswith("st_"):
            try:
                attrs[name] = getattr(result, name)
            except (AttributeError, OSError):
                continue
    attrs["st_file_attributes"] = int(attrs.get("st_file_attributes", 0)) | stat.FILE_ATTRIBUTE_REPARSE_POINT
    return SimpleNamespace(**attrs)


def _with_changed_file_identity(result: object) -> SimpleNamespace:
    attrs: dict[str, object] = {}
    for name in dir(result):
        if name.startswith("st_"):
            try:
                attrs[name] = getattr(result, name)
            except (AttributeError, OSError):
                continue
    attrs["st_ino"] = int(attrs.get("st_ino", 0)) + 1
    return SimpleNamespace(**attrs)


def test_public_surface_is_closed_and_versioned(tmp_path: Path) -> None:
    root_a = tmp_path / "plotters-a"
    root_b = tmp_path / "plotters-b"
    root_a.mkdir()
    root_b.mkdir()

    assert pc3_pmp_integrity.PC3_PMP_INTEGRITY_MANIFEST_VERSION == (
        "pc3-pmp-integrity-manifest-1.0"
    )
    assert issubclass(pc3_pmp_integrity.PC3PMPIntegrityError, ValueError)

    result = _manifest(root_a, root_b)

    _assert_public_result(result, count=0)


def test_plotter_roots_is_required_with_no_default_or_ambient_fallback() -> None:
    build = pc3_pmp_integrity.build_pc3_pmp_integrity_manifest
    parameter = inspect.signature(build).parameters["plotter_roots"]

    assert parameter.default is inspect.Parameter.empty
    with pytest.raises(TypeError):
        build()


def test_manifest_selects_only_supported_regular_files_and_hides_paths(tmp_path: Path) -> None:
    root_a = tmp_path / "plotters-a"
    root_b = tmp_path / "plotters-b"
    root_a.mkdir()
    root_b.mkdir()
    _write(root_a, "Alpha.PC3", b"alpha")
    _write(root_a, r"Nested\Beta.pMp", b"beta")
    _write(root_b, "gamma.PMP", b"gamma")
    _write(root_b, "ignored.txt", b"ignore")
    (root_b / "directory.PC3").mkdir()

    result = _manifest(root_a, root_b)

    _assert_public_result(result, count=3)
    public_json = json.dumps(result, sort_keys=True)
    for private_name in ("Alpha.PC3", "Beta.pMp", "gamma.PMP", "Nested"):
        assert private_name not in public_json


def test_manifest_is_stable_across_equivalent_creation_permutations(tmp_path: Path) -> None:
    first_a = tmp_path / "first-a"
    first_b = tmp_path / "first-b"
    second_a = tmp_path / "second-a"
    second_b = tmp_path / "second-b"
    for root in (first_a, first_b, second_a, second_b):
        root.mkdir()

    entries = (
        ("Profiles/alpha.PC3", b"alpha"),
        ("Profiles/beta.pmp", b"beta"),
        ("Profiles/gamma.Pc3", b"gamma"),
    )
    for relative_path, content in entries:
        _write(first_a, relative_path, content)
    for relative_path, content in reversed(entries):
        _write(second_a, relative_path, content)
    _write(first_b, "secondary.PMP", b"secondary")
    _write(second_b, "secondary.PMP", b"secondary")

    first = _manifest(first_a, first_b)
    second = _manifest(second_a, second_b)

    assert first == second
    _assert_public_result(first, count=4)


def test_aggregate_recipe_uses_exact_canonical_records_and_per_file_sha256(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_a = tmp_path / "plotters-a"
    root_b = tmp_path / "plotters-b"
    root_a.mkdir()
    root_b.mkdir()
    _write(root_a, "B.PMP", b"beta")
    _write(root_a, "a.PC3", b"alpha")
    _write(root_b, r"Nested\C.Pc3", b"gamma")

    observed_payloads: list[object] = []

    def capture_canonical_hash(payload: object) -> str:
        observed_payloads.append(payload)
        return canonical_json_sha256(payload)

    monkeypatch.setattr(pc3_pmp_integrity, "canonical_json_sha256", capture_canonical_hash)

    result = _manifest(root_a, root_b)
    expected_payload = {
        "manifest_version": "pc3-pmp-integrity-manifest-1.0",
        "records": [
            {
                "root_slot": 0,
                "relative_path": "a.pc3",
                "sha256": hashlib.sha256(b"alpha").hexdigest(),
            },
            {
                "root_slot": 0,
                "relative_path": "b.pmp",
                "sha256": hashlib.sha256(b"beta").hexdigest(),
            },
            {
                "root_slot": 1,
                "relative_path": "nested/c.pc3",
                "sha256": hashlib.sha256(b"gamma").hexdigest(),
            },
        ],
    }

    assert observed_payloads == [expected_payload]
    assert result["aggregate_sha256"] == canonical_json_sha256(expected_payload)
    _assert_public_result(result, count=3)


def test_canonical_relative_paths_normalize_separator_and_case_and_reject_escape() -> None:
    normalize = pc3_pmp_integrity.canonicalize_pc3_pmp_relative_path

    assert normalize(r"Nested\PLOTTER.Pc3") == "nested/plotter.pc3"
    assert normalize("Nested/STYLE.PMP") == "nested/style.pmp"
    for path in ("../outside.pc3", r"..\outside.pmp", "/outside.pc3", r"C:\outside.pmp"):
        with pytest.raises(pc3_pmp_integrity.PC3PMPIntegrityError):
            normalize(path)


def test_duplicate_normalized_identity_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root_a = tmp_path / "plotters-a"
    root_b = tmp_path / "plotters-b"
    root_a.mkdir()
    root_b.mkdir()
    first = _write(root_a, "first.PC3", b"first")
    second = _write(root_a, "second.PMP", b"second")
    original_relative_to = Path.relative_to

    def duplicate_relative_to(path: Path, *other: object, **kwargs: object) -> Path:
        if path in {first, second}:
            return Path(r"Duplicate\PATH.PC3")
        return original_relative_to(path, *other, **kwargs)

    monkeypatch.setattr(Path, "relative_to", duplicate_relative_to)

    with pytest.raises(pc3_pmp_integrity.PC3PMPIntegrityError, match="duplicate|collision"):
        _manifest(root_a, root_b)


def test_symlink_or_reparse_entries_and_root_escape_fail_closed(tmp_path: Path) -> None:
    root_a = tmp_path / "plotters-a"
    root_b = tmp_path / "plotters-b"
    root_a.mkdir()
    root_b.mkdir()
    outside = tmp_path / "outside.PC3"
    outside.write_bytes(b"outside")
    _symlink_or_skip(root_a / "escape.PC3", outside)

    with pytest.raises(pc3_pmp_integrity.PC3PMPIntegrityError, match="symlink|reparse|outside"):
        _manifest(root_a, root_b)


def test_windows_reparse_attribute_entry_fails_closed_without_symlink_semantics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_a = tmp_path / "plotters-a"
    root_b = tmp_path / "plotters-b"
    root_a.mkdir()
    root_b.mkdir()
    selected = _write(root_a, "selected.PC3", b"selected")
    original_lstat = Path.lstat

    def path_lstat(path: Path, *args: object, **kwargs: object) -> object:
        result = original_lstat(path, *args, **kwargs)
        if path == selected:
            return _with_windows_reparse_attribute(result)
        return result

    monkeypatch.setattr(Path, "is_symlink", lambda _path: False)
    monkeypatch.setattr(Path, "lstat", path_lstat)

    with pytest.raises(
        pc3_pmp_integrity.PC3PMPIntegrityError,
        match="entry|file|reparse|junction|outside",
    ):
        _manifest(root_a, root_b)


@pytest.mark.parametrize("exception", [FileNotFoundError("raced"), PermissionError("unreadable")])
def test_missing_unreadable_or_raced_selected_file_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exception: OSError,
) -> None:
    root_a = tmp_path / "plotters-a"
    root_b = tmp_path / "plotters-b"
    root_a.mkdir()
    root_b.mkdir()
    selected = _write(root_a, "selected.PC3", b"selected")
    original_os_open = os.open

    def fail_selected_open(
        path: os.PathLike[str] | str,
        flags: int,
        *args: object,
        **kwargs: object,
    ) -> int:
        if Path(path) == selected:
            raise exception
        return original_os_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", fail_selected_open)

    with pytest.raises(pc3_pmp_integrity.PC3PMPIntegrityError, match="open|read|missing|unreadable|race"):
        _manifest(root_a, root_b)


def test_selected_file_identity_drift_during_hash_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_a = tmp_path / "plotters-a"
    root_b = tmp_path / "plotters-b"
    root_a.mkdir()
    root_b.mkdir()
    _write(root_a, "selected.PC3", b"selected")
    original_os_read = os.read
    original_os_fstat = os.fstat
    read_completed = False

    def tracked_read(descriptor: int, size: int) -> bytes:
        nonlocal read_completed
        result = original_os_read(descriptor, size)
        read_completed = True
        return result

    def drifting_fstat(descriptor: int) -> object:
        result = original_os_fstat(descriptor)
        if read_completed:
            return _with_changed_file_identity(result)
        return result

    monkeypatch.setattr(os, "read", tracked_read)
    monkeypatch.setattr(os, "fstat", drifting_fstat)

    with pytest.raises(
        pc3_pmp_integrity.PC3PMPIntegrityError,
        match="race|drift|changed|identity|replaced",
    ):
        _manifest(root_a, root_b)

    assert read_completed


def test_transient_swap_and_restore_selected_file_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_a = tmp_path / "plotters-a"
    root_b = tmp_path / "plotters-b"
    root_a.mkdir()
    root_b.mkdir()
    selected = _write(root_a, "selected.PC3", b"selected")
    outside = tmp_path / "outside.PC3"
    outside.write_bytes(b"outside")
    probe = tmp_path / "symlink-probe"
    _symlink_or_skip(probe, outside)
    probe.unlink()

    original_os_open = os.open
    swapped = False

    def raced_open(path: os.PathLike[str] | str, flags: int, *args: object, **kwargs: object) -> int:
        nonlocal swapped
        if Path(path) != selected:
            return original_os_open(path, flags, *args, **kwargs)
        backup = selected.with_suffix(".backup")
        selected.rename(backup)
        selected.symlink_to(outside)
        try:
            fd = original_os_open(path, flags, *args, **kwargs)
            swapped = True
            return fd
        finally:
            selected.unlink(missing_ok=True)
            backup.rename(selected)

    monkeypatch.setattr(os, "open", raced_open)

    with pytest.raises(
        pc3_pmp_integrity.PC3PMPIntegrityError,
        match="race|drift|changed|identity|reparse|replaced",
    ):
        _manifest(root_a, root_b)

    assert swapped


def test_root_identity_drift_before_traversal_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_a = tmp_path / "plotters-a"
    root_b = tmp_path / "plotters-b"
    root_a.mkdir()
    root_b.mkdir()
    _write(root_a, "selected.PC3", b"selected")
    original_lstat = Path.lstat
    root_calls = 0

    def path_lstat(path: Path, *args: object, **kwargs: object) -> object:
        nonlocal root_calls
        result = original_lstat(path, *args, **kwargs)
        if path == root_a:
            root_calls += 1
            if root_calls >= 3:
                return _with_changed_file_identity(result)
        return result

    monkeypatch.setattr(Path, "lstat", path_lstat)

    with pytest.raises(
        pc3_pmp_integrity.PC3PMPIntegrityError,
        match="root|directory|race|drift|changed|identity|replaced",
    ):
        _manifest(root_a, root_b)


def test_nested_directory_identity_drift_before_descent_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_a = tmp_path / "plotters-a"
    root_b = tmp_path / "plotters-b"
    root_a.mkdir()
    root_b.mkdir()
    nested = root_a / "nested"
    nested.mkdir()
    _write(nested, "selected.PC3", b"selected")
    original_lstat = Path.lstat
    nested_calls = 0

    def path_lstat(path: Path, *args: object, **kwargs: object) -> object:
        nonlocal nested_calls
        result = original_lstat(path, *args, **kwargs)
        if path == nested:
            nested_calls += 1
            if nested_calls >= 3:
                return _with_changed_file_identity(result)
        return result

    monkeypatch.setattr(Path, "lstat", path_lstat)

    with pytest.raises(
        pc3_pmp_integrity.PC3PMPIntegrityError,
        match="directory|race|drift|changed|identity|reparse|replaced",
    ):
        _manifest(root_a, root_b)


def test_root_substitution_after_post_enumeration_check_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_a = tmp_path / "plotters-a"
    root_b = tmp_path / "plotters-b"
    replacement = tmp_path / "replacement-root"
    backup = tmp_path / "plotters-a-original"
    root_a.mkdir()
    root_b.mkdir()
    replacement.mkdir()
    selected = _write(root_a, "selected.PC3", b"inside")
    _write(replacement, "selected.PC3", b"outside")
    original_lstat = Path.lstat
    swapped = False

    def path_lstat(path: Path, *args: object, **kwargs: object) -> object:
        nonlocal swapped
        if path == selected and not swapped:
            root_a.rename(backup)
            replacement.rename(root_a)
            swapped = True
        return original_lstat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", path_lstat)

    try:
        with pytest.raises(
            pc3_pmp_integrity.PC3PMPIntegrityError,
            match="root|directory|parent|race|drift|changed|identity|replaced|metadata",
        ):
            _manifest(root_a, root_b)
    finally:
        if swapped:
            root_a.rename(replacement)
            backup.rename(root_a)

    assert swapped


def test_nested_parent_substitution_after_post_enumeration_check_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_a = tmp_path / "plotters-a"
    root_b = tmp_path / "plotters-b"
    root_a.mkdir()
    root_b.mkdir()
    nested = root_a / "nested"
    nested.mkdir()
    replacement = tmp_path / "replacement-nested"
    replacement.mkdir()
    backup = root_a / "nested-original"
    selected = _write(nested, "selected.PC3", b"inside")
    _write(replacement, "selected.PC3", b"outside")
    original_lstat = Path.lstat
    swapped = False

    def path_lstat(path: Path, *args: object, **kwargs: object) -> object:
        nonlocal swapped
        if path == selected and not swapped:
            nested.rename(backup)
            replacement.rename(nested)
            swapped = True
        return original_lstat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", path_lstat)

    try:
        with pytest.raises(
            pc3_pmp_integrity.PC3PMPIntegrityError,
            match="directory|parent|race|drift|changed|identity|replaced|metadata",
        ):
            _manifest(root_a, root_b)
    finally:
        if swapped:
            nested.rename(replacement)
            backup.rename(nested)

    assert swapped


def test_byte_change_and_root_slot_order_change_aggregate(tmp_path: Path) -> None:
    root_a = tmp_path / "plotters-a"
    root_b = tmp_path / "plotters-b"
    root_a.mkdir()
    root_b.mkdir()
    selected = _write(root_a, "shared.PC3", b"before")
    _write(root_b, "shared.PC3", b"other-root")

    before = _manifest(root_a, root_b)
    reversed_roots = _manifest(root_b, root_a)
    selected.write_bytes(b"after")
    after = _manifest(root_a, root_b)

    assert before["aggregate_sha256"] != reversed_roots["aggregate_sha256"]
    assert before["aggregate_sha256"] != after["aggregate_sha256"]
    _assert_public_result(after, count=2)


@pytest.mark.parametrize("roots", [(), (Path("one"),), (Path("one"), Path("two"), Path("three"))])
def test_scope_requires_exactly_two_explicit_existing_ordinary_roots(
    tmp_path: Path,
    roots: tuple[Path, ...],
) -> None:
    del tmp_path
    with pytest.raises(pc3_pmp_integrity.PC3PMPIntegrityError, match="two|root"):
        _manifest(*roots)


def test_two_explicit_roots_must_exist_and_be_directories(tmp_path: Path) -> None:
    missing_a = tmp_path / "missing-a"
    missing_b = tmp_path / "missing-b"
    with pytest.raises(pc3_pmp_integrity.PC3PMPIntegrityError, match="root|exist|directory"):
        _manifest(missing_a, missing_b)

    root_a = tmp_path / "plotters-a"
    root_b = tmp_path / "plotters-b"
    root_a.write_bytes(b"not-a-directory")
    root_b.mkdir()
    with pytest.raises(pc3_pmp_integrity.PC3PMPIntegrityError, match="root|directory"):
        _manifest(root_a, root_b)


def test_two_explicit_roots_must_be_distinct(tmp_path: Path) -> None:
    root_a = tmp_path / "plotters-a"
    root_a.mkdir()

    with pytest.raises(
        pc3_pmp_integrity.PC3PMPIntegrityError,
        match="distinct|duplicate|same|root",
    ):
        _manifest(root_a, root_a)


def test_two_explicit_roots_reject_symlink_or_reparse_root(tmp_path: Path) -> None:
    actual_root = tmp_path / "actual-plotters"
    other_root = tmp_path / "other-plotters"
    actual_root.mkdir()
    other_root.mkdir()
    linked_root = tmp_path / "linked-plotters"
    _symlink_or_skip(linked_root, actual_root, is_directory=True)

    with pytest.raises(pc3_pmp_integrity.PC3PMPIntegrityError, match="root|symlink|reparse"):
        _manifest(linked_root, other_root)


def test_windows_reparse_attribute_root_fails_closed_without_symlink_semantics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_a = tmp_path / "plotters-a"
    root_b = tmp_path / "plotters-b"
    root_a.mkdir()
    root_b.mkdir()

    original_path_stat = Path.stat
    original_path_lstat = Path.lstat
    original_os_lstat = os.lstat

    def path_stat(path: Path, *args: object, **kwargs: object) -> object:
        result = original_path_stat(path, *args, **kwargs)
        if path == root_a:
            return _with_windows_reparse_attribute(result)
        return result

    def path_lstat(path: Path, *args: object, **kwargs: object) -> object:
        result = original_path_lstat(path, *args, **kwargs)
        if path == root_a:
            return _with_windows_reparse_attribute(result)
        return result

    def os_lstat(path: os.PathLike[str] | str, *args: object, **kwargs: object) -> object:
        result = original_os_lstat(path, *args, **kwargs)
        if Path(path) == root_a:
            return _with_windows_reparse_attribute(result)
        return result

    monkeypatch.setattr(Path, "is_symlink", lambda _path: False)
    monkeypatch.setattr(Path, "stat", path_stat)
    monkeypatch.setattr(Path, "lstat", path_lstat)
    monkeypatch.setattr(os, "lstat", os_lstat)

    with pytest.raises(pc3_pmp_integrity.PC3PMPIntegrityError, match="root|reparse|junction"):
        _manifest(root_a, root_b)


def test_module_uses_only_fail_closed_read_hash_authority_surface() -> None:
    source = Path(pc3_pmp_integrity.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_from = {
        (node.module, alias.name)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
        for alias in node.names
    }
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    attribute_calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    named_calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    local_callables = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }

    allowed_imported_modules = {"hashlib", "os", "stat"}
    allowed_imports_from = {
        ("__future__", "annotations"),
        ("pathlib", "Path"),
        ("cad_agent.drawing_contracts", "canonical_json_sha256"),
    }
    allowed_attribute_calls = {
        "S_ISDIR",
        "S_ISREG",
        "append",
        "as_posix",
        "casefold",
        "close",
        "fstat",
        "hexdigest",
        "is_absolute",
        "is_symlink",
        "iterdir",
        "join",
        "lower",
        "lstat",
        "open",
        "read",
        "relative_to",
        "sha256",
        "split",
        "startswith",
    }
    allowed_named_calls = local_callables | {
        "all",
        "any",
        "bool",
        "bytes",
        "canonical_json_sha256",
        "dict",
        "enumerate",
        "getattr",
        "int",
        "isinstance",
        "len",
        "list",
        "set",
        "sorted",
        "str",
        "tuple",
    }

    assert ("cad_agent.drawing_contracts", "canonical_json_sha256") in imported_from
    assert imported_modules <= allowed_imported_modules
    assert imported_from <= allowed_imports_from
    assert attribute_calls <= allowed_attribute_calls
    assert named_calls <= allowed_named_calls

    path_constructor_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Path"
    ]
    assert path_constructor_calls == []
