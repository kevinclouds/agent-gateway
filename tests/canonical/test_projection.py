from agent_gateway.canonical.events import CanonicalStreamEvent
from agent_gateway.canonical.projection import ResponseProjection


def test_projection_builds_text_output_from_content_deltas() -> None:
    projection = ResponseProjection()
    projection.apply(CanonicalStreamEvent(type="response.started", data={"response_id": "r1"}))
    projection.apply(CanonicalStreamEvent(type="message.started", data={"message_id": "m1", "role": "assistant"}))
    projection.apply(CanonicalStreamEvent(type="content.delta", data={"message_id": "m1", "text": "hello"}))
    projection.apply(CanonicalStreamEvent(type="content.delta", data={"message_id": "m1", "text": " world"}))
    projection.apply(CanonicalStreamEvent(type="response.completed", data={"response_id": "r1"}))

    response = projection.snapshot()
    assert response.status == "completed"
    assert response.messages[0].segments == [{"type": "text", "text": "hello world"}]


def test_projection_records_permission_block() -> None:
    projection = ResponseProjection()
    projection.apply(
        CanonicalStreamEvent(
            type="permission.blocked",
            data={
                "response_id": "r1",
                "permission_request_id": "p1",
                "permission_kind": "command",
            },
        )
    )

    response = projection.snapshot()
    assert response.response_id == "r1"
    assert response.status == "blocked"
    assert response.block is not None
    assert response.block.permission_request_id == "p1"


def test_snapshot_returns_defensive_copy() -> None:
    projection = ResponseProjection()
    projection.apply(CanonicalStreamEvent(type="response.started", data={"response_id": "r1"}))
    projection.apply(CanonicalStreamEvent(type="message.started", data={"message_id": "m1", "role": "assistant"}))

    response = projection.snapshot()
    response.response_id = "mutated"
    response.messages.append({"unexpected": "shape"})  # type: ignore[arg-type]

    fresh_snapshot = projection.snapshot()
    assert fresh_snapshot.response_id == "r1"
    assert len(fresh_snapshot.messages) == 1
    assert fresh_snapshot.messages[0].message_id == "m1"
    assert fresh_snapshot.messages[0].role == "assistant"
    assert fresh_snapshot.messages[0].segments == []


def test_projection_accumulates_tool_call_arguments_and_completion() -> None:
    projection = ResponseProjection()
    projection.apply(CanonicalStreamEvent(type="response.started", data={"response_id": "r1"}))
    projection.apply(
        CanonicalStreamEvent(
            type="tool_call.started",
            data={"response_id": "r1", "call_id": "call_123", "name": "get_weather"},
        )
    )
    projection.apply(
        CanonicalStreamEvent(
            type="tool_call.arguments.delta",
            data={"response_id": "r1", "call_id": "call_123", "text": '{"city":"Bos'},
        )
    )
    projection.apply(
        CanonicalStreamEvent(
            type="tool_call.arguments.delta",
            data={"response_id": "r1", "call_id": "call_123", "text": 'ton"}'},
        )
    )
    projection.apply(
        CanonicalStreamEvent(
            type="tool_call.completed",
            data={"response_id": "r1", "call_id": "call_123"},
        )
    )

    response = projection.snapshot()
    assert response.tool_calls[0].name == "get_weather"
    assert response.tool_calls[0].arguments == '{"city":"Boston"}'
    assert response.tool_calls[0].status == "completed"
