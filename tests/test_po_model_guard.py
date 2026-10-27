from __future__ import annotations

import json
import os
import sqlite3
import tomllib
from pathlib import Path

import pytest

from scripts.po_model_guard import GuardError, ensure_configuration, read_turn, verify_turn


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
