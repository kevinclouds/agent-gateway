from agent_gateway.canonical.events import CanonicalStreamEvent
from agent_gateway.runtime.rectifier import DeepSeekRectifier
from agent_gateway.runtime.engine import RuntimeEngine


def test_engine_applies_rectifier_output_into_projection() -> None:
    engine = RuntimeEngine()
    rectifier = DeepSeekRectifier()
    events = [CanonicalStreamEvent(type="response.started", data={"response_id": "r1"})]
    events.extend(
        rectifier.rectify(
            {"choices": [{"delta": {"content": "ok"}}]},
            response_id="r1",
            message_id="m1",
        )
    )
    events.append(CanonicalStreamEvent(type="response.completed", data={"response_id": "r1"}))

    response = engine.consume(events)

    assert response.status == "completed"
    assert response.response_id == "r1"
    assert response.messages[0].message_id == "m1"
    assert response.messages[0].role == "assistant"
    assert response.messages[0].segments[0]["text"] == "ok"


def test_engine_merges_multiple_rectified_deltas_into_one_message() -> None:
    engine = RuntimeEngine()
    rectifier = DeepSeekRectifier()
    events = [CanonicalStreamEvent(type="response.started", data={"response_id": "r1"})]
    events.extend(
        rectifier.rectify(
            {"choices": [{"delta": {"content": "he"}}]},
            response_id="r1",
            message_id="m1",
        )
    )
    events.extend(
        rectifier.rectify(
            {"choices": [{"delta": {"content": "llo"}}]},
            response_id="r1",
            message_id="m1",
        )
    )
    events.append(CanonicalStreamEvent(type="response.completed", data={"response_id": "r1"}))

    response = engine.consume(events)

    assert len(response.messages) == 1
    assert response.messages[0].segments == [{"type": "text", "text": "hello"}]
