from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tomllib
from contextlib import contextmanager
from pathlib import Path

import pytest

from scripts.po_model_guard import GuardError, ensure_configuration, read_turn, verify_turn
from scripts import po_model_guard as guard


def _home(tmp_path: Path, text: str = '') -> Path:
    home = tmp_path / 'codex'
    home.mkdir()
    (home / 'config.toml').write_text(text, encoding='utf-8')
    return home


def _effective(home: Path) -> dict:
    return tomllib.loads((home / 'config.toml').read_text(encoding='utf-8'))


@pytest.mark.parametrize('agents', [
    '',
    '[agents]\n',
    '[agents]\ndefault_subagent_model="gpt-6-luna"\ndefault_subagent_reasoning_effort="high"\n',
    '[agents]\ndefault_subagent_model="gpt-6.1-sol"\ndefault_subagent_reasoning_effort="medium"\n',
])
def test_repair_missing_or_drifted_settings_preserves_unrelated_config(tmp_path, agents):
    home = _home(tmp_path, 'model="gpt-6-luna"\nmodel_reasoning_effort="medium"\nprivate_sentinel="KEEP"\n' + agents)
    result = ensure_configuration(home, repair=True, read_effective=_effective)
    assert result['configuration'] == 'VERIFIED'
    config = _effective(home)
    assert config['private_sentinel'] == 'KEEP'
    assert 'KEEP' not in json.dumps(result)
    assert config['model'] == 'gpt-6-luna'
    assert config['model_reasoning_effort'] == 'medium'
    assert config['agents']['default_subagent_model'] == 'gpt-6.1-sol'
    role = tomllib.loads((home / 'agents/po-sol.toml').read_text())
    assert (role['model'], role['model_reasoning_effort']) == ('gpt-6.1-sol', 'high')


def test_correct_config_is_read_only_and_restart_rechecks_drift(tmp_path):
    home = _home(tmp_path)
    ensure_configuration(home, repair=True, read_effective=_effective)
    before = (home / 'config.toml').read_bytes()
    assert ensure_configuration(home, repair=False, read_effective=_effective)['repaired'] == []
    assert (home / 'config.toml').read_bytes() == before
    (home / 'config.toml').write_text('model="gpt-6-luna"\nmodel_reasoning_effort="medium"\n')
    assert ensure_configuration(home, repair=True, read_effective=_effective)['configuration'] == 'VERIFIED'


def test_unrepairable_effective_override_or_unobservable_runtime_fails_closed(tmp_path):
    home = _home(tmp_path)
    def wrong(_):
        value = _effective(home)
        value['agents']['default_subagent_model'] = 'gpt-6-luna'
        return value
    with pytest.raises(GuardError, match='effective'):
        ensure_configuration(home, repair=True, read_effective=wrong)
    def unavailable(_):
        raise GuardError('runtime unavailable')
    with pytest.raises(GuardError, match='unavailable'):
        ensure_configuration(home, repair=True, read_effective=unavailable)


def test_invalid_config_is_preserved(tmp_path):
    home = _home(tmp_path, '[agents\n')
    before = (home / 'config.toml').read_bytes()
    with pytest.raises(GuardError):
        ensure_configuration(home, repair=True, read_effective=_effective)
    assert (home / 'config.toml').read_bytes() == before


def _events(model='gpt-6.1-sol', effort='high'):
    return [
        {'timestamp': '2026-10-27T03:00:00Z', 'type': 'turn_context',
         'payload': {'turn_id': 'new-turn', 'model': model, 'effort': effort}},
        {'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {'last_token_usage': {'output_tokens': 10}}}},
        {'type': 'event_msg', 'payload': {'type': 'task_complete', 'turn_id': 'new-turn'}},
    ]


@pytest.mark.parametrize(('model', 'effort'), [('gpt-6-luna', 'medium'), ('gpt-6.1-sol', 'medium')])
def test_old_session_never_changes_model_merely_because_config_was_repaired(model, effort):
    with pytest.raises(GuardError, match='runtime model'):
        verify_turn(_events(model, effort), 'new-turn', '2026-10-27T02:59:00Z')


def test_runtime_requires_exact_fresh_executed_completed_turn():
    assert verify_turn(_events(), 'new-turn', '2026-10-27T02:59:00Z')['runtime'] == 'VERIFIED'
    for turn, since, events in [
        ('other-turn', '2026-10-27T02:59:00Z', _events()),
        ('new-turn', '2026-10-27T03:01:00Z', _events()),
        ('new-turn', '2026-10-27T02:59:00Z', _events()[:1]),
        ('new-turn', '2026-10-27T02:59:00Z', [_events()[0], _events()[2]]),
    ]:
        with pytest.raises(GuardError):
            verify_turn(events, turn, since)


@pytest.mark.parametrize('tokens', [True, False, None, '10', 10.0, float('inf'), float('nan'), -1, 0])
def test_runtime_rejects_invalid_or_empty_output_token_evidence(tokens):
    events = _events()
    events[1]['payload']['info']['last_token_usage']['output_tokens'] = tokens
    with pytest.raises(GuardError):
        verify_turn(events, 'new-turn', '2026-10-27T02:59:00Z')


@pytest.mark.parametrize('borrowed', ['other-turn', 'after-completion'])
def test_runtime_cannot_borrow_usage_from_another_or_finished_turn(borrowed):
    context, usage, complete = _events()
    if borrowed == 'other-turn':
        usage['payload']['turn_id'] = 'different-turn'
        events = [context, usage, complete]
    else:
        events = [context, complete, usage]
    with pytest.raises(GuardError):
        verify_turn(events, 'new-turn', '2026-10-27T02:59:00Z')


@pytest.mark.skipif(os.name != 'nt', reason='supported Windows junction boundary')
@pytest.mark.parametrize('component', ['home', 'agents'])
def test_already_correct_reparse_config_is_rejected_without_following_it(tmp_path, component):
    home = _home(tmp_path)
    ensure_configuration(home, repair=True, read_effective=_effective)
    original = home if component == 'home' else home / 'agents'
    target = tmp_path / 'protected-original'
    original.rename(target)
    result = subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(original), str(target)],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    before = {p.relative_to(target): p.read_bytes() for p in target.rglob('*.toml')}
    try:
        with pytest.raises(GuardError, match='reparse|symlink'):
            ensure_configuration(home, repair=False, read_effective=_effective)
        assert {p.relative_to(target): p.read_bytes() for p in target.rglob('*.toml')} == before
    finally:
        original.rmdir()  # Remove only the owned junction, never its target.


@pytest.mark.skipif(os.name != 'nt', reason='supported Windows file sharing and locking')
@pytest.mark.parametrize('writer_mode', ['write', 'replace'])
def test_repair_preserves_any_successful_concurrent_settings_update(tmp_path, monkeypatch, writer_mode):
    home = _home(tmp_path, 'private_sentinel="KEEP"\n')
    config = home / 'config.toml'
    config_identity = config.stat()
    child_results = []
    real_replace, real_fsync = os.replace, os.fsync

    def concurrent_update():
        if child_results:
            return
        script = '''import os, pathlib, sys
p = pathlib.Path(sys.argv[1])
try:
    data = p.read_text() + '\\nconcurrent_sentinel="CONCURRENT_KEEP"\\n'
    if sys.argv[2] == 'replace':
        candidate = p.with_suffix('.writer-tmp')
        candidate.write_text(data)
        os.replace(candidate, p)
    else:
        p.write_text(data)
except PermissionError:
    print('BLOCKED_BY_FILE_CUSTODY')
    sys.exit(3)
'''
        child_results.append(subprocess.run([sys.executable, '-c', script, str(config), writer_mode],
                                            capture_output=True, text=True, check=False, timeout=10))

    def replace_with_competing_writer(source, destination):
        if Path(destination) == config:
            concurrent_update()
        return real_replace(source, destination)

    def sync_with_competing_writer(descriptor):
        if os.path.samestat(os.fstat(descriptor), config_identity):
            concurrent_update()
        return real_fsync(descriptor)

    monkeypatch.setattr(guard.os, 'replace', replace_with_competing_writer)
    monkeypatch.setattr(guard.os, 'fsync', sync_with_competing_writer)
    try:
        ensure_configuration(home, repair=True, read_effective=_effective)
    except GuardError:
        pass
    assert len(child_results) == 1, 'The second process must actually attempt the update.'
    result = child_results[0]
    if result.returncode == 0:
        assert _effective(home)['concurrent_sentinel'] == 'CONCURRENT_KEEP'
    else:
        assert result.returncode == 3, result.stderr
        assert 'BLOCKED_BY_FILE_CUSTODY' in result.stdout
    assert _effective(home)['private_sentinel'] == 'KEEP'


def test_documented_script_entrypoint_works_outside_repository_cwd(tmp_path):
    script = Path(guard.__file__)
    result = subprocess.run([sys.executable, str(script), '--help'], cwd=tmp_path,
                            capture_output=True, text=True, check=False, timeout=10)
    assert result.returncode == 0, result.stderr
    assert '--repair' in result.stdout


@pytest.mark.skipif(os.name != 'nt', reason='supported Windows sharing and mapped writers')
@pytest.mark.parametrize('existing_writer', ['open', 'mapping'])
def test_existing_writer_or_writable_mapping_blocks_repair(tmp_path, existing_writer):
    home = _home(tmp_path, 'private_sentinel="KEEP"\n')
    config = home / 'config.toml'
    before = config.read_bytes()
    script = '''import mmap, pathlib, sys
stream = pathlib.Path(sys.argv[1]).open('r+b')
if sys.argv[2] == 'mapping':
    mapping = mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_WRITE)
    stream.close()
print('READY', flush=True)
sys.stdin.readline()
'''
    process = subprocess.Popen([sys.executable, '-c', script, str(config), existing_writer],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True)
    try:
        assert process.stdout.readline().strip() == 'READY'
        with pytest.raises(GuardError, match='custody'):
            guard._write(config, b'model="gpt-6-luna"\n', before)
        assert config.read_bytes() == before
    finally:
        process.communicate('\n', timeout=10)
    assert process.returncode == 0


@pytest.mark.skipif(os.name != 'nt', reason='supported Windows exclusive creation')
def test_racing_file_creation_is_preserved(tmp_path, monkeypatch):
    target = tmp_path / 'managed' / 'po-sol.toml'
    original_pin = guard.pin_directory_chain

    @contextmanager
    def racing_creation(parent):
        with original_pin(parent):
            result = subprocess.run([sys.executable, '-c',
                'import pathlib,sys;pathlib.Path(sys.argv[1]).write_bytes(b"KEEP_NEW_OWNER")', str(target)],
                capture_output=True, check=False, timeout=10)
            assert result.returncode == 0, result.stderr
            yield

    monkeypatch.setattr(guard, 'pin_directory_chain', racing_creation)
    with pytest.raises(GuardError, match='custody'):
        guard._write(target, b'REPLACEMENT', None)
    assert target.read_bytes() == b'KEEP_NEW_OWNER'


@pytest.mark.skipif(os.name != 'nt', reason='supported Windows same-handle rollback')
@pytest.mark.parametrize('rollback_fails', [False, True])
def test_partial_write_restores_original_or_explicitly_reports_unverified(tmp_path, monkeypatch, rollback_fails):
    home = _home(tmp_path, 'private_sentinel="KEEP"\n')
    config = home / 'config.toml'
    before = config.read_bytes()
    real_write = os.write
    failed = False

    def partial_write(descriptor, data):
        nonlocal failed
        if not failed:
            failed = True
            real_write(descriptor, data[:3])
            raise OSError('injected partial write')
        if rollback_fails:
            raise OSError('injected rollback failure')
        return real_write(descriptor, data)

    monkeypatch.setattr(guard.os, 'write', partial_write)
    expected = 'rollback NOT_VERIFIED' if rollback_fails else 'original bytes restored'
    with pytest.raises(GuardError, match=expected):
        guard._write(config, b'model="gpt-6-luna"\n', before)
    if not rollback_fails:
        assert config.read_bytes() == before


@pytest.mark.skipif(os.name != 'nt', reason='supported Windows extended paths')
def test_runtime_read_accepts_windows_extended_path_but_not_wrong_model(tmp_path):
    home = _home(tmp_path)
    sessions = home / 'sessions'
    sessions.mkdir()
    rollout = sessions / 'po.jsonl'
    rollout.write_text('\n'.join(json.dumps(e) for e in _events('gpt-6-luna', 'medium')))
    with sqlite3.connect(home / 'state_5.sqlite') as connection:
        connection.execute('create table threads(id text, rollout_path text)')
        connection.execute('insert into threads values(?,?)', ('po', '\\\\?\\' + str(rollout.resolve())))
    with pytest.raises(GuardError, match='runtime model'):
        read_turn(home, 'po', 'new-turn', '2026-10-27T02:59:00Z')
