"""F0 safety contracts and opt-in populated PostgreSQL migration/restore drill."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from scripts import cafe_production as ops
from scripts import full_v2_baseline as baseline
from tests.test_cafe_production_ops import pg_database, requires_postgres


def test_staging_target_is_explicit_and_cannot_alias_live(monkeypatch):
    monkeypatch.delenv('F0_STAGING_DATABASE_URL', raising=False)
    with pytest.raises(RuntimeError, match='explicitly'):
        baseline.staging_url()
    monkeypatch.setenv('F0_STAGING_DATABASE_URL', 'postgresql://localhost/live_cafe')
    with pytest.raises(RuntimeError, match='names'):
        baseline.staging_url()
    monkeypatch.setenv('F0_STAGING_DATABASE_URL', 'postgresql://localhost/cafe_restore_f0')
    monkeypatch.delenv('F0_STAGING_ACK', raising=False)
    with pytest.raises(RuntimeError, match='ACK'):
        baseline.staging_url()
    monkeypatch.setenv('F0_STAGING_ACK', 'isolated-not-live')
    for name in ('LOCAL_DATABASE_URL', 'LOCAL_BACKUP_DATABASE_URL', 'DATABASE_URL'):
        monkeypatch.delenv(name, raising=False)
    assert baseline.staging_url().database == 'cafe_restore_f0'
    monkeypatch.setenv('LOCAL_DATABASE_URL', 'postgresql://different-user@127.0.0.1:5432/cafe_restore_f0')
    with pytest.raises(RuntimeError, match='matches'):
        baseline.staging_url()


@pytest.mark.parametrize('kind,name', [('tables', 'invoices'), ('tables', 'invoice_payments'),
    ('tables', 'inventory'), ('tables', 'business_day_closures'), ('sequences', 'invoices_id_seq')])
def test_reconciliation_refuses_changed_or_missing_history(kind, name):
    before = {'format': 1, 'tables': {'invoices': 'a', 'invoice_payments': 'b',
              'inventory': 'c', 'business_day_closures': 'd'},
              'sequences': {'invoices_id_seq': [10, True]}, 'revisions': ['v1']}
    assert baseline.compare(before, copy.deepcopy(before))['historical_data_unchanged']
    after = copy.deepcopy(before)
    after[kind].pop(name)
    with pytest.raises(RuntimeError, match=name):
        baseline.compare(before, after)
    after[kind][name] = 'changed'
    with pytest.raises(RuntimeError, match=name):
        baseline.compare(before, after)


def test_empty_table_column_and_report_view_removal_is_blocked():
    before = {'format': 1, 'tables': {}, 'sequences': {}, 'revisions': ['v1'],
              'columns': {'invoices': {'invoice_number': {'type': 'VARCHAR(80)'}}},
              'views': {'report': 'original-definition-hash'}}
    after = copy.deepcopy(before)
    after['columns']['invoices'] = {}
    with pytest.raises(RuntimeError, match='columns.invoices.invoice_number'):
        baseline.compare(before, after)
    after = copy.deepcopy(before)
    after['views'] = {}
    with pytest.raises(RuntimeError, match='views.report'):
        baseline.compare(before, after)


def test_row_fingerprint_preserves_duplicates_and_changes():
    assert baseline.fingerprint(['a', 'a']) != baseline.fingerprint(['a'])
    assert baseline.fingerprint(['ab', 'c']) != baseline.fingerprint(['a', 'bc'])
    assert baseline.fingerprint([])['count'] == 0


def source_guard():
    path = Path(__file__).resolve().parents[2] / 'scripts/check_cafe_v1_baseline.py'
    spec = importlib.util.spec_from_file_location('f0_source_guard', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frozen_v1_source_ancestry_and_coverage():
    result = source_guard().check()
    assert result['files_verified'] >= 390
    assert result['removed_files'] == []


def test_source_manifest_cannot_hide_removed_files(tmp_path):
    guard = source_guard()
    manifest = json.loads(guard.MANIFEST.read_text())
    manifest['sha256'].pop(next(iter(manifest['sha256'])))
    path = tmp_path / 'incomplete.json'
    path.write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError, match='coverage'):
        guard.check(path)


def test_source_guard_detects_removal_and_manifest_tampering(tmp_path, monkeypatch):
    guard = source_guard()
    # Check only a copied path: never remove or edit a tracked Cafe V1 source.
    manifest = json.loads(guard.MANIFEST.read_text())
    name = next(iter(manifest['sha256']))
    manifest['sha256'] = {name: manifest['sha256'][name]}
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(manifest))
    monkeypatch.setattr(guard, 'protected_path', lambda candidate: candidate == name)
    monkeypatch.setattr(guard, 'ROOT', tmp_path)
    monkeypatch.setattr(guard, 'git', lambda *args: __import__('subprocess').check_output(
        ['git', *args], cwd=Path(__file__).resolve().parents[2]))
    from types import SimpleNamespace
    monkeypatch.setattr(guard, 'subprocess', SimpleNamespace(run=lambda *args, **kwargs: None))
    with pytest.raises(RuntimeError, match='removed/renamed'):
        guard.check(path)
    manifest['sha256'][name] = '0' * 64
    path.write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError, match='manifest mismatch'):
        guard.check(path)


@requires_postgres
def test_populated_v1_backup_restore_forward_migration_reconciles(pg_database, monkeypatch):
    from app.core.scope import scope_context_for_user
    from app.models import (Branch, BusinessDayClosure, Category, Customer, Inventory,
        MenuCategory, MenuItem, PaymentMode, Product, Supplier, User)
    from app.schemas.cafe_pos import CafeCheckoutRequest
    from app.services.business_day import business_today
    from app.services.cafe_pos import checkout
    from app.services.p9_reporting import get_cafe_dashboard, P9DashboardFilters
    create, config = pg_database
    source = create()
    # Pin the SOURCE schema to V1 even after future V2 migrations are added.
    # Fixture provisioning is confined to this newly created test database.
    from alembic import command
    import os
    with ops.maintenance(source) as connection:
        command.upgrade(ops.alembic_config(connection), '20261018_0020')
        with Session(bind=connection) as db:
            ops.configure_new_installation(db,
                ops.BootstrapConfig.model_validate_json(config.read_text()),
                os.environ['CAFE_ADMIN_PASSWORD'], os.environ['CAFE_CASHIER_PASSWORD'])
    engine = create_engine(source)
    with Session(engine) as db:
        cashier = db.scalar(select(User).where(User.role == 'staff'))
        owner = db.scalar(select(User).where(User.role == 'admin'))
        branch = db.scalar(select(Branch))
        company = branch.company_id
        category = Category(company_id=company, name='F0 stock')
        supplier = Supplier(company_id=company, name='F0 supplier')
        menu = MenuCategory(company_id=company, branch_id=branch.id, name='F0 menu')
        customer = Customer(company_id=company, branch_id=branch.id, name='F0 customer')
        db.add_all([category, supplier, menu, customer]); db.flush()
        product = Product(company_id=company, category_id=category.id, supplier_id=supplier.id,
                          sku='F0-ITEM', name='F0 item', unit_cost=40, selling_price=100)
        db.add(product); db.flush()
        item = MenuItem(company_id=company, branch_id=branch.id, product_id=product.id,
                        category_id=menu.id, name=product.name, selling_price=100, available=True)
        db.add_all([item, Inventory(company_id=company, branch_id=branch.id,
                                   product_id=product.id, quantity_on_hand=100)])
        db.commit()
        scope = scope_context_for_user(cashier)
        for number, mode_name in enumerate(('Cash', 'UPI', 'Card')):
            mode = db.scalar(select(PaymentMode).where(PaymentMode.name == mode_name))
            request = CafeCheckoutRequest(branch_id=branch.id,
                items=[dict(menu_item_public_id=item.public_id, quantity=2)],
                payment_mode_id=mode.id, reference_number=f'F0-{number}')
            key = f'f0-populated-preservation-{number}'
            first = checkout(db, scope=scope, user=cashier, payload=request, idempotency_key=key)
            replay = checkout(db, scope=scope, user=cashier, payload=request, idempotency_key=key)
            assert first.receipt.invoice_id == replay.receipt.invoice_id
        db.add(BusinessDayClosure(company_id=company, branch_id=branch.id,
            business_date=business_today(), opening_cash=100, cash_collections=200,
            expected_cash=300, counted_cash=300, variance=0, non_cash_total=400, status='closed'))
        db.commit()
        owner_id = owner.id
        filters = P9DashboardFilters(start_date=business_today(), end_date=business_today())
        report_before = get_cafe_dashboard(db, scope=scope_context_for_user(owner), filters=filters).model_dump(mode='json')
    engine.dispose()
    before = baseline.capture(source)
    assert before['revisions'] == ['20261018_0020']
    assert before['tables']['invoices']['count'] == 3
    assert before['tables']['invoice_payments']['count'] == 3
    archive = ops.backup(source, reason='pre-upgrade')
    metadata = ops.verify_archive(archive)
    assert metadata['sha256'] == ops.digest(archive)
    target = create('cafe_restore_')
    monkeypatch.setenv('F0_RESTORE_DATABASE_URL', target.render_as_string(hide_password=False))
    ops.restore(source, archive, 'F0_RESTORE_DATABASE_URL', target.database)
    assert baseline.compare(before, baseline.capture(target))['historical_data_unchanged']
    ops.upgrade(target)
    assert baseline.compare(before, baseline.capture(target))['historical_data_unchanged']
    assert baseline.capture(source) == before
    engine = create_engine(target)
    with Session(engine) as db:
        owner = db.get(User, owner_id)
        assert get_cafe_dashboard(db, scope=scope_context_for_user(owner), filters=filters).model_dump(mode='json') == report_before
        assert db.scalar(select(Inventory.quantity_on_hand)) == 94
    engine.dispose()
