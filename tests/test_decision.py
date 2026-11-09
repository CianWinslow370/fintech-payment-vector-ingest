import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))

from src.fintech_ingest import action_for_risk, chunk_event, PaymentEvent


def test_high_risk_event_is_sent_to_review():
    assert action_for_risk(0.82) == "review"
    assert action_for_risk(0.2) == "approve"


def test_chunk_keeps_event_context():
    event = PaymentEvent("evt", "acct", 10.0, "USD", "x" * 500, 0.1)
    parts = chunk_event(event, limit=100)
    assert len(parts) > 1
    assert all(part for part in parts)
