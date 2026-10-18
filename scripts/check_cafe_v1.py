#!/usr/bin/env python3
"""Read-only Café Linux readiness checks; optional cloud services are irrelevant."""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.request import build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
SERVICES = ('postgresql.service', 'kalpvrik-api.service',
            'kalpvrik-frontend.service', 'kalpvrik-backup.timer')
LOCAL_HOSTS = {'localhost', '127.0.0.1', '::1'}


class CheckFailure(RuntimeError):
    """Operator-safe diagnostic that never contains a connection string."""


def production_settings():
    from dotenv import load_dotenv
    path = Path(os.environ.get('KALPVRIK_ENV_FILE', '/etc/kalpvrik/local-hub.env'))
    if not path.is_file():
        raise CheckFailure('External production environment file is missing.')
    load_dotenv(path, override=False)
    from app.core.config import Settings, DeploymentMode
    from app.core.security_hardening import validate_production_security_settings
    settings = Settings(_env_file=path)
    if (settings.environment.lower() not in {'production', 'prod'}
            or settings.deployment_mode != DeploymentMode.LOCAL_HUB
            or os.environ.get('KALPVRIK_PROFILE') != 'cafe-v1'):
        raise CheckFailure('Production local_hub with KALPVRIK_PROFILE=cafe-v1 is required.')
    validate_production_security_settings(settings)
    if len(settings.secret_key) < 32 or settings.secret_key.startswith('REPLACE_'):
        raise CheckFailure('Replace SECRET_KEY with at least 32 random characters.')
    if settings.cors_origins != ['http://127.0.0.1:4173']:
        raise CheckFailure('Café local profile requires FRONTEND_ORIGIN=http://127.0.0.1:4173 and empty FRONTEND_EXTRA_ORIGINS.')
    if not settings.resolved_require_privileged_mfa:
        raise CheckFailure('Privileged MFA must remain enabled in production.')
    return settings


def check_database(settings):
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    url = make_url(settings.runtime_database_url)
    if url.get_backend_name() != 'postgresql' or url.host not in LOCAL_HOSTS:
        raise CheckFailure('Café PostgreSQL URL must use localhost, 127.0.0.1 or ::1.')
    engine = create_engine(url, connect_args={'connect_timeout': 5, 'options': '-c statement_timeout=5000'})
    try:
        with engine.connect() as db:
            if db.scalar(text('SELECT 1')) != 1:
                raise CheckFailure('PostgreSQL query failed.')
            addresses = {a.strip() for a in db.scalar(text('SHOW listen_addresses')).split(',') if a.strip()}
            if not addresses <= LOCAL_HOSTS:
                raise CheckFailure('PostgreSQL listens beyond loopback; set listen_addresses=localhost and restart PostgreSQL.')
            config = Config(str(ROOT / 'backend/alembic.ini'))
            config.set_main_option('script_location', str(ROOT / 'backend/alembic'))
            heads = set(ScriptDirectory.from_config(config).get_heads())
            if set(db.execute(text('SELECT version_num FROM alembic_version')).scalars()) != heads:
                raise CheckFailure('Database migration is not current; use the guarded upgrade procedure.')
            if db.scalar(text('SELECT count(*) FROM production_installations')) != 1:
                raise CheckFailure('Production bootstrap/guarded upgrade has not completed.')
    finally:
        engine.dispose()


def check_service(name):
    for state in ('is-active', 'is-enabled'):
        result = subprocess.run(['systemctl', state, '--quiet', name], timeout=10, check=False)
        if result.returncode:
            raise CheckFailure(f'{name} is not {state.removeprefix("is-")}.')


def check_backup_result():
    result = subprocess.run(['systemctl', 'show', 'kalpvrik-backup.service', '--property=Result', '--value'],
                            capture_output=True, text=True, timeout=10, check=True)
    if result.stdout.strip() != 'success':
        raise CheckFailure('Latest backup service failed; inspect journalctl -u kalpvrik-backup.service.')


def fetch(url):
    # Local readiness must also work on desktops with corporate HTTP proxies.
    with build_opener(ProxyHandler({})).open(url, timeout=5) as response:
        if response.status != 200:
            raise CheckFailure('HTTP check failed.')
        return response.read(2_000_000)


def check_api():
    result = json.loads(fetch('http://127.0.0.1:8000/api/health'))
    if (result.get('status') != 'healthy' or result.get('deployment_mode') != 'local_hub'
            or result.get('environment') not in {'production', 'prod'}):
        raise CheckFailure('Operational API did not report healthy production local_hub.')


class BuiltAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.scripts.append(dict(attrs).get('src', ''))


def check_ui():
    root = 'http://127.0.0.1:4173'
    index = fetch(root + '/')
    if fetch(root + '/cafe/pos') != index:
        raise CheckFailure('Local UI SPA route fallback failed.')
    parser = BuiltAssets()
    parser.feed(index.decode('utf-8'))
    assets = [src for src in parser.scripts if src.startswith('/assets/') and src.endswith('.js')]
    if not assets or any(src.startswith('/@vite') or src.startswith('/src/') for src in parser.scripts):
        raise CheckFailure('Frontend is not a compiled production build.')
    for asset in assets:
        content = fetch(root + asset)
        if not content or content.lstrip().startswith(b'<!doctype html'):
            raise CheckFailure('Frontend JavaScript asset is missing.')


def run_checks(preflight=False):
    settings = production_settings()
    checks = [('PostgreSQL (query, private listener, current schema)', lambda: check_database(settings))]
    if not preflight:
        checks += [(name, lambda name=name: check_service(name)) for name in SERVICES]
        checks += [('Latest backup result', check_backup_result), ('HTTP API health', check_api), ('Local built UI', check_ui)]
    failed = False
    for label, check in checks:
        try:
            check()
            print(f'[OK]   {label}')
        except Exception as exc:
            # Driver exceptions can include connection URLs: never print production secrets.
            detail = str(exc) if isinstance(exc, CheckFailure) else 'inspect configuration/service journal.'
            print(f'[FAIL] {label}: {detail}', file=sys.stderr)
            failed = True
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight', action='store_true', help='Check configuration/database before API startup.')
    args = parser.parse_args()
    try:
        return run_checks(args.preflight)
    except Exception as exc:
        detail = str(exc) if isinstance(exc, CheckFailure) else 'check external environment file (no secrets logged).'
        print(f'[FAIL] Café production configuration: {detail}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
