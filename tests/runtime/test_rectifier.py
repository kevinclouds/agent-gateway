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


def test_rectifier_turns_tool_call_deltas_into_tool_events() -> None:
    rectifier = DeepSeekRectifier()

    first_events = rectifier.rectify(
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_123",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": '{"city":"Bos',
                                },
                            }
                        ]
                    }
                }
            ]
        },
        response_id="r1",
        message_id="m1",
    )
    second_events = rectifier.rectify(
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "function": {"arguments": 'ton"}'},
                            }
                        ]
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        },
        response_id="r1",
        message_id="m1",
    )

    assert [event.type for event in first_events] == [
        "tool_call.started",
        "tool_call.arguments.delta",
    ]
    assert first_events[0].data["call_id"] == "call_123"
    assert first_events[0].data["name"] == "get_weather"
    assert first_events[1].data["text"] == '{"city":"Bos'
    assert [event.type for event in second_events] == [
        "tool_call.arguments.delta",
        "tool_call.completed",
    ]
    assert second_events[0].data["text"] == 'ton"}'
