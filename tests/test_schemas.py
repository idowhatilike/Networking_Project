"""Kiểm thử cơ sở cho lược đồ sự kiện (F3, NT2)."""
from shared.schemas import EventRecord , EventType


def test_event_record_schema():
    rec = EventRecord(
        idempotency_key="550e8400-e29b-41d4-a716-446655440000",
        ts=1730000000,
        device_id="dev-01",
        child_id="child-01",
        type=EventType.DOMAIN_QUERY,
        subject="example.edu.vn",
        duration_sec=0,
        policy_id="pol-v1",
    )
    assert rec.type == EventType.DOMAIN_QUERY
    assert rec.subject == "example.edu.vn"
