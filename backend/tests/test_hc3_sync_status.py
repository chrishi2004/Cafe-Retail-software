from __future__ import annotations

from datetime import UTC, datetime

from app.schemas.sync import EventEnvelope, EventSource
from app.sync.service import enqueue_outbox_event, stage_inbox_event
from tests.multi_venture_fixtures import login_headers
from tests.p5_fixtures import seed_p5_test_data


def _event(*, company_id: int, branch_id: int, source: EventSource, suffix: str) -> EventEnvelope:
    return EventEnvelope(
        event_type=f"hc3.scope.{suffix}",
        source=source,
        source_device_id="hc3-test-device" if source == EventSource.LOCAL_HUB else None,
        business_group_id="1",
        company_id=str(company_id),
        branch_id=str(branch_id),
        aggregate_type="scope_probe",
        aggregate_id=f"{company_id}-{branch_id}-{suffix}",
        aggregate_version=1,
        occurred_at=datetime.now(UTC),
        payload={"probe": suffix},
    )


def test_cafe_partner_sync_status_excludes_retail_queue_counts(
    client,
    db_session_factory,
) -> None:
    ids = seed_p5_test_data(db_session_factory)
    with db_session_factory() as db:
        with db.begin():
            stage_inbox_event(
                db,
                _event(
                    company_id=2,
                    branch_id=ids["cafe_branch"],
                    source=EventSource.CLOUD_GATEWAY,
                    suffix="cafe-in",
                ),
            )
            enqueue_outbox_event(
                db,
                _event(
                    company_id=2,
                    branch_id=ids["cafe_branch"],
                    source=EventSource.LOCAL_HUB,
                    suffix="cafe-out",
                ),
            )
            stage_inbox_event(
                db,
                _event(
                    company_id=1,
                    branch_id=ids["retail_branch"],
                    source=EventSource.CLOUD_GATEWAY,
                    suffix="retail-in",
                ),
            )
            enqueue_outbox_event(
                db,
                _event(
                    company_id=1,
                    branch_id=ids["retail_branch"],
                    source=EventSource.LOCAL_HUB,
                    suffix="retail-out",
                ),
            )

    response = client.get(
        "/api/sync/status",
        headers=login_headers(client, "cafe.admin@example.test"),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["company_id"] == 2
    assert payload["pending_inbox"] == 1
    assert payload["pending_outbox"] == 1
    assert payload["dead_letters"] == 0
