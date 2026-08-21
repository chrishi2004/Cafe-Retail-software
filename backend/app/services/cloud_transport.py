from __future__ import annotations

import hashlib
import hmac
import json
import time
from uuid import uuid4

import httpx

from app.schemas.cloud import MenuPublicationInput, MenuPublicationRead
from app.schemas.hc3 import CloudCommandBatch, CloudSyncPushRead
from app.schemas.hc4 import SignedHeartbeatInput, SignedHeartbeatRead, WriterLeaseInput, WriterLeaseRead
from app.schemas.sync import EventEnvelope
from app.sync.service import PermanentSyncError, RetryableSyncError, parse_retry_after


def gateway_api_url(gateway_base_url: str, path: str) -> str:
    """Build a cloud-gateway API URL without ever duplicating the /api prefix.

    Deployment documentation and older installations may provide either the host
    root (https://gateway.example.com) or the API root
    (https://gateway.example.com/api). Both forms are accepted deliberately.
    """
    base = gateway_base_url.strip().rstrip("/")
    if not base:
        raise ValueError("Cloud gateway base URL is required.")
    api_root = base if base.endswith("/api") else f"{base}/api"
    return f"{api_root}/{path.lstrip('/')}"


def _raise_sync_http(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    retry_after = parse_retry_after(response.headers.get("Retry-After"))
    if response.status_code == 429 or response.status_code >= 500:
        raise RetryableSyncError(
            f"Cloud gateway returned HTTP {response.status_code}.",
            code=f"cloud_http_{response.status_code}",
            retry_after_seconds=retry_after,
        )
    raise PermanentSyncError(
        f"Cloud gateway rejected synchronization with HTTP {response.status_code}.",
        code=f"cloud_http_{response.status_code}",
    )


def _device_headers(device_id: str, installation_proof: str) -> dict[str, str]:
    return {
        "X-Device-Id": device_id,
        "X-Device-Proof": installation_proof,
        "Content-Type": "application/json",
    }


def _signed_device_headers(
    device_id: str,
    installation_proof: str,
    payload: object,
    *,
    timestamp: str | None = None,
    nonce: str | None = None,
) -> dict[str, str]:
    if hasattr(payload, "model_dump"):
        body = payload.model_dump(mode="json")
    else:
        body = payload
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    resolved_timestamp = timestamp or str(int(time.time()))
    resolved_nonce = nonce or uuid4().hex
    canonical = f"{device_id}\n{resolved_timestamp}\n{resolved_nonce}\n{digest}".encode("utf-8")
    derived_key = hashlib.sha256(installation_proof.encode("utf-8")).hexdigest().encode("utf-8")
    signature = hmac.new(derived_key, canonical, hashlib.sha256).hexdigest()
    return {
        **_device_headers(device_id, installation_proof),
        "X-Device-Timestamp": resolved_timestamp,
        "X-Device-Nonce": resolved_nonce,
        "X-Device-Signature": signature,
    }


def _post_signed(
    *,
    url: str,
    device_id: str,
    installation_proof: str,
    payload: object,
    timeout_seconds: float,
) -> httpx.Response:
    body = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
    try:
        response = httpx.post(
            url,
            headers=_signed_device_headers(device_id, installation_proof, payload),
            json=body,
            timeout=timeout_seconds,
        )
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise RetryableSyncError(str(exc), code="cloud_unreachable") from exc
    _raise_sync_http(response)
    return response


def push_menu_publication(
    *,
    gateway_base_url: str,
    device_id: str,
    installation_proof: str,
    payload: MenuPublicationInput,
    timeout_seconds: float = 15.0,
) -> MenuPublicationRead:
    url = gateway_api_url(gateway_base_url, "/cloud/publications/menu")
    try:
        response = httpx.post(
            url,
            headers=_device_headers(device_id, installation_proof),
            json=payload.model_dump(mode="json"),
            timeout=timeout_seconds,
        )
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise RetryableSyncError(str(exc), code="cloud_unreachable") from exc
    _raise_sync_http(response)
    return MenuPublicationRead.model_validate(response.json())


def send_signed_heartbeat(
    *,
    gateway_base_url: str,
    device_id: str,
    installation_proof: str,
    payload: SignedHeartbeatInput,
    timeout_seconds: float = 15.0,
) -> SignedHeartbeatRead:
    response = _post_signed(
        url=gateway_api_url(gateway_base_url, "/cloud/devices/heartbeat"),
        device_id=device_id,
        installation_proof=installation_proof,
        payload=payload,
        timeout_seconds=timeout_seconds,
    )
    return SignedHeartbeatRead.model_validate(response.json())


def acquire_writer_lease(
    *,
    gateway_base_url: str,
    device_id: str,
    installation_proof: str,
    payload: WriterLeaseInput,
    timeout_seconds: float = 15.0,
) -> WriterLeaseRead:
    response = _post_signed(
        url=gateway_api_url(gateway_base_url, "/cloud/continuity/lease/acquire"),
        device_id=device_id,
        installation_proof=installation_proof,
        payload=payload,
        timeout_seconds=timeout_seconds,
    )
    return WriterLeaseRead.model_validate(response.json())


def renew_writer_lease(
    *,
    gateway_base_url: str,
    device_id: str,
    installation_proof: str,
    payload: WriterLeaseInput,
    timeout_seconds: float = 15.0,
) -> WriterLeaseRead:
    response = _post_signed(
        url=gateway_api_url(gateway_base_url, "/cloud/continuity/lease/renew"),
        device_id=device_id,
        installation_proof=installation_proof,
        payload=payload,
        timeout_seconds=timeout_seconds,
    )
    return WriterLeaseRead.model_validate(response.json())


def pull_cloud_commands(
    *,
    gateway_base_url: str,
    device_id: str,
    installation_proof: str,
    limit: int,
    timeout_seconds: float = 15.0,
) -> list[EventEnvelope]:
    url = gateway_api_url(gateway_base_url, "/cloud/sync/commands")
    try:
        response = httpx.get(
            url,
            headers=_device_headers(device_id, installation_proof),
            params={"limit": max(1, min(limit, 200))},
            timeout=timeout_seconds,
        )
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise RetryableSyncError(str(exc), code="cloud_unreachable") from exc
    _raise_sync_http(response)
    return CloudCommandBatch.model_validate(response.json()).events


class CloudGatewaySyncTransport:
    def __init__(
        self,
        *,
        gateway_base_url: str,
        device_id: str,
        installation_proof: str,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.gateway_base_url = gateway_base_url.strip().rstrip("/")
        self.device_id = device_id
        self.installation_proof = installation_proof
        self.timeout_seconds = timeout_seconds

    def send(self, event: EventEnvelope) -> dict[str, object]:
        url = gateway_api_url(self.gateway_base_url, "/cloud/sync/events")
        try:
            response = httpx.post(
                url,
                headers=_device_headers(self.device_id, self.installation_proof),
                json=event.model_dump(mode="json"),
                timeout=self.timeout_seconds,
            )
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise RetryableSyncError(str(exc), code="cloud_unreachable") from exc
        _raise_sync_http(response)
        return CloudSyncPushRead.model_validate(response.json()).model_dump(mode="json")
