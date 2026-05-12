from agent_gateway.runtime.rectifier import DeepSeekRectifier


def test_rectifier_turns_delta_into_content_event() -> None:
    rectifier = DeepSeekRectifier()
    chunk = {"choices": [{"delta": {"content": "hello"}}]}

    events = rectifier.rectify(chunk, response_id="r1", message_id="m1")

    assert [event.type for event in events] == ["message.started", "content.delta"]
    assert events[0].data["message_id"] == "m1"
    assert events[1].data["response_id"] == "r1"
    assert events[1].data["message_id"] == "m1"
    assert events[1].data["text"] == "hello"


def test_rectifier_emits_message_started_once_per_message() -> None:
    rectifier = DeepSeekRectifier()

    first_events = rectifier.rectify(
        {"choices": [{"delta": {"content": "he"}}]},
        response_id="r1",
        message_id="m1",
    )
    second_events = rectifier.rectify(
        {"choices": [{"delta": {"content": "llo"}}]},
        response_id="r1",
        message_id="m1",
    )

    assert [event.type for event in first_events] == ["message.started", "content.delta"]
    assert [event.type for event in second_events] == ["content.delta"]
