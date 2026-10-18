"""Opt-in real browser → production API → disposable PostgreSQL acceptance test."""
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import build_opener, ProxyHandler, Request

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.mfa import encrypt_totp_secret
from app.models import Branch, Category, Inventory, MenuCategory, MenuItem, Product, Supplier, User
from scripts import cafe_production as ops
from tests.test_cafe_production_ops import pg_database, requires_postgres, snapshot

ROOT = Path(__file__).resolve().parents[2]
SECRET = 'acceptance-only-application-encryption-secret-123456789'
TOTP = 'JBSWY3DPEHPK3PXP'


@requires_postgres
@pytest.mark.skipif(os.environ.get('CAFE_RELEASE_BROWSER') != '1', reason='Set CAFE_RELEASE_BROWSER=1 with Playwright/Chromium installed and a built frontend.')
def test_production_cafe_browser_restart_backup_restore_and_upgrade(pg_database, tmp_path, monkeypatch):
    create, config = pg_database
    url = create()
    ops.bootstrap(url, config)
    engine = create_engine(url)
    with Session(engine) as db:
        branch = db.scalar(select(Branch))
        owner = db.scalar(select(User).where(User.role == 'admin'))
        owner.mfa_enabled = True
        owner.mfa_enrolled_at = datetime.now(UTC)
        owner.mfa_secret_encrypted = encrypt_totp_secret(TOTP, SECRET)
        category = Category(company_id=branch.company_id, name='Audit stock')
        supplier = Supplier(company_id=branch.company_id, name='Audit supplier')
        menu_category = MenuCategory(company_id=branch.company_id, branch_id=branch.id, name='Audit menu')
        db.add_all([category, supplier, menu_category]); db.flush()
        product = Product(company_id=branch.company_id, category_id=category.id, supplier_id=supplier.id,
            sku='AUDIT-ITEM', name='Audit Sandwich', unit_cost=40, selling_price=100)
        db.add(product); db.flush()
        db.add_all([Inventory(company_id=branch.company_id, branch_id=branch.id, product_id=product.id, quantity_on_hand=100),
            MenuItem(company_id=branch.company_id, branch_id=branch.id, product_id=product.id,
                category_id=menu_category.id, name=product.name, selling_price=100, available=True)])
        db.commit()
    engine.dispose()
    assert (ROOT / 'frontend/dist/index.html').is_file(), 'Build production frontend before browser acceptance.'
    env_file = tmp_path / 'production.env'
    env_file.write_text('\n'.join([
        'ENVIRONMENT=production', 'DEPLOYMENT_MODE=local_hub', 'KALPVRIK_PROFILE=cafe-v1',
        f'LOCAL_DATABASE_URL={url.render_as_string(hide_password=False)}', f'SECRET_KEY={SECRET}',
        'FRONTEND_ORIGIN=http://127.0.0.1:4173', 'FRONTEND_EXTRA_ORIGINS=',
        'API_DOCS_ENABLED=false', 'REQUIRE_PRIVILEGED_MFA=true',
        f'KALPVRIK_DATA_DIR={tmp_path / "durable-data"}', 'KALPVRIK_BACKUP_RETENTION_DAYS=30',
    ]) + '\n')
    env_file.chmod(0o600)
    # Do not inherit development application/database settings into production API.
    env = {key: value for key, value in os.environ.items() if key in {
        'PATH', 'HOME', 'LANG', 'LD_LIBRARY_PATH', 'CAFE_PLAYWRIGHT_MODULE'}}
    env.update(KALPVRIK_ENV_FILE=str(env_file), CAFE_AUDIT_DATABASE_URL=url.render_as_string(hide_password=False),
        CAFE_AUDIT_PYTHON=sys.executable, CAFE_AUDIT_TOTP=TOTP, CAFE_AUDIT_ARTIFACTS=str(tmp_path))
    processes = []
    log = (tmp_path / 'servers.log').open('a')
    def start():
        processes.extend([
            subprocess.Popen([sys.executable, '-m', 'uvicorn', 'operational_server:app', '--host', '127.0.0.1', '--port', '8000'],
                cwd=ROOT / 'backend', env=env, stdout=log, stderr=log),
            subprocess.Popen([sys.executable, str(ROOT / 'scripts/serve_spa.py'), '--directory', str(ROOT / 'frontend/dist'), '--bind', '127.0.0.1', '--port', '4173'],
                cwd=ROOT, env=env, stdout=log, stderr=log),
        ])
        opener = build_opener(ProxyHandler({}))
        for address in ('http://127.0.0.1:8000/api/health', 'http://127.0.0.1:4173/'):
            for _ in range(80):
                try:
                    with opener.open(address, timeout=1) as response:
                        assert response.status == 200
                    break
                except OSError:
                    if any(process.poll() is not None for process in processes):
                        pytest.fail('Acceptance server exited; inspect servers.log.')
                    time.sleep(0.1)
            else:
                pytest.fail('Acceptance server failed to start.')
        assert all(process.poll() is None for process in processes), 'Acceptance ports must belong to the launched production servers.'
        # Browser routing can bypass browser-generated preflights: verify the
        # actual production CORS boundary independently against the running API.
        request = Request('http://127.0.0.1:8000/api/cafe/billing/pos/checkout', method='OPTIONS', headers={
            'Origin': 'http://127.0.0.1:4173', 'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'authorization,content-type,idempotency-key',
        })
        with opener.open(request, timeout=5) as response:
            assert response.status == 200
            assert response.headers['Access-Control-Allow-Origin'] == 'http://127.0.0.1:4173'
            assert 'idempotency-key' in response.headers['Access-Control-Allow-Headers'].lower()
    def stop():
        for process in processes:
            process.terminate()
        for process in processes:
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
        processes.clear()
    try:
        for phase in ('operations', 'after-restart'):
            start()
            completed = subprocess.run(['node', str(ROOT / 'frontend/e2e/cafe-production-audit.cjs'), phase],
                cwd=ROOT / 'frontend', env=env, capture_output=True, text=True, timeout=180)
            stop()
            assert completed.returncode == 0, completed.stdout + completed.stderr + f'\nArtifacts: {tmp_path}'
            print(completed.stdout)
        before = snapshot(url)
        archive = ops.backup(url, reason='daily')
        ops.verify_archive(archive)
        restored = create('cafe_restore_')
        monkeypatch.setenv('CAFE_RESTORE_DATABASE_URL', restored.render_as_string(hide_password=False))
        ops.restore(url, archive, 'CAFE_RESTORE_DATABASE_URL', restored.database)
        assert snapshot(restored) == before
        ops.upgrade(url)
        assert snapshot(url) == before
        print('PASS daily verified pg_dump, disposable restore, and guarded upgrade: all database rows retained.')
    finally:
        stop()
        log.close()
