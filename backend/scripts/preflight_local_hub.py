"""Read-only Local Hub readiness checks. Exit 1 means deployment remains blocked."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from urllib.parse import urlparse

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from app.models import Company, User, UserRole


def inspect_configuration(settings):
    checks = []
    def check(name, ok, remedy):
        checks.append({'gate': name, 'passed': bool(ok), 'action': '' if ok else remedy})
    check('local_hub_mode', settings.deployment_mode == 'local_hub', 'Set DEPLOYMENT_MODE=local_hub.')
    check('production_mode', settings.environment.lower() in {'production', 'prod'}, 'Set ENVIRONMENT=production.')
    check('signing_secret', len(settings.secret_key) >= 32 and 'change-me' not in settings.secret_key,
          'Generate and securely retain a unique SECRET_KEY of at least 32 characters.')
    check('admin_mfa_required', settings.resolved_require_privileged_mfa, 'Require privileged MFA.')
    check('api_docs_disabled', not settings.resolved_api_docs_enabled, 'Disable public API documentation.')
    origins = settings.cors_origins
    check('explicit_origins', bool(origins) and all(urlparse(o).scheme in {'http', 'https'} and
          urlparse(o).hostname and '*' not in o for o in origins), 'Configure explicit frontend origins.')
    from sqlalchemy.engine import make_url
    url = make_url(settings.local_runtime_database_url)
    check('postgresql', url.get_backend_name() == 'postgresql', 'Use PostgreSQL for the Local Hub.')
    check('dedicated_database_role', url.username not in {None, 'postgres'}, 'Use a dedicated non-superuser database role.')
    return checks


def inspect_backup(root, max_age_hours):
    files = list(Path(root).glob('**/*.dump'))
    if not files:
        return {'gate': 'recent_verified_backup', 'passed': False, 'action': 'Create a backup and restore it into a separate database.'}
    latest = max(files, key=lambda p: p.stat().st_mtime)
    sidecar = Path(str(latest) + '.sha256')
    valid = False
    if sidecar.is_file():
        expected = sidecar.read_text().split()[0]
        with latest.open('rb') as stream:
            valid = hashlib.file_digest(stream, 'sha256').hexdigest() == expected
    fresh = 0 <= time.time() - latest.stat().st_mtime <= max_age_hours * 3600
    return {'gate': 'recent_verified_backup', 'passed': valid and fresh,
            'action': '' if valid and fresh else 'Create a fresh backup with a valid SHA-256 sidecar.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup-root', default=os.getenv('KALPVRIK_BACKUP_ROOT', '/var/lib/kalpvrik/backups/postgres'))
    parser.add_argument('--max-backup-age-hours', type=float, default=26)
    parser.add_argument('--configuration-only', action='store_true')
    args = parser.parse_args()
    try:
        from app.core.config import Settings
        settings = Settings()
        checks = inspect_configuration(settings)
    except Exception:
        print(json.dumps({'ready': False, 'checks': [{'gate': 'configuration', 'passed': False,
            'action': 'Invalid environment settings. Review configuration locally; secrets are not printed.'}]}))
        return 1
    if not args.configuration_only:
        for binary in ('pg_dump', 'pg_restore', 'psql'):
            checks.append({'gate': binary, 'passed': bool(shutil.which(binary)), 'action': f'Install PostgreSQL client tools if {binary} is missing.'})
        try:
            checks.append(inspect_backup(args.backup_root, args.max_backup_age_hours))
        except (OSError, IndexError):
            checks.append({'gate': 'recent_verified_backup', 'passed': False, 'action': 'Backup is unreadable or checksum sidecar is invalid.'})
        try:
            engine = create_engine(settings.local_runtime_database_url, connect_args={'connect_timeout': 5})
            with Session(engine) as db:
                revision = db.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
                config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
                config.set_main_option('script_location', str(Path(__file__).resolve().parents[1] / 'alembic'))
                expected = ScriptDirectory.from_config(config).get_heads()
                checks.append({'gate': 'migrations', 'passed': sorted(revision) == sorted(expected), 'action': 'Back up first, then apply migrations if heads differ.'})
                unsafe = db.scalar(text('SELECT rolsuper FROM pg_roles WHERE rolname = current_user'))
                checks.append({'gate': 'database_not_superuser', 'passed': not unsafe, 'action': 'Run under a dedicated non-superuser database role.'})
                companies = list(db.scalars(select(Company).where(Company.is_active.is_(True))))
                checks.append({'gate': 'live_business', 'passed': bool(companies) and not any(c.is_demo for c in companies), 'action': 'Initialize real business data and disable active demo ventures.'})
                admins = list(db.scalars(select(User).where(User.is_active.is_(True), User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]))))
                checks.append({'gate': 'admin_enrollment', 'passed': bool(admins) and all(u.mfa_enabled for u in admins), 'action': 'Enroll MFA for all active privileged accounts.'})
            engine.dispose()
        except Exception:
            checks.append({'gate': 'database_checks', 'passed': False, 'action': 'Database checks failed. Verify connectivity, migrations and permissions locally.'})
    print(json.dumps({'ready': all(c['passed'] for c in checks), 'scope': 'configuration' if args.configuration_only else 'host_preflight',
        'checks': checks, 'manual_gates': ['Restore drill with recorded timings', 'Printer and scanner tests',
        'LAN clients and internet-outage test', 'Cloud queue convergence and remote HTTPS access',
        'Full product acceptance matrix']}, indent=2))
    return 0 if all(c['passed'] for c in checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
