"""Exercise replay ordering and single-use inputs at the student boundaries."""

from datetime import UTC, datetime
from itertools import permutations

import pytest

from lab28_platform.contracts import FEATURE_REFS, FeedbackPayload, IngestionEvent
from lab28_platform.integration_tasks import (
    dedupe_latest,
    event_headers,
    feast_online_request,
    readiness_status,
)


def test_empty_trace_is_omitted() -> None:
    assert event_headers("", "feedback:42") == [("idempotency-key", b"feedback:42")]


def test_single_use_batch_keeps_tie_winner_and_sorted_keys() -> None:
    first = IngestionEvent(
        event_id="event-001",
        idempotency_key="a",
        entity_id="student-7",
        occurred_at=datetime(2026, 9, 3, tzinfo=UTC),
        payload=FeedbackPayload(asker_id="student-7", text="Dịch vụ rất tốt", rating=5),
    )
    winner = first.model_copy(update={"event_id": "event-002"})
    other = first.model_copy(update={"idempotency_key": "b"})

    for delivery in permutations([first, winner, other]):
        batch = (event for event in delivery)
        assert dedupe_latest(batch) == [winner, other]
    assert first.event_id == "event-001"
    assert dedupe_latest(iter(())) == []


def test_feature_requests_do_not_share_mutable_feature_lists() -> None:
    request = feast_online_request("student-7")
    request["features"].clear()
    assert feast_online_request("student-8")["features"] == list(FEATURE_REFS)


@pytest.mark.parametrize("mandatory_first", [False, True])
def test_mandatory_failure_wins_for_single_use_probe_stream(mandatory_first: bool) -> None:
    probes = [
        {"ready": False, "mandatory": False},
        {"ready": False, "mandatory": True},
    ]
    if mandatory_first:
        probes.reverse()
    assert readiness_status(probe for probe in probes) == "not_ready"


def test_empty_probe_stream_is_ready() -> None:
    assert readiness_status(iter(())) == "ready"
