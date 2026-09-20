import hashlib
import os
import time
from app.core.config import Settings
from scripts.preflight_local_hub import inspect_backup, inspect_configuration


def test_defaults_block_production():
    gates = {g['gate']: g['passed'] for g in inspect_configuration(Settings(_env_file=None, secret_key='change-me-in-development'))}
    assert not gates['production_mode']
    assert not gates['signing_secret']
    assert not gates['admin_mfa_required']


def test_verified_backup_rejects_corruption_and_staleness(tmp_path):
    assert not inspect_backup(tmp_path, 26)['passed']
    dump = tmp_path / 'test.dump'
    dump.write_bytes(b'archive')
    sidecar = tmp_path / 'test.dump.sha256'
    sidecar.write_text(hashlib.sha256(b'archive').hexdigest() + '  test.dump\n')
    assert inspect_backup(tmp_path, 26)['passed']
    dump.write_bytes(b'corrupt')
    assert not inspect_backup(tmp_path, 26)['passed']
    dump.write_bytes(b'archive')
    past = time.time() - 27 * 3600
    os.utime(dump, (past, past))
    assert not inspect_backup(tmp_path, 26)['passed']
