"""Real PostgreSQL preservation tests; explicitly opt in with a disposable test server."""
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import (Branch, Company, Invoice, InvoiceSequence, MenuCategory, MenuItem,
                        PaymentMode, ProductionInstallation, User)
from app.services.production_safety import assert_demo_seed_allowed
from scripts import cafe_production as ops

ADMIN_URL = os.environ.get('CAFE_PRODUCTION_TEST_ADMIN_URL')
requires_postgres = pytest.mark.skipif(not ADMIN_URL, reason='Set CAFE_PRODUCTION_TEST_ADMIN_URL for disposable PostgreSQL integration tests.')


@pytest.fixture()
def pg_database(monkeypatch, tmp_path):
    if not ADMIN_URL:
        pytest.skip('Disposable PostgreSQL test server not configured.')
    admin = create_engine(ADMIN_URL, isolation_level='AUTOCOMMIT')
    databases = []
    def create(prefix='cafe_test_'):
        name = prefix + uuid4().hex[:12]
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        databases.append(name)
        return make_url(ADMIN_URL).set(database=name)
    monkeypatch.setenv('KALPVRIK_DATA_DIR', str(tmp_path / 'durable-data'))
    monkeypatch.delenv('KALPVRIK_BACKUP_ROOT', raising=False)
    monkeypatch.delenv('LOCAL_BACKUP_DATABASE_URL', raising=False)
    monkeypatch.setenv('CAFE_ADMIN_PASSWORD', 'ActualAdmin-Secret123!')
    monkeypatch.setenv('CAFE_CASHIER_PASSWORD', 'ActualCashier-Secret456!')
    config = tmp_path / 'install.json'
    config.write_text(json.dumps(dict(group_name='Production Test Group', cafe_name='Real Configured Cafe',
        legal_name='Configured Business', branch_name='Main Counter', admin_name='Owner',
        admin_email='owner@example.com', cashier_name='Cashier', cashier_email='cashier@example.com')))
    try:
        yield create, config
    finally:
        with admin.connect() as connection:
            for name in databases:
                connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


def snapshot(url):
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            return {table: list(connection.execute(text(f'SELECT row_to_json(t)::text FROM {table} t ORDER BY 1')).scalars())
                    for table in ops.user_tables(connection)}
    finally:
        engine.dispose()


@requires_postgres
def test_linux_preflight_reads_private_current_database_without_mutation(pg_database):
    import runpy
    from types import SimpleNamespace
    create, config = pg_database
    url = create()
    check = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'scripts/check_cafe_v1.py'))['check_database']
    settings = SimpleNamespace(runtime_database_url=url.render_as_string(hide_password=False))
    with pytest.raises(Exception):
        check(settings)  # Empty/uninitialized database cannot start the production API.
    ops.bootstrap(url, config)
    before = snapshot(url)
    check(settings)
    assert snapshot(url) == before


@requires_postgres
def test_bootstrap_only_new_database_no_fake_trading_and_repeat_refused(pg_database):
    create, config = pg_database
    url = create()
    ops.bootstrap(url, config)
    engine = create_engine(url)
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Company)) == 1
        assert db.scalar(select(Company)).is_demo is False
        assert db.scalar(select(Company)).name == 'Real Configured Cafe'
        assert {user.role.value for user in db.scalars(select(User))} == {'admin', 'staff'}
        assert {mode.name for mode in db.scalars(select(PaymentMode))} == {'Cash', 'UPI', 'Card'}
        assert db.scalar(select(InvoiceSequence)).next_number == 1
        for table in ('cafe_orders', 'invoices', 'sales', 'customers'):
            assert db.scalar(text('SELECT count(*) FROM ' + table)) == 0
        with pytest.raises(RuntimeError, match='production installation'):
            assert_demo_seed_allowed(db)  # Refuses even if ENVIRONMENT was forgotten.
    before = snapshot(url)
    with pytest.raises(RuntimeError, match='NEW-installation-only'):
        ops.bootstrap(url, config)
    assert snapshot(url) == before
    engine.dispose()


@requires_postgres
def test_verified_backup_upgrade_and_restore_preserve_actual_invoice(pg_database, monkeypatch):
    from app.core.scope import scope_context_for_user
    from app.schemas.cafe_pos import CafeCheckoutRequest
    from app.services.cafe_pos import checkout
    create, config = pg_database
    url = create()
    ops.bootstrap(url, config)
    engine = create_engine(url)
    with Session(engine) as db:
        cashier = db.scalar(select(User).where(User.role == 'staff'))
        branch = db.scalar(select(Branch))
        category = MenuCategory(company_id=1, name='Actual Menu')
        db.add(category); db.flush()
        item = MenuItem(company_id=1, branch_id=branch.id, category_id=category.id,
                        name='Actual Item', selling_price=100, available=True)
        db.add(item); db.commit()
        receipt = checkout(db, scope=scope_context_for_user(cashier), user=cashier,
            payload=CafeCheckoutRequest(branch_id=branch.id, items=[dict(menu_item_public_id=item.public_id, quantity=2)],
                payment_mode_id=db.scalar(select(PaymentMode.id).where(PaymentMode.name == 'Cash'))),
            idempotency_key='real-upgrade-preservation-001').receipt
        assert receipt.grand_total == 200
    before = snapshot(url)
    ops.upgrade(url)
    assert snapshot(url) == before
    archive = next(ops.backup_directory().glob('*/*.dump'))
    metadata = ops.verify_archive(archive)
    assert metadata['source']['database'] == url.database
    assert metadata['reason'] == 'pre-upgrade'
    target = create('cafe_restore_')
    monkeypatch.setenv('CAFE_RESTORE_DATABASE_URL', target.render_as_string(hide_password=False))
    ops.restore(url, archive, 'CAFE_RESTORE_DATABASE_URL', target.database)
    assert snapshot(target) == before
    assert snapshot(url) == before
    with pytest.raises(RuntimeError, match='not empty'):
        ops.restore(url, archive, 'CAFE_RESTORE_DATABASE_URL', target.database)
    monkeypatch.setenv('CAFE_RESTORE_DATABASE_URL', url.render_as_string(hide_password=False))
    with pytest.raises(RuntimeError):
        ops.restore(url, archive, 'CAFE_RESTORE_DATABASE_URL', url.database)
    archive.write_bytes(archive.read_bytes() + b'corrupt')
    with pytest.raises(RuntimeError, match='checksum'):
        ops.verify_archive(archive)
    engine.dispose()


@requires_postgres
def test_destructive_checks_block_resets_and_failed_backup_blocks_alembic(pg_database, monkeypatch):
    create, config = pg_database
    url = create()
    ops.bootstrap(url, config)
    before = snapshot(url)
    for action in ('reset', 'drop', 'recreate', 'seed', 'stamp', 'downgrade'):
        with ops.maintenance(url) as connection, pytest.raises(RuntimeError, match='contains data'):
            ops.assert_safe_operation(connection, action)
    def failed(*args, **kwargs):
        raise RuntimeError('pg_dump failed')
    monkeypatch.setattr(ops, 'backup', failed)
    with pytest.raises(RuntimeError, match='pg_dump failed'):
        ops.upgrade(url)
    assert snapshot(url) == before


def test_production_settings_reject_sqlite():
    with pytest.raises(ValueError, match='persistent PostgreSQL'):
        Settings(environment='production', local_database_url='sqlite:///temporary.db', _env_file=None)


def test_backup_paths_and_minimum_retention_are_enforced(monkeypatch, tmp_path):
    monkeypatch.setenv('KALPVRIK_DATA_DIR', str(ops.REPOSITORY / 'runtime-data'))
    with pytest.raises(RuntimeError, match='inside the repository'):
        ops.data_directory()
    monkeypatch.setenv('KALPVRIK_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('KALPVRIK_BACKUP_ROOT', str(ops.REPOSITORY / 'backups'))
    with pytest.raises(RuntimeError, match='inside the repository'):
        ops.backup_directory()
    monkeypatch.setenv('KALPVRIK_BACKUP_RETENTION_DAYS', '29')
    with pytest.raises(RuntimeError, match='at least 30'):
        ops.backup(make_url('postgresql://localhost/cafe_test_unused'))


def test_pg_tools_keep_password_out_of_process_arguments(monkeypatch):
    captured = {}
    def run(arguments, **kwargs):
        captured.update(arguments=arguments, **kwargs)
        return type('Result', (), {'returncode': 0, 'stdout': 'ok'})()
    monkeypatch.setattr(ops.subprocess, 'run', run)
    ops.pg_run('pg_dump', ['--format=custom'], make_url('postgresql+psycopg://cafe:VerySecret@localhost/cafe?sslmode=require'))
    assert 'VerySecret' not in ' '.join(captured['arguments'])
    assert captured['env']['PGPASSWORD'] == 'VerySecret'
    assert 'sslmode=require' in captured['arguments'][-1]


def test_retention_preserves_30_days_and_failed_archive_is_not_published(monkeypatch, tmp_path):
    monkeypatch.setenv('KALPVRIK_DATA_DIR', str(tmp_path))
    monkeypatch.delenv('KALPVRIK_BACKUP_ROOT', raising=False)
    monkeypatch.delenv('LOCAL_BACKUP_DATABASE_URL', raising=False)
    monkeypatch.setenv('KALPVRIK_BACKUP_RETENTION_DAYS', '30')
    def pg(tool, arguments, url=None):
        if tool == 'pg_dump':
            Path(arguments[arguments.index('--file') + 1]).write_bytes(b'PGDMP' + b'test-archive')
        return 'archive table of contents'
    monkeypatch.setattr(ops, 'pg_run', pg)
    url = make_url('postgresql://localhost/cafe_test_retention')
    old = ops.backup(url)
    recent = ops.backup(url)
    from datetime import datetime, UTC, timedelta
    os.utime(old, (0, (datetime.now(UTC) - timedelta(days=31)).timestamp()))
    os.utime(recent, (0, (datetime.now(UTC) - timedelta(days=29)).timestamp()))
    newest = ops.backup(url)
    assert not old.exists() and recent.exists() and newest.exists()
    assert Path(str(newest) + '.sha256').exists()
    def invalid(tool, arguments, url=None):
        if tool == 'pg_dump':
            Path(arguments[arguments.index('--file') + 1]).write_bytes(b'bad')
        return 'invalid'
    monkeypatch.setattr(ops, 'pg_run', invalid)
    with pytest.raises(RuntimeError, match='custom-format'):
        ops.backup(url)
    assert len(list(ops.backup_directory().glob('*/*.dump'))) == 2
    assert not list(ops.backup_directory().glob('*/*.partial'))


@requires_postgres
def test_upgrade_from_previous_revision_preserves_business_configuration(pg_database, monkeypatch):
    from alembic import command
    create, config_path = pg_database
    url = create()
    with ops.maintenance(url) as connection:
        command.upgrade(ops.alembic_config(connection), '20260821_0019')
        with Session(bind=connection) as db, monkeypatch.context() as patch:
            # Construct the previous release's real configuration before the marker migration existed.
            patch.setattr(ops, 'mark_production', lambda _db: None)
            ops.configure_new_installation(db, ops.BootstrapConfig.model_validate_json(config_path.read_text()),
                                          'AdminPreviousRelease!', 'CashierPreviousRelease!')
    before = snapshot(url)
    ops.upgrade(url)
    after = snapshot(url)
    for table in before:
        if table != 'public.alembic_version':
            assert after[table] == before[table]
    assert len(after['public.production_installations']) == 1
    assert '20261018_0020' in after['public.alembic_version'][0]


@requires_postgres
def test_bootstrap_failure_rolls_back_schema_and_can_retry(pg_database, monkeypatch):
    create, config = pg_database
    url = create()
    original = ops.configure_new_installation
    def interrupted(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError('installation interrupted')
    with monkeypatch.context() as patch:
        patch.setattr(ops, 'configure_new_installation', interrupted)
        with pytest.raises(RuntimeError, match='interrupted'):
            ops.bootstrap(url, config)
    assert snapshot(url) == {}
    ops.bootstrap(url, config)
    assert snapshot(url)['public.production_installations']


def test_runtime_uses_external_production_configuration_and_refuses_missing_file(monkeypatch, tmp_path):
    from app.core.config import get_settings
    external = tmp_path / 'local-hub.env'
    external.write_text('ENVIRONMENT=production\nLOCAL_DATABASE_URL=postgresql+psycopg://owner@localhost/persistent_cafe\n')
    for name in ('ENVIRONMENT', 'LOCAL_DATABASE_URL', 'DATABASE_URL'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('KALPVRIK_ENV_FILE', str(external))
    get_settings.cache_clear()
    try:
        configured = get_settings()
        assert configured.environment == 'production'
        assert configured.local_runtime_database_url.endswith('/persistent_cafe')
        external.unlink()
        get_settings.cache_clear()
        with pytest.raises(RuntimeError, match='refusing fallback'):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_repository_parent_data_root_cannot_allow_backups_in_checkout(monkeypatch):
    monkeypatch.setenv('KALPVRIK_DATA_DIR', str(ops.REPOSITORY.parent))
    monkeypatch.setenv('KALPVRIK_BACKUP_ROOT', str(ops.REPOSITORY / 'backups'))
    with pytest.raises(RuntimeError, match='inside the repository'):
        ops.backup_directory()
