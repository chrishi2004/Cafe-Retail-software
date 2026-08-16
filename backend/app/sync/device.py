from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.models.sync import SyncDevice, SyncDeviceStatus


@dataclass(frozen=True)
class DeviceIdentity:
    device_id: str
    credential_ref: str | None


class CredentialStore(Protocol):
    """Secret lookup boundary. Implementations must never persist raw credentials in the database."""

    def get_secret(self) -> str | None:
        ...


class SettingsCredentialStore:
    """Reads the device secret from server-side settings and exposes only its value to transport code."""

    def __init__(self, configured_settings: Settings = settings) -> None:
        self._settings = configured_settings

    def get_secret(self) -> str | None:
        secret: SecretStr | None = self._settings.sync_device_secret
        if secret is None:
            return None
        value = secret.get_secret_value().strip()
        return value or None


class DeviceIdentityStore:
    """Persists stable installation identity while keeping the credential itself out of PostgreSQL."""

    def __init__(self, configured_settings: Settings = settings) -> None:
        self._settings = configured_settings

    def get_or_create(self, db: Session) -> DeviceIdentity:
        configured_id = (self._settings.sync_device_id or "").strip() or None
        credential_ref = (self._settings.sync_device_credential_ref or "").strip() or None

        if configured_id:
            device = db.scalar(select(SyncDevice).where(SyncDevice.device_id == configured_id))
        else:
            device = db.scalar(
                select(SyncDevice)
                .where(SyncDevice.status == SyncDeviceStatus.ACTIVE)
                .order_by(SyncDevice.id.asc())
                .limit(1)
            )

        now = datetime.now(UTC)
        if device is None:
            device = SyncDevice(
                device_id=configured_id or str(uuid4()),
                display_name=self._settings.sync_device_name,
                credential_ref=credential_ref,
                status=SyncDeviceStatus.ACTIVE,
                last_started_at=now,
                last_seen_at=now,
            )
            db.add(device)
            db.flush()
        else:
            device.display_name = self._settings.sync_device_name or device.display_name
            device.credential_ref = credential_ref or device.credential_ref
            device.last_started_at = now
            device.last_seen_at = now
            db.flush()

        return DeviceIdentity(device_id=device.device_id, credential_ref=device.credential_ref)

    def touch(self, db: Session, device_id: str) -> None:
        device = db.scalar(select(SyncDevice).where(SyncDevice.device_id == device_id))
        if device is None:
            return
        device.last_seen_at = datetime.now(UTC)
        db.flush()
