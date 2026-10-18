"""PostgreSQL-only Café bootstrap, backups, restore drills and guarded upgrades."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import getpass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

BACKEND = Path(__file__).resolve().parents[1]
REPOSITORY = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


class BootstrapConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    group_name: str = Field(min_length=1, max_length=200)
    cafe_name: str = Field(min_length=1, max_length=200)
    legal_name: str = Field(min_length=1, max_length=240)
    company_code: str = Field(default='CAFE', min_length=1, max_length=40)
    slug: str = Field(default='cafe', pattern=r'^[a-z0-9-]{1,120}$')
    branch_name: str = Field(min_length=1, max_length=150)
    address: str = Field(default='', max_length=255)
    city: str = Field(default='', max_length=100)
    admin_name: str = Field(min_length=1, max_length=150)
    admin_email: EmailStr
    cashier_name: str = Field(min_length=1, max_length=150)
    cashier_email: EmailStr
    invoice_prefix: str = Field(default='CAFE-', min_length=1, max_length=30)


def configured_url():
    from app.core.config import DeploymentMode, settings
    if settings.deployment_mode != DeploymentMode.LOCAL_HUB:
        raise RuntimeError('Production maintenance must target the Local Hub, not the cloud gateway.')
    url = make_url(settings.local_runtime_database_url)
    if url.get_backend_name() != 'postgresql' or not url.database:
        raise RuntimeError('A configured PostgreSQL Local Hub database is required.')
    backup_url = os.environ.get('LOCAL_BACKUP_DATABASE_URL')
    if backup_url and identity(make_url(backup_url)) != identity(url):
        raise RuntimeError('Backup and application database targets differ. Refusing maintenance.')
    return url


def identity(url):
    return {'host': url.host or 'localhost', 'port': url.port or 5432, 'database': url.database}


def data_directory() -> Path:
    default = Path(os.environ.get('PROGRAMDATA', 'C:/ProgramData')) / 'Kalpvrik' if os.name == 'nt' else Path('/var/lib/kalpvrik')
    path = Path(os.environ.get('KALPVRIK_DATA_DIR', str(default))).expanduser()
    if not path.is_absolute():
        raise RuntimeError('KALPVRIK_DATA_DIR must be absolute and outside the repository.')
    path = path.resolve()
    if path == REPOSITORY or REPOSITORY in path.parents:
        raise RuntimeError('Production data and backups cannot be stored inside the repository.')
    return path


def backup_directory() -> Path:
    root = data_directory()
    requested = Path(os.environ.get('KALPVRIK_BACKUP_ROOT', str(root / 'backups' / 'postgres'))).resolve()
    if requested == REPOSITORY or REPOSITORY in requested.parents:
        raise RuntimeError('Backup path cannot be inside the repository, even if the data directory is its parent.')
    if root not in requested.parents:
        raise RuntimeError('Backups must be under KALPVRIK_DATA_DIR, outside the repository.')
    return requested


def pg_run(tool: str, arguments: list[str], url=None) -> str:
    env = os.environ.copy()
    args = [tool, *arguments]
    if url is not None:
        if url.password is not None:
            env['PGPASSWORD'] = url.password
        # Preserve TLS options without exposing credentials in process arguments.
        clean = url._replace(drivername='postgresql', password=None)
        args.extend(['--dbname', clean.render_as_string(hide_password=False)])
    result = subprocess.run(args, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode:
        raise RuntimeError(f'{tool} failed (exit {result.returncode}); no upgrade/restore was authorized to continue.')
    return result.stdout


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            sha.update(chunk)
    return sha.hexdigest()


def verify_archive(path: Path) -> dict:
    metadata = json.loads(Path(str(path) + '.json').read_text())
    expected = Path(str(path) + '.sha256').read_text().split()[0]
    if not path.is_file() or digest(path) != expected or metadata['sha256'] != expected:
        raise RuntimeError('Backup checksum verification failed.')
    with path.open('rb') as stream:
        if stream.read(5) != b'PGDMP':
            raise RuntimeError('A PostgreSQL custom-format archive is required.')
    if not pg_run('pg_restore', ['--list', str(path)]).strip():
        raise RuntimeError('Backup archive has no readable table of contents.')
    # Decode the entire archive, including compressed table data, without executing SQL.
    pg_run('pg_restore', ['--file', os.devnull, str(path)])
    return metadata


def backup(url, *, reason: str = 'daily') -> Path:
    retention = int(os.environ.get('KALPVRIK_BACKUP_RETENTION_DAYS', '30'))
    if retention < 30:
        raise RuntimeError('Backup retention must be at least 30 days.')
    dump_url = make_url(os.environ['LOCAL_BACKUP_DATABASE_URL']) if os.environ.get('LOCAL_BACKUP_DATABASE_URL') else url
    if identity(dump_url) != identity(url):
        raise RuntimeError('Backup and application database targets differ.')
    root = backup_directory()
    now = datetime.now(UTC)
    data_directory().mkdir(parents=True, exist_ok=True, mode=0o750)
    root.mkdir(parents=True, exist_ok=True, mode=0o750)
    destination = root / now.strftime('%Y-%m')
    destination.mkdir(parents=True, exist_ok=True, mode=0o750)
    archive = destination / f'cafe_{now:%Y%m%dT%H%M%S}_{uuid4().hex}.dump'
    partial = Path(str(archive) + '.partial')
    try:
        pg_run('pg_dump', ['--format=custom', '--no-owner', '--no-acl', '--file', str(partial)], dump_url)
        checksum = digest(partial)
        metadata = {'format_version': 1, 'created_at': now.isoformat(), 'source': identity(url),
                    'reason': reason, 'sha256': checksum}
        # A backup is only usable after archive, manifest and checksum are all present and verified.
        partial.replace(archive)
        Path(str(archive) + '.sha256').write_text(f'{checksum}  {archive.name}\n')
        Path(str(archive) + '.json').write_text(json.dumps(metadata, indent=2) + '\n')
        if os.name != 'nt':
            for path in (archive, Path(str(archive) + '.sha256'), Path(str(archive) + '.json')):
                path.chmod(0o600)
        verify_archive(archive)
    except Exception:
        partial.unlink(missing_ok=True)
        # Never leave a failed dump looking like a successful, restorable backup.
        for path in (archive, Path(str(archive) + '.sha256'), Path(str(archive) + '.json')):
            path.unlink(missing_ok=True)
        raise
    cutoff = (now - timedelta(days=retention)).timestamp()
    for old in root.glob('*/cafe_*.dump'):
        if old.stat().st_mtime < cutoff and Path(str(old) + '.json').is_file() and Path(str(old) + '.sha256').is_file():
            for path in (old, Path(str(old) + '.json'), Path(str(old) + '.sha256')):
                path.unlink()
    return archive


@contextmanager
def maintenance(url):
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            if not connection.scalar(text('SELECT pg_try_advisory_xact_lock(7351020261018)')):
                raise RuntimeError('Another production maintenance operation is running.')
            yield connection
    finally:
        engine.dispose()


def user_tables(connection) -> list[str]:
    # Check all non-system schemas, not only public, before a destructive or restore operation.
    return list(connection.execute(text("SELECT quote_ident(n.nspname)||'.'||quote_ident(c.relname) "
        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE c.relkind IN ('r','p') AND n.nspname NOT IN ('pg_catalog','information_schema') "
        "AND n.nspname NOT LIKE 'pg_toast%'" )).scalars())


def assert_safe_operation(connection, operation: str) -> None:
    if operation in {'reset', 'drop', 'recreate', 'seed', 'downgrade', 'stamp'}:
        populated = any(connection.execute(text(f'SELECT 1 FROM {table} LIMIT 1')).first()
                        for table in user_tables(connection))
        if populated:
            raise RuntimeError('Destructive/reset operation refused: the database contains data.')
        raise RuntimeError('Destructive maintenance is not a supported production operation.')
    if operation != 'upgrade':
        raise RuntimeError('Unsupported production upgrade operation.')
    tables = set(inspect(connection).get_table_names())
    if not tables or 'alembic_version' not in tables:
        raise RuntimeError('An existing Alembic-managed installation is required; use bootstrap for a new database.')
    from alembic.script import ScriptDirectory
    revisions = list(connection.execute(text('SELECT version_num FROM alembic_version')).scalars())
    script = ScriptDirectory.from_config(alembic_config())
    if not revisions:
        raise RuntimeError('Database has no Alembic revision; refusing to stamp or recreate it.')
    for revision in revisions:
        script.get_revision(revision)  # A newer/unknown database must never be downgraded implicitly.


def alembic_config(connection=None):
    from alembic.config import Config
    config = Config(str(BACKEND / 'alembic.ini'))
    config.set_main_option('script_location', str(BACKEND / 'alembic'))
    config.set_main_option('prepend_sys_path', str(BACKEND))
    if connection is not None:
        config.attributes['connection'] = connection
    return config


def mark_production(db: Session):
    from app.models import ProductionInstallation
    if db.get(ProductionInstallation, 1) is None:
        db.add(ProductionInstallation(id=1, installation_id=str(uuid4())))
        db.flush()


def configure_new_installation(db: Session, config: BootstrapConfig, admin_password: str, cashier_password: str):
    from app.core.security import hash_password
    from app.models import (Branch, BusinessGroup, BusinessProfile, BusinessType, Company, InvoiceSequence,
        InvoiceSequenceResetRule, InvoiceSequenceType, PaymentMode, PaymentModeType, User, UserRole)
    # The historical migration chain creates only canonical configuration placeholders.
    # This helper is called solely inside the pristine-database transaction after Alembic.
    group = db.get(BusinessGroup, 1)
    company = db.get(Company, 1)
    if group is None or company is None or company.code != 'HYBRID_RETAIL' or not company.is_demo:
        raise RuntimeError('Unexpected migration baseline; refusing production bootstrap.')
    group.name = config.group_name
    group.legal_name = config.legal_name
    company.business_type = BusinessType.CAFE
    company.name = company.trade_name = config.cafe_name
    company.legal_name = config.legal_name
    company.code = config.company_code
    company.slug = config.slug
    company.is_demo = False
    branch = Branch(company_id=company.id, name=config.branch_name, address=config.address, city=config.city)
    db.add(branch); db.flush()
    db.add_all([
        User(business_group_id=group.id, company_id=company.id, name=config.admin_name,
             email=str(config.admin_email).lower(), role=UserRole.ADMIN, password_hash=hash_password(admin_password)),
        User(business_group_id=group.id, company_id=company.id, branch_id=branch.id, name=config.cashier_name,
             email=str(config.cashier_email).lower(), role=UserRole.STAFF, password_hash=hash_password(cashier_password)),
    ])
    for name, kind in [('Cash', PaymentModeType.CASH), ('UPI', PaymentModeType.UPI), ('Card', PaymentModeType.CARD)]:
        db.add(PaymentMode(company_id=company.id, name=name, mode_type=kind, requires_reference=kind != PaymentModeType.CASH))
    profile = db.scalar(select(BusinessProfile).where(BusinessProfile.company_id == company.id))
    if profile is None:
        raise RuntimeError('Business profile migration baseline is missing.')
    profile.legal_name = config.legal_name
    profile.trade_name = config.cafe_name
    profile.address = config.address
    profile.city = config.city
    profile.email = str(config.admin_email).lower()
    sequence = db.scalar(select(InvoiceSequence).where(InvoiceSequence.company_id == company.id))
    if sequence is None:
        raise RuntimeError('Invoice sequence migration baseline is missing.')
    sequence.branch_id = branch.id
    sequence.prefix = config.invoice_prefix
    sequence.fiscal_year = 'continuous'
    sequence.reset_rule = InvoiceSequenceResetRule.NEVER
    sequence.invoice_type = InvoiceSequenceType.NON_GST_INVOICE
    # Continuous sequence avoids resetting invoice identifiers when code/year changes.
    mark_production(db)
    db.flush()


def bootstrap(url, config_path: Path):
    from alembic import command
    config = BootstrapConfig.model_validate_json(config_path.read_text())
    passwords = [os.environ.get(name) or getpass.getpass(prompt) for name, prompt in (
        ('CAFE_ADMIN_PASSWORD', 'New Café admin password: '), ('CAFE_CASHIER_PASSWORD', 'New cashier password: '))]
    if any(len(password) < 12 for password in passwords) or passwords[0] == passwords[1]:
        raise RuntimeError('Use distinct admin/cashier passwords with at least 12 characters.')
    if str(config.admin_email).lower() == str(config.cashier_email).lower():
        raise RuntimeError('Admin and cashier must have distinct email addresses.')
    data_directory().mkdir(parents=True, exist_ok=True, mode=0o750)
    with maintenance(url) as connection:
        if user_tables(connection):
            raise RuntimeError('Bootstrap is NEW-installation-only. Existing schemas/data will never be reset or reseeded.')
        command.upgrade(alembic_config(connection), 'head')
        with Session(bind=connection) as db:
            configure_new_installation(db, config, *passwords)
    print('New Café installation created. Enroll admin MFA using scripts.bootstrap_mfa before production login.')


def upgrade(url):
    from alembic import command
    with maintenance(url) as connection:
        assert_safe_operation(connection, 'upgrade')
        archive = backup(url, reason='pre-upgrade')
        print(f'Verified pre-upgrade backup: {archive}')
        command.upgrade(alembic_config(connection), 'head')
        with Session(bind=connection) as db:
            mark_production(db)
    print('Alembic upgrade completed. Existing business data was retained.')


def restore(url, archive: Path, target_env: str, confirmation: str):
    metadata = verify_archive(archive)
    raw = os.environ.get(target_env)
    if not raw:
        raise RuntimeError(f'Set {target_env} to a separate disposable PostgreSQL database URL.')
    target = make_url(raw)
    if target.get_backend_name() != 'postgresql' or not target.database or not target.database.startswith('cafe_restore_'):
        raise RuntimeError('Restore target must be a disposable PostgreSQL database named cafe_restore_*.')
    if confirmation != target.database:
        raise RuntimeError('Confirm the exact disposable target database name.')
    if target.database in {url.database, metadata['source']['database']} or identity(target) == identity(url):
        raise RuntimeError('Restore into the production/source database is forbidden.')
    with maintenance(target) as connection:
        if user_tables(connection):
            raise RuntimeError('Restore target is not empty. No --clean, DROP or overwrite is permitted.')
        pg_run('pg_restore', ['--single-transaction', '--exit-on-error', '--no-owner', '--no-acl', str(archive)], target)
    print('Restore drill completed in the separate disposable database; production was untouched.')


def main():
    from dotenv import load_dotenv
    env_file = os.environ.get('KALPVRIK_ENV_FILE')
    if env_file:
        path = Path(env_file)
        if not path.is_file():
            raise RuntimeError('KALPVRIK_ENV_FILE does not exist.')
        load_dotenv(path, override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    first = sub.add_parser('bootstrap'); first.add_argument('--config', type=Path, required=True)
    sub.add_parser('upgrade')
    sub.add_parser('status')
    verify = sub.add_parser('verify-backup'); verify.add_argument('--archive', type=Path, required=True)
    check = sub.add_parser('check-upgrade'); check.add_argument('--operation', default='upgrade')
    dump = sub.add_parser('backup'); dump.add_argument('--reason', choices=['daily', 'manual', 'pre-upgrade'], default='manual')
    drill = sub.add_parser('restore'); drill.add_argument('--archive', type=Path, required=True)
    drill.add_argument('--target-env', default='CAFE_RESTORE_DATABASE_URL'); drill.add_argument('--confirm-database', required=True)
    args = parser.parse_args()
    url = configured_url()
    data_directory()  # Reject code-directory storage even for otherwise read-only checks.
    if args.action == 'bootstrap': bootstrap(url, args.config)
    elif args.action == 'upgrade': upgrade(url)
    elif args.action == 'backup':
        with maintenance(url): print(f'Verified backup: {backup(url, reason=args.reason)}')
    elif args.action == 'verify-backup':
        metadata = verify_archive(args.archive.resolve())
        if metadata['source'] != identity(url):
            raise RuntimeError('Archive does not belong to the configured production database.')
        print('Backup archive, full decode, checksum and source identity verified.')
    elif args.action == 'status':
        with maintenance(url) as connection:
            assert_safe_operation(connection, 'upgrade')
            revisions = list(connection.execute(text('SELECT version_num FROM alembic_version')).scalars())
        print(json.dumps({'database': identity(url), 'alembic_revisions': revisions}))
    elif args.action == 'restore': restore(url, args.archive.resolve(), args.target_env, args.confirm_database)
    else:
        with maintenance(url) as connection: assert_safe_operation(connection, args.operation)
        print('Upgrade safety check passed; use the upgrade command for backup + Alembic.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Production maintenance refused/failed: {exc}', file=sys.stderr)
        raise SystemExit(1)
