from dataclasses import dataclass, field


@dataclass
class ConversationState:
    """Estado en memoria de una única sesión de consola."""

    active_skill: str | None = None
    pending_skill: str | None = None
    pending_skill_reason: str | None = None
    pending_skill_text: str | None = None
    fields: dict[str, object] = field(default_factory=dict)
    history: list[dict[str, str]] = field(default_factory=list)

    def update_fields(self, updates: dict[str, object]) -> None:
        self.fields.update(
            {key: value for key, value in updates.items() if value is not None}
        )

    def add_message(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})

    def reset(self) -> None:
        self.active_skill = None
        self.pending_skill = None
        self.pending_skill_reason = None
        self.pending_skill_text = None
        self.fields.clear()
        self.history.clear()
