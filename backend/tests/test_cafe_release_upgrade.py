"""Real disposable Git tags; inert systemd/package/DB commands for failure ordering."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(os.name != 'posix', reason='Linux production upgrade workflow.')


@pytest.fixture()
def release(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('upgrade_cafe_release', ROOT / 'scripts/upgrade_cafe_release.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source, app, data = (tmp_path / name for name in ('origin', 'app', 'persistent'))
    source.mkdir()
    data.mkdir()
    (data / 'upgrades').mkdir()
    def git(*args, cwd=source):
        return subprocess.check_output(['git', *args], cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()
    git('init', '-q')
    git('config', 'user.name', 'Release Test')
    git('config', 'user.email', 'release@example.com')
    for name in ('backend/requirements.txt', 'frontend/package-lock.json', 'scripts/upgrade_cafe.sh',
                 'scripts/check_cafe_v1.py', 'backend/scripts/cafe_production.py'):
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('initial release\n')
    git('add', '.')
    git('commit', '-qm', 'First release')
    git('tag', '-a', 'cafe-v1.0.0', '-m', 'First version')
    old_commit = git('rev-parse', 'HEAD')
    (source / 'version.txt').write_text('Updated application\n')
    git('add', '.')
    git('commit', '-qm', 'Updated release')
    git('tag', '-a', 'cafe-v1.1.0', '-m', 'Next version')
    new_commit = git('rev-parse', 'HEAD')
    git('clone', '-q', str(source), str(app), cwd=tmp_path)
    git('checkout', '--detach', old_commit, cwd=app)
    monkeypatch.setattr(module, 'APP', app)
    monkeypatch.setattr(module, 'DATA', data)
    monkeypatch.setattr(module.time, 'sleep', lambda seconds: None)

    class Harness(module.Upgrade):
        fail_at = None
        def __init__(self, tag='cafe-v1.1.0'):
            super().__init__(tag)
            self.events = []
            self.backup_states = []

        def command(self, args, *, cwd=None, env=None, check=True):
            args = [str(arg) for arg in args]
            self.events.append(args)
            if args[0] == 'git':
                return super().command(args, cwd=cwd, env=env, check=check)
            key = None
            output = ''
            code = 0
            if args[0] == 'systemctl' and args[1] == 'is-active':
                code = 1  # Optional writers and in-flight backup are absent.
            elif args[:2] == ['systemctl', 'show']:
                output = self.backup_states.pop(0) if args[2] == 'kalpvrik-backup.service' and self.backup_states else 'inactive'
            elif args[0] == 'runuser':
                index = next(i for i, arg in enumerate(args) if arg.endswith('/cafe_production.py'))
                key = args[index + 1]
                if key == 'status':
                    output = json.dumps({'database': {'database': 'same_cafe'}, 'alembic_revisions': ['current']})
                elif key == 'backup':
                    archive = data / 'verified.dump'
                    archive.write_bytes(b'PGDMP-test-placeholder')
                    output = f'Verified backup: {archive}\n'
            elif '-m' in args and 'pip' in args:
                key = 'pip'
            elif args[:2] == ['npm', 'ci']:
                key = 'npm-ci'
            elif args[:3] == ['npm', 'run', 'build']:
                key = 'build'
                assert env['VITE_API_BASE_URL'] == 'http://127.0.0.1:8000/api'
            if self.fail_at is not None and key == self.fail_at:
                code = 1
            if check and code:
                raise RuntimeError(f'Simulated {key} failure')
            return subprocess.CompletedProcess(args, code, output)

        def health(self, *, check=True):
            self.events.append(['health'])
            code = int(self.directory is not None and self.fail_at == 'health')
            if check and code:
                raise RuntimeError('Health failed')
            return subprocess.CompletedProcess(['health'], code, '')

    return module, Harness, git, app, data, old_commit, new_commit, source


def test_tagged_upgrade_orders_backup_checkout_dependencies_migration_build_and_health(release):
    module, Harness, git, app, data, old, new, source = release
    upgrade = Harness()
    upgrade.perform()
    assert git('rev-parse', 'HEAD', cwd=app) == new
    events = upgrade.events
    def position(fragment):
        return next(i for i, args in enumerate(events) if fragment in ' '.join(args))
    assert position(' backup --reason pre-upgrade') < position(' verify-backup --archive') < position('git fetch')
    assert position('git checkout') < position('pip install') < position('npm ci') < position('cafe_production.py upgrade') < position('npm run build')
    assert position('npm run build') < position('systemctl restart') < len(events) - 1
    journal = json.loads((upgrade.directory / 'state.json').read_text())
    assert journal['stage'] == 'complete'
    assert journal['previous_commit'] == old
    assert journal['target_commit'] == new
    assert journal['backup_verified'] is True
    assert journal['migrations_completed'] is True
    assert Path(journal['backup_archive']).is_file()
    assert (upgrade.directory / 'upgrade_runner.py').is_file()
    assert not any(word in ' '.join(' '.join(args) for args in events) for word in ('drop', 'recreate', 'bootstrap', 'seed', 'downgrade'))


@pytest.mark.parametrize('failure', ['backup', 'verify-backup', 'pip', 'npm-ci', 'upgrade', 'build', 'health'])
def test_failed_upgrade_leaves_services_disabled_and_never_restores_database(release, failure):
    module, Harness, git, app, data, old, new, source = release
    upgrade = Harness()
    upgrade.fail_at = failure
    with pytest.raises(RuntimeError):
        upgrade.perform()
    journal = json.loads((upgrade.directory / 'state.json').read_text())
    assert journal['stage'] == 'failed'
    assert upgrade.events[-1] == ['systemctl', 'disable', '--now', *module.APP_UNITS, module.TIMER]
    assert not any('restore' in ' '.join(event) for event in upgrade.events)
    if failure in {'backup', 'verify-backup'}:
        assert git('rev-parse', 'HEAD', cwd=app) == old
        assert not any('git fetch' in ' '.join(event) for event in upgrade.events)
    if failure in {'upgrade', 'build', 'health'}:
        assert journal['migrations_started'] is True
    if failure == 'upgrade':
        assert not journal.get('migrations_completed')
    if failure == 'health':
        assert journal['migrations_completed'] is True


@pytest.mark.parametrize('target', ['cafe-v1.0.0', 'cafe-v0.9.0'])
def test_reinstall_or_downgrade_refused_before_any_service_change(release, target):
    module, Harness, git, app, data, old, new, source = release
    upgrade = Harness(target)
    with pytest.raises(RuntimeError, match='must be newer'):
        upgrade.perform()
    assert not any(event[0] == 'systemctl' for event in upgrade.events)


def test_dirty_or_untagged_installation_refused(release):
    module, Harness, git, app, data, old, new, source = release
    (app / 'uncommitted.txt').write_text('Keep local changes')
    with pytest.raises(RuntimeError, match='local changes'):
        Harness().perform()
    (app / 'uncommitted.txt').unlink()
    git('tag', '-d', 'cafe-v1.0.0', cwd=app)
    with pytest.raises(RuntimeError, match='exactly one'):
        Harness().perform()


def test_moved_published_tag_refused_without_checkout(release):
    module, Harness, git, app, data, old, new, source = release
    (source / 'version.txt').write_text('Unreviewed replacement of published release')
    git('commit', '-qam', 'Other commit')
    git('tag', '-fa', 'cafe-v1.1.0', '-m', 'Moved tag')
    with pytest.raises(RuntimeError, match='Command failed'):
        Harness().perform()
    assert git('rev-parse', 'HEAD', cwd=app) == old


def test_unrelated_release_history_is_refused(release):
    module, Harness, git, app, data, old, new, source = release
    git('checkout', '--orphan', 'unrelated')
    git('commit', '-qm', 'Unrelated root')
    git('tag', 'cafe-v1.2.0')
    upgrade = Harness('cafe-v1.2.0')
    with pytest.raises(RuntimeError, match='Command failed'):
        upgrade.perform()
    assert git('rev-parse', 'HEAD', cwd=app) == old
    assert json.loads((upgrade.directory / 'state.json').read_text())['backup_verified'] is True


def test_concurrent_upgrade_lock_refuses_second_run(release, monkeypatch, capsys):
    import sys
    module, Harness, git, app, data, old, new, source = release
    config = data / 'production.env'
    config.write_text('External configuration placeholder for lock test')
    python = app / 'backend/.venv/bin/python'
    python.parent.mkdir(parents=True)
    python.touch()
    monkeypatch.setattr(module, 'CONFIG', config)
    monkeypatch.setattr(module, '__file__', str(app / 'scripts/upgrade_cafe_release.py'))
    monkeypatch.setattr(module.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(sys, 'argv', ['upgrade_cafe_release.py', 'cafe-v1.1.0'])
    with (data / 'upgrades/upgrade.lock').open('a') as lock:
        module.fcntl.flock(lock, module.fcntl.LOCK_EX | module.fcntl.LOCK_NB)
        assert module.main() == 1
    assert 'Upgrade refused/failed' in capsys.readouterr().err
    assert not list((data / 'upgrades').glob('*/state.json'))


def test_shell_database_credentials_cannot_override_production_environment(release, monkeypatch):
    module, Harness, *_ = release
    monkeypatch.setenv('LOCAL_DATABASE_URL', 'postgresql+psycopg://wrong:password@127.0.0.1/wrong_database')
    monkeypatch.setenv('LOCAL_BACKUP_DATABASE_URL', 'postgresql://wrong:password@127.0.0.1/wrong_database')
    monkeypatch.setenv('ENVIRONMENT', 'development')
    monkeypatch.setenv('PGPASSWORD', 'wrong-password')
    monkeypatch.setenv('PYTHONPATH', '/wrong/python/modules')
    upgrade = Harness()
    assert upgrade.env['KALPVRIK_ENV_FILE'] == str(module.CONFIG)
    assert not {'LOCAL_DATABASE_URL', 'LOCAL_BACKUP_DATABASE_URL', 'ENVIRONMENT', 'PGPASSWORD', 'PYTHONPATH'} & upgrade.env.keys()


def test_upgrade_waits_for_activating_oneshot_backup_before_changing_code(release):
    module, Harness, *_ = release
    upgrade = Harness()
    upgrade.backup_states = ['activating', 'active', 'deactivating', 'inactive']
    upgrade.perform()
    checks = [i for i, args in enumerate(upgrade.events) if args[:3] == ['systemctl', 'show', 'kalpvrik-backup.service']]
    fetch = next(i for i, args in enumerate(upgrade.events) if args[:2] == ['git', 'fetch'])
    assert len(checks) == 4
    assert all(i < fetch for i in checks)


@pytest.mark.parametrize('tag', ['main', '--force', 'cafe-v1.01.0', 'cafe-v1.2.3;touch /tmp/x', 'cafe-v1.2.3-beta'])
def test_only_exact_numeric_release_names_are_accepted(release, tag):
    module, Harness, *_ = release
    with pytest.raises(RuntimeError, match='exact release tag'):
        Harness(tag)
