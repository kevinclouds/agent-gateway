from dataclasses import dataclass, field


@dataclass
class CanonicalBlock:
    kind: str
    permission_request_id: str
    permission_kind: str


@dataclass
class CanonicalMessage:
    message_id: str
    role: str
    segments: list[dict[str, str]] = field(default_factory=list)


@dataclass
class CanonicalToolCall:
    call_id: str
    name: str
    arguments: str = ""
    status: str = "started"


@dataclass
class CanonicalResponse:
    response_id: str
    turn_id: str | None = None
    status: str = "in_progress"
    usage: dict[str, int] = field(default_factory=dict)
    messages: list[CanonicalMessage] = field(default_factory=list)
    tool_calls: list[CanonicalToolCall] = field(default_factory=list)
    block: CanonicalBlock | None = None


@dataclass
class CanonicalTurn:
    turn_id: str
    model: str
    input_items: list[dict[str, object]]
    tools: list[dict[str, object]] = field(default_factory=list)
    tool_choice: object | None = None
