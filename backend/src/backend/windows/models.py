from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Span(BaseModel):
    name: str
    start_sec: float
    end_sec: float


def _known(value, allowed: tuple[str, ...], fallback: str) -> str:
    value = str(value).lower() if value is not None else fallback
    return value if value in allowed else fallback


class Action(Span):
    actor: Literal["cashier", "customer", "other", "unknown"] = "unknown"
    recipient: Literal["cashier", "customer", "none", "unknown"] = "none"

    @field_validator("actor", mode="before")
    @classmethod
    def known_actor(cls, value):
        return _known(value, ("cashier", "customer", "other", "unknown"), "unknown")

    @field_validator("recipient", mode="before")
    @classmethod
    def known_recipient(cls, value):
        return _known(value, ("cashier", "customer", "none", "unknown"), "unknown")


class WindowGraph(BaseModel):
    true_states: list[Span] = Field(default_factory=list)
    false_states: list[str] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)


class StateValue(Span):
    value: Literal["true", "false", "unknown"]

    @field_validator("value", mode="before")
    @classmethod
    def known_value(cls, value):
        return _known(value, ("true", "false", "unknown"), "unknown")


class DenseWindowGraph(BaseModel):
    states: list[StateValue] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)

    def window_graph(self) -> WindowGraph:
        held = [Span(name=s.name, start_sec=s.start_sec, end_sec=s.end_sec) for s in self.states if s.value == "true"]
        names = {span.name for span in held}
        denied = [s.name for s in self.states if s.value == "false" and s.name not in names]
        return WindowGraph(true_states=held, false_states=list(dict.fromkeys(denied)), actions=self.actions)


class Window(BaseModel):
    index: int
    start_sec: float
    end_sec: float
    frame_times: list[float]
    caption: str | None = None
    raw: str | None = None
    graph: WindowGraph | None = None
    error: str | None = None
    seconds: dict[str, float] = Field(default_factory=dict)
