from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import Branch, BusinessType, Company
from app.services.cafe_cloud_publication import build_cafe_publication
from app.services.cloud_transport import push_menu_publication
from app.sync.device import DeviceIdentityStore, SettingsCredentialStore

DEFAULT_STATE_PATH = "/var/lib/kalpvrik/menu-publication-state.json"


def _state_path() -> Path:
    return Path(os.environ.get("KALPVRIK_PUBLICATION_STATE", DEFAULT_STATE_PATH))


def _load_state(path: Path) -> dict[str, dict[str, object]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not read menu publication state: {exc}") from exc
    return payload if isinstance(payload, dict) else {}


def _write_state(path: Path, state: dict[str, dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _content_fingerprint(payload) -> str:
    stable = payload.model_dump(
        mode="json",
        exclude={"publication_id", "version", "snapshot_at"},
    )
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _targets(company_id: int | None, branch_id: int | None) -> list[tuple[int, int]]:
    with SessionLocal() as db:
        statement = (
            select(Company.id, Branch.id)
            .join(Branch, Branch.company_id == Company.id)
            .where(
                Company.business_type == BusinessType.CAFE,
                Company.is_active.is_(True),
                Branch.is_active.is_(True),
            )
            .order_by(Company.id, Branch.id)
            .execution_options(scope_bypass=True)
        )
        if company_id is not None:
            statement = statement.where(Company.id == company_id)
        if branch_id is not None:
            statement = statement.where(Branch.id == branch_id)
        return [(int(row[0]), int(row[1])) for row in db.execute(statement).all()]


def publish(*, company_id: int | None, branch_id: int | None, force: bool) -> None:
    gateway = (settings.cloud_gateway_base_url or "").strip()
    if not gateway:
        raise SystemExit("CLOUD_GATEWAY_BASE_URL is required for menu publication.")
    secret = SettingsCredentialStore(settings).get_secret()
    if not secret:
        raise SystemExit("SYNC_DEVICE_SECRET is required for menu publication.")

    with SessionLocal() as db:
        with db.begin():
            identity = DeviceIdentityStore(settings).get_or_create(db)
    device_id = identity.device_id

    targets = _targets(company_id, branch_id)
    if not targets:
        print("No active Cafe branch matched the publication scope; nothing to publish.")
        return

    path = _state_path()
    state = _load_state(path)
    published = 0
    skipped = 0

    for index, (resolved_company, resolved_branch) in enumerate(targets):
        version = (time.time_ns() // 1_000) + index
        publication_id = uuid4()
        with SessionLocal() as db:
            payload = build_cafe_publication(
                db,
                company_id=resolved_company,
                branch_id=resolved_branch,
                version=version,
                publication_id=publication_id,
            )
        fingerprint = _content_fingerprint(payload)
        key = f"{resolved_company}:{resolved_branch}"
        previous = state.get(key) or {}
        if not force and previous.get("fingerprint") == fingerprint:
            skipped += 1
            print(f"Cafe {key}: unchanged; publication skipped.")
            continue

        result = push_menu_publication(
            gateway_base_url=gateway,
            device_id=device_id,
            installation_proof=secret,
            payload=payload,
        )
        state[key] = {
            "fingerprint": fingerprint,
            "publication_id": str(result.publication_id),
            "version": int(result.version),
            "state": result.state,
            "snapshot_at": result.snapshot_at.isoformat(),
        }
        _write_state(path, state)
        published += 1
        print(
            f"Cafe {key}: published version={result.version} publication_id={result.publication_id} "
            f"categories={len(payload.categories)} items={len(payload.items)} tables={len(payload.tables)}"
        )

    print(f"Menu publication complete: published={published}, skipped_unchanged={skipped}.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publish sanitized Cafe menu/QR snapshots from the Local Hub to the restricted cloud gateway."
    )
    parser.add_argument("--company-id", type=int)
    parser.add_argument("--branch-id", type=int)
    parser.add_argument("--force", action="store_true", help="Publish even when the local snapshot fingerprint is unchanged.")
    args = parser.parse_args()
    publish(company_id=args.company_id, branch_id=args.branch_id, force=args.force)


if __name__ == "__main__":
    main()
