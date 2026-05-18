from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HistoryEntry:
    age: int
    text: str
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"age": self.age, "text": self.text, "tags": self.tags}

    @classmethod
    def from_dict(cls, data: dict) -> "HistoryEntry":
        return cls(age=data["age"], text=data["text"], tags=data.get("tags", []))

