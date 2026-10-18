"""Read-only source ancestry/removal guard. Never updates the frozen V1 manifest."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASELINE = '9ab1eb67cea5d6cb613a582455cc53099834cacc'
MANIFEST = ROOT / 'docs/baselines/cafe-v1-source.json'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def check(manifest_path=MANIFEST):
    manifest = json.loads(Path(manifest_path).read_text())
    if manifest['commit'] != BASELINE:
        raise RuntimeError('Frozen Cafe V1 commit changed; release review required.')
    subprocess.run(['git', 'merge-base', '--is-ancestor', BASELINE, 'HEAD'], cwd=ROOT, check=True)
    changed, removed = [], []
    for name, expected in manifest['sha256'].items():
        original = git('show', f'{BASELINE}:{name}')
        if hashlib.sha256(original).hexdigest() != expected:
            raise RuntimeError(f'Frozen manifest mismatch: {name}')
        path = ROOT / name
        if not path.is_file():
            removed.append(name)
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            changed.append(name)
    # Ensure dropping entries from the manifest cannot hide source removals.
    original_names = set(git('ls-tree', '-r', '--name-only', BASELINE).decode().splitlines())
    protected = {name for name in original_names if protected_path(name)}
    if protected != set(manifest['sha256']):
        raise RuntimeError('Frozen manifest coverage changed; release review required.')
    if removed:
        raise RuntimeError('Cafe V1 files removed/renamed: ' + ', '.join(removed))
    return {'baseline': BASELINE, 'head': git('rev-parse', 'HEAD').decode().strip(),
            'files_verified': len(protected), 'changed_files_require_review': changed,
            'removed_files': removed}


def protected_path(name):
    return name.startswith(('backend/app/', 'backend/alembic/', 'backend/alembic_cloud/',
                            'backend/scripts/', 'backend/tests/', 'frontend/src/',
                            'frontend/tests/', 'frontend/e2e/', 'scripts/', 'deploy/')) or name in {
        'backend/requirements.txt', 'backend/operational_server.py', 'backend/server.py',
        'frontend/package.json', 'frontend/package-lock.json'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(check(), indent=2))
