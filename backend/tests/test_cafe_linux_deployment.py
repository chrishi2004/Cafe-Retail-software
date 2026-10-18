"""Café-only deployment checks, including real compiled SPA delivery."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
from threading import Thread
from http.server import ThreadingHTTPServer
from functools import partial

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(os.name != 'posix', reason='Linux deployment profile tests.')


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def health():
    return load_script('check_cafe_v1')


def ready_checks(monkeypatch, health):
    monkeypatch.setattr(health, 'production_settings', lambda: object())
    monkeypatch.setattr(health, 'check_database', lambda settings: None)
    monkeypatch.setattr(health, 'check_api', lambda: None)
    monkeypatch.setattr(health, 'check_ui', lambda: None)


def test_disabled_optional_services_do_not_affect_health(monkeypatch, health):
    ready_checks(monkeypatch, health)
    commands = []
    def systemctl(args, **kwargs):
        commands.append(args)
        assert not any(word in ' '.join(args) for word in ('sync', 'cloud', 'menu-publish', 'qr', 'ai.service'))
        return subprocess.CompletedProcess(args, 0, stdout='success\n')
    monkeypatch.setattr(health.subprocess, 'run', systemctl)
    assert health.run_checks() == 0
    for unit in health.SERVICES:
        assert ['systemctl', 'is-active', '--quiet', unit] in commands
        assert ['systemctl', 'is-enabled', '--quiet', unit] in commands


@pytest.mark.parametrize('failure', ['postgresql.service', 'kalpvrik-api.service',
    'kalpvrik-frontend.service', 'kalpvrik-backup.timer', 'backup-result', 'database', 'api', 'ui'])
def test_required_dependency_failure_is_unhealthy(monkeypatch, health, failure, capsys):
    ready_checks(monkeypatch, health)
    def systemctl(args, **kwargs):
        return subprocess.CompletedProcess(args, 1 if failure in args else 0,
            stdout='exit-code\n' if failure == 'backup-result' else 'success\n')
    monkeypatch.setattr(health.subprocess, 'run', systemctl)
    def fail(*args):
        raise RuntimeError('secret-containing driver error must not be printed')
    for name in ('database', 'api', 'ui'):
        if failure == name:
            monkeypatch.setattr(health, 'check_' + name, fail)
    assert health.run_checks() == 1
    assert 'secret-containing' not in capsys.readouterr().err


def test_startup_preflight_needs_no_running_app_or_optional_services(monkeypatch, health):
    ready_checks(monkeypatch, health)
    def forbidden(*args, **kwargs):
        pytest.fail('Preflight must not depend on systemctl/HTTP before startup')
    monkeypatch.setattr(health.subprocess, 'run', forbidden)
    monkeypatch.setattr(health, 'check_api', forbidden)
    monkeypatch.setattr(health, 'check_ui', forbidden)
    assert health.run_checks(preflight=True) == 0


def test_production_api_response_required(monkeypatch, health):
    monkeypatch.setattr(health, 'fetch', lambda url: json.dumps(dict(status='healthy', deployment_mode='cloud_gateway', environment='production')).encode())
    with pytest.raises(RuntimeError, match='Operational API'):
        health.check_api()


def test_actual_static_server_serves_built_ui_and_detects_missing_assets(monkeypatch, health, tmp_path):
    spa = load_script('serve_spa')
    (tmp_path / 'assets').mkdir()
    (tmp_path / 'index.html').write_text('<!doctype html><div id="root"></div><script type="module" src="/assets/main.js"></script>')
    asset = tmp_path / 'assets/main.js'
    asset.write_text('console.log("built application");')
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(spa.SpaHandler, directory=str(tmp_path)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    fetch = health.fetch
    monkeypatch.setattr(health, 'fetch', lambda url: fetch(url.replace(':4173', f':{server.server_port}')))
    try:
        health.check_ui()
        asset.unlink()
        with pytest.raises(RuntimeError, match='asset is missing'):
            health.check_ui()
        (tmp_path / 'index.html').write_text('<script type="module" src="/@vite/client"></script>')
        with pytest.raises(RuntimeError, match='compiled production'):
            health.check_ui()
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_launcher_prefers_app_mode_and_keeps_user_profile_outside_code(tmp_path):
    browser = tmp_path / 'chromium'
    browser.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
    browser.chmod(0o755)
    result = subprocess.run(['/usr/bin/bash', str(ROOT / 'scripts/open_cafe.sh')],
        env={'PATH': str(tmp_path), 'HOME': str(tmp_path / 'desktop-user')}, text=True, capture_output=True, check=True)
    assert '--app=http://127.0.0.1:4173/' in result.stdout
    assert f'--user-data-dir={tmp_path}/desktop-user/.config/kalpvrik-cafe' in result.stdout


def test_profile_units_are_local_and_have_no_optional_dependencies():
    api = (ROOT / 'deploy/cafe-v1/kalpvrik-api.service.d/local-only.conf').read_text()
    frontend = (ROOT / 'deploy/cafe-v1/kalpvrik-frontend.service.d/local-only.conf').read_text()
    assert '--host 127.0.0.1' in api
    assert '--bind 127.0.0.1' in frontend
    assert 'check_cafe_v1.py --preflight' in api
    for content in (api, frontend):
        assert '0.0.0.0' not in content
        assert 'network-online' not in content
        assert 'sync.service' not in content


def test_profile_config_uses_external_file_without_cloud_credentials(monkeypatch, health, tmp_path):
    # Isolate dotenv's environment mutations from the rest of the suite.
    monkeypatch.setattr(health.os, 'environ', {})
    contents = (ROOT / 'deploy/cafe-v1/local-hub.env.example').read_text()
    config = tmp_path / 'production.env'
    config.write_text(contents.replace('REPLACE_WITH_A_LONG_RANDOM_SECRET', 'actual-random-secret-for-this-test-only-123456789'))
    monkeypatch.setenv('KALPVRIK_ENV_FILE', str(config))
    settings = health.production_settings()
    assert settings.deployment_mode.value == 'local_hub'
    assert settings.cloud_gateway_base_url is None
    assert settings.sync_device_secret is None
    assert settings.openai_api_key is None


def test_unedited_template_cannot_start_production(monkeypatch, health, tmp_path):
    monkeypatch.setattr(health.os, 'environ', {})
    config = tmp_path / 'production.env'
    config.write_text((ROOT / 'deploy/cafe-v1/local-hub.env.example').read_text())
    monkeypatch.setenv('KALPVRIK_ENV_FILE', str(config))
    with pytest.raises(RuntimeError, match='SECRET_KEY'):
        health.production_settings()


@pytest.mark.parametrize('host', ['192.168.1.50', 'db.example.com', '0.0.0.0'])
def test_remote_postgres_target_refused_before_connect(health, host):
    from types import SimpleNamespace
    with pytest.raises(RuntimeError, match='PostgreSQL URL must use'):
        health.check_database(SimpleNamespace(runtime_database_url=f'postgresql+psycopg://app:password@{host}/cafe'))


@pytest.mark.parametrize('listener', ['*', '0.0.0.0', 'localhost,192.168.1.5', '::'])
def test_public_database_listener_refused(monkeypatch, health, listener):
    from types import SimpleNamespace
    import sqlalchemy
    class Database:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def scalar(self, query):
            if str(query) == 'SELECT 1':
                return 1
            assert str(query) == 'SHOW listen_addresses'
            return listener
    engine = SimpleNamespace(connect=lambda: Database(), dispose=lambda: None)
    monkeypatch.setattr(sqlalchemy, 'create_engine', lambda *args, **kwargs: engine)
    with pytest.raises(RuntimeError, match='listens beyond loopback'):
        health.check_database(SimpleNamespace(runtime_database_url='postgresql+psycopg://app:password@127.0.0.1/cafe'))


@pytest.mark.skipif(getattr(os, 'geteuid', lambda: -1)() != 0, reason='Uninstaller root guard requires root; all mutations are stubbed.')
def test_uninstall_never_stops_postgres_or_removes_durable_paths(tmp_path):
    # Run the real shell flow with inert command shims; no host services/files change.
    commands = tmp_path / 'commands'
    for tool in ('systemctl', 'rm'):
        shim = tmp_path / tool
        shim.write_text(f'#!/bin/sh\nprintf "{tool} %s\\n" "$*" >> "$COMMAND_LOG"\n')
        shim.chmod(0o755)
    result = subprocess.run(['/usr/bin/bash', str(ROOT / 'scripts/uninstall_cafe_linux.sh'), '--remove-code'],
        env={'PATH': str(tmp_path), 'COMMAND_LOG': str(commands)}, text=True, capture_output=True, check=True)
    log = commands.read_text()
    assert 'rm -rf -- /opt/kalpvrik' in log
    assert 'postgresql' not in log
    assert '/var/lib/kalpvrik' not in log
    assert '/etc/kalpvrik' not in log
    assert 'Daily application backups are now stopped' in result.stdout
