#!/usr/bin/env python3
"""Upgrade an installed Linux Café release; never restore/reset production data."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from uuid import uuid4

APP = Path('/opt/kalpvrik')
DATA = Path('/var/lib/kalpvrik')
CONFIG = Path('/etc/kalpvrik/local-hub.env')
OS_ENV = {'PATH', 'HOME', 'USER', 'LOGNAME', 'LANG', 'LC_ALL', 'LC_CTYPE',
          'TMPDIR', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'SSH_AUTH_SOCK',
          'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY',
          'http_proxy', 'https_proxy', 'all_proxy', 'no_proxy'}
APP_UNITS = ('kalpvrik-api.service', 'kalpvrik-frontend.service')
TIMER = 'kalpvrik-backup.timer'
TAG = re.compile(r'cafe-v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z')


def version(tag):
    match = TAG.fullmatch(tag)
    if not match:
        raise RuntimeError('Use an exact release tag such as cafe-v1.1.0.')
    return tuple(map(int, match.groups()))


class Upgrade:
    def __init__(self, target):
        version(target)
        self.target = target
        # Shell/development DB URLs must not override the external production file.
        self.env = {key: value for key, value in os.environ.items() if key in OS_ENV}
        self.env['KALPVRIK_ENV_FILE'] = str(CONFIG)
        self.state = {'target_tag': target, 'started_at': datetime.now(timezone.utc).isoformat()}
        self.directory = None

    def command(self, args, *, cwd=None, env=None, check=True):
        result = subprocess.run([str(a) for a in args], cwd=cwd or APP, env=env or self.env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if self.directory:
            with (self.directory / 'commands.log').open('a') as log:
                log.write(f'\n$ {" ".join(map(str, args))}\n{result.stdout}\n')
        if check and result.returncode:
            detail = f'inspect {self.directory}/commands.log' if self.directory else 'check the installed checkout, Café health and prerequisites'
            raise RuntimeError(f'Command failed (exit {result.returncode}): {args[0]}; {detail}.')
        return result

    def git(self, *args):
        return self.command(['git', *args]).stdout.strip()

    def record(self, **updates):
        self.state.update(updates)
        self.state['updated_at'] = datetime.now(timezone.utc).isoformat()
        temporary = self.directory / 'state.json.tmp'
        with temporary.open('w') as output:
            temporary.chmod(0o600)
            output.write(json.dumps(self.state, indent=2) + '\n')
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(self.directory / 'state.json')
        descriptor = os.open(self.directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def stage(self, name):
        self.record(stage=name)
        print(f'[{name}]', flush=True)

    def maintenance(self, *args):
        return self.command(['runuser', '-u', 'kalpvrik', '--', 'env', f'KALPVRIK_ENV_FILE={CONFIG}',
            APP / 'backend/.venv/bin/python', APP / 'backend/scripts/cafe_production.py', *args]).stdout

    def health(self, *, check=True):
        return self.command(['runuser', '-u', 'kalpvrik', '--', 'env', f'KALPVRIK_ENV_FILE={CONFIG}',
            APP / 'backend/.venv/bin/python', APP / 'scripts/check_cafe_v1.py'], check=check)

    def installed(self):
        if Path(self.git('rev-parse', '--show-toplevel')).resolve() != APP.resolve():
            raise RuntimeError('/opt/kalpvrik must be the application Git checkout root.')
        if self.git('status', '--porcelain', '--untracked-files=all'):
            raise RuntimeError('Application checkout has local changes; preserve/review them before upgrading.')
        commit = self.git('rev-parse', 'HEAD')
        tags = [tag for tag in self.git('tag', '--points-at', 'HEAD').splitlines() if TAG.fullmatch(tag)]
        if len(tags) != 1:
            raise RuntimeError('Installed HEAD must have exactly one published cafe-vX.Y.Z tag. See CAFE_UPGRADE_GUIDE.md.')
        return tags[0], commit

    def unit_busy(self, unit, *, optional=False):
        result = self.command(['systemctl', 'show', unit, '--property=ActiveState', '--value'], check=not optional)
        if optional and result.returncode:
            return False
        state = result.stdout.strip()
        if state in {'inactive', 'failed'}:
            return False
        if state in {'active', 'activating', 'reloading', 'deactivating', 'refreshing'}:
            return True
        raise RuntimeError(f'Cannot determine service state for {unit}; refusing maintenance.')

    def perform(self):
        old_tag, old_commit = self.installed()
        if version(self.target) <= version(old_tag):
            raise RuntimeError('Requested release must be newer; automatic downgrade/reinstall is refused.')
        self.health()  # Includes real DB/private listener/current old schema, UI and backup timer.
        for unit in ('kalpvrik-sync.service', 'kalpvrik-menu-publish.service', 'kalpvrik-menu-publish.timer'):
            if self.unit_busy(unit, optional=True):
                raise RuntimeError(f'Stop optional writer/publication unit {unit} before maintenance.')
        self.directory = DATA / 'upgrades' / f'{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid4().hex[:8]}'
        self.directory.mkdir(mode=0o700)
        shutil.copyfile(Path(__file__), self.directory / 'upgrade_runner.py')
        self.record(previous_tag=old_tag, previous_commit=old_commit, stage='verified-installed-version')
        print(f'Installed: {old_tag} ({old_commit}); requested: {self.target}\nJournal: {self.directory}', flush=True)
        try:
            self.stage('stop-writers')
            self.command(['systemctl', 'disable', '--now', *APP_UNITS, TIMER])
            # Wait for an already-running daily backup rather than interrupt its dump.
            for _ in range(150):
                if not self.unit_busy('kalpvrik-backup.service'):
                    break
                time.sleep(2)
            else:
                raise RuntimeError('Existing daily backup is still running; leave maintenance stopped and investigate.')
            self.record(previous_database=json.loads(self.maintenance('status')))
            self.stage('pre-upgrade-backup')
            output = self.maintenance('backup', '--reason', 'pre-upgrade')
            paths = [line.removeprefix('Verified backup: ') for line in output.splitlines() if line.startswith('Verified backup: ')]
            if len(paths) != 1:
                raise RuntimeError('Backup did not report a unique verified archive.')
            archive = Path(paths[0]).resolve()
            if DATA.resolve() not in archive.parents:
                raise RuntimeError('Backup must be stored under /var/lib/kalpvrik.')
            self.record(backup_archive=str(archive))
            self.maintenance('verify-backup', '--archive', archive)
            self.record(backup_verified=True)
            self.stage('fetch-release')
            # No --force: a published tag that moved is an error, not an update.
            self.git('fetch', '--no-tags', 'origin', f'refs/tags/{self.target}:refs/tags/{self.target}')
            target_commit = self.git('rev-parse', '--verify', f'refs/tags/{self.target}^{{commit}}')
            self.command(['git', 'merge-base', '--is-ancestor', old_commit, target_commit])
            if old_commit == target_commit:
                raise RuntimeError('New version tag points to unchanged installed code.')
            # Required contracts must exist before switching executable code.
            for path in ('backend/requirements.txt', 'frontend/package-lock.json',
                         'scripts/upgrade_cafe.sh', 'scripts/check_cafe_v1.py', 'backend/scripts/cafe_production.py'):
                self.git('cat-file', '-e', f'{target_commit}:{path}')
            self.record(target_commit=target_commit)
            self.stage('checkout-release')
            self.git('checkout', '--detach', target_commit)
            if self.git('rev-parse', 'HEAD') != target_commit:
                raise RuntimeError('Release checkout verification failed.')
            self.stage('backend-dependencies')
            self.command([APP / 'backend/.venv/bin/python', '-m', 'pip', 'install', '-r', APP / 'backend/requirements.txt'])
            self.stage('frontend-dependencies')
            self.command(['npm', 'ci'], cwd=APP / 'frontend')
            self.stage('forward-migrations')
            self.record(migrations_started=True)
            # Reuse the established backup + transactional Alembic engine. No seed/reset.
            self.maintenance('upgrade')
            self.record(migrations_completed=True)
            self.stage('production-build')
            env = dict(self.env, VITE_API_BASE_URL='http://127.0.0.1:8000/api',
                VITE_OPERATIONAL_API_BASE_URL='http://127.0.0.1:8000/api', VITE_CLOUD_API_BASE_URL='http://127.0.0.1:8000/api')
            self.command(['npm', 'run', 'build'], cwd=APP / 'frontend', env=env)
            # Root builds must be readable/executable by the runtime service account.
            for path in ('backend/.venv', 'frontend/dist'):
                self.command(['chmod', '-R', 'a+rX,go-w', APP / path])
            self.stage('restart-services')
            self.command(['systemctl', 'restart', *APP_UNITS])
            self.command(['systemctl', 'enable', *APP_UNITS, TIMER])
            self.command(['systemctl', 'start', TIMER])
            self.stage('health-checks')
            for _ in range(15):
                if self.health(check=False).returncode == 0:
                    break
                time.sleep(2)
            else:
                raise RuntimeError('Post-upgrade Café health checks failed.')
            self.record(current_database=json.loads(self.maintenance('status')), stage='complete')
            print(f'Upgrade complete: {self.target}. Database retained. Journal: {self.directory}', flush=True)
        except BaseException:
            failed_stage = self.state['stage']
            # Health failure may follow a committed migration: never auto-start old code
            # or restore an old backup over potentially newer business transactions.
            try:
                stopped = self.command(['systemctl', 'disable', '--now', *APP_UNITS, TIMER], check=False)
                if stopped.returncode:
                    print('Service shutdown failed; stop the counter and inspect systemctl immediately.', file=sys.stderr)
            finally:
                self.record(stage='failed', failed_stage=failed_stage)
                print(f'Upgrade stopped at {failed_stage}; API/UI and timer must remain disabled/stopped (check systemctl).\n'
                      f'Keep PostgreSQL running. See CAFE_UPGRADE_GUIDE.md. Journal: {self.directory}', file=sys.stderr)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tag', help='Exact published cafe-vX.Y.Z release tag')
    args = parser.parse_args()
    try:
        version(args.tag)
        if os.geteuid() != 0 or Path(__file__).resolve().parents[1] != APP:
            raise RuntimeError('Run as root from the installed /opt/kalpvrik checkout.')
        if not CONFIG.is_file() or not (APP / 'backend/.venv/bin/python').is_file():
            raise RuntimeError('Existing Café production configuration and virtual environment are required.')
        if DATA.is_symlink():
            raise RuntimeError('/var/lib/kalpvrik must be a persistent directory, not a symlink.')
        directory = DATA / 'upgrades'
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        with (directory / 'upgrade.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            Upgrade(args.tag).perform()
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        print(f'Upgrade refused/failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    # Checked-out code/dependencies must remain readable by the runtime account;
    # journals live in their own root-only directory and contain no credentials.
    os.umask(0o022)
    raise SystemExit(main())
