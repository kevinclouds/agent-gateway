from dataclasses import dataclass, field


@dataclass
class CanonicalStreamEvent:
    type: str
    data: dict[str, object] = field(default_factory=dict)
