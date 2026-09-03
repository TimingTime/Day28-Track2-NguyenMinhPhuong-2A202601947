"""A slow group join must not turn a nonempty topic into a successful empty run."""

from types import SimpleNamespace
from typing import Any

import pytest

from lab28_platform import event_bus
from lab28_platform.contracts import FeedbackPayload, IngestionEvent
from lab28_platform.settings import KafkaSettings


class ScriptedConsumer:
    def __init__(self, steps: list[Any], assigned_after: int) -> None:
        self.steps = iter(steps)
        self.assigned_after = assigned_after
        self.calls = 0

    def subscribe(self, topics: list[str]) -> None:
        pass

    def poll(self, timeout: float) -> Any:
        self.calls += 1
        return next(self.steps, None)

    def assignment(self) -> list[int]:
        return [0] if self.calls >= self.assigned_after else []


def message(offset: int) -> SimpleNamespace:
    event = IngestionEvent(
        idempotency_key=f"feedback:{offset}",
        entity_id="asker-1",
        payload=FeedbackPayload(asker_id="asker-1", text="Dịch vụ rất tốt", rating=5),
    )
    return SimpleNamespace(
        error=lambda: None,
        headers=lambda: [],
        value=lambda: event.model_dump_json().encode("utf-8"),
        topic=lambda: "data.raw",
        partition=lambda: 0,
        offset=lambda: offset,
        key=lambda: b"asker-1",
    )


def batch_consumer(
    monkeypatch: pytest.MonkeyPatch, client: ScriptedConsumer
) -> event_bus.BatchConsumer:
    monkeypatch.setattr(event_bus, "Consumer", lambda _: client)
    monkeypatch.setattr(event_bus, "time", SimpleNamespace(monotonic=lambda: float(client.calls)))
    return event_bus.BatchConsumer(KafkaSettings.from_env())


def test_delayed_assignment_and_gaps_do_not_drop_pending_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = ScriptedConsumer([None] * 5 + [message(0), None, message(1)], assigned_after=6)
    consumer = batch_consumer(monkeypatch, client)

    decoded, poison = consumer.poll_batch(20)

    assert [entry.offset for entry in decoded] == [0, 1]
    assert poison == []
    assert client.calls == 11  # Stop only after three consecutive empty polls.


def test_assigned_empty_topic_still_finishes_after_idle_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = ScriptedConsumer([], assigned_after=0)
    consumer = batch_consumer(monkeypatch, client)

    assert consumer.poll_batch(20) == ([], [])
    assert client.calls == 3


def test_missing_assignment_is_an_error_instead_of_a_successful_empty_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = ScriptedConsumer([], assigned_after=100)
    consumer = batch_consumer(monkeypatch, client)

    with pytest.raises(event_bus.BrokerUnavailable, match="assignment timed out"):
        consumer.poll_batch(20, assignment_timeout=5)
    assert client.calls == 6
