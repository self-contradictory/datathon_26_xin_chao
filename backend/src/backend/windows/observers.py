import time
from typing import Protocol

from backend.windows.clips import Clip
from backend.windows.model import WindowVLM, parse, schema_suffix
from backend.windows.models import DenseWindowGraph, Window, WindowGraph
from backend.windows.vocabulary import analyzer_prompt, caption_prompt, structured_prompt


class WindowObserver(Protocol):
    name: str

    def observe(self, clip: Clip) -> Window: ...


def _window(clip: Clip) -> Window:
    return Window(index=clip.index, start_sec=clip.start, end_sec=clip.end, frame_times=clip.times)


def _timed(window: Window, stage: str, call):
    began = time.perf_counter()
    result = call()
    window.seconds[stage] = round(time.perf_counter() - began, 2)
    return result


def _read_graph(window: Window, dense: bool = False) -> Window:
    try:
        window.graph = parse(DenseWindowGraph, window.raw).window_graph() if dense else parse(WindowGraph, window.raw)
    except ValueError as error:
        window.error = str(error)
    return window


class StructuredObserver:
    def __init__(self, model: WindowVLM, dense: bool = False, max_new_tokens: int = 1024) -> None:
        self.model, self.dense, self.max_new_tokens = model, dense, max_new_tokens
        self.name = "structured_dense" if dense else "structured"

    def observe(self, clip: Clip) -> Window:
        window = _window(clip)
        schema = DenseWindowGraph if self.dense else WindowGraph
        prompt = structured_prompt(clip.start, clip.end, self.dense) + schema_suffix(schema)
        window.raw = _timed(window, "observe", lambda: self.model.generate(prompt, clip, self.max_new_tokens))
        return _read_graph(window, self.dense)


class SemanticAnalyzer:
    def __init__(self, model: WindowVLM, max_new_tokens: int = 768) -> None:
        self.model, self.max_new_tokens = model, max_new_tokens

    def analyze(self, window: Window) -> Window:
        prompt = analyzer_prompt(window.start_sec, window.end_sec, window.caption) + schema_suffix(WindowGraph)
        window.raw = _timed(window, "analyze", lambda: self.model.generate(prompt, None, self.max_new_tokens))
        return _read_graph(window)


class CaptionObserver:
    name = "caption"

    def __init__(self, model: WindowVLM, analyzer: SemanticAnalyzer | None = None,
                 max_new_tokens: int = 320) -> None:
        self.model, self.max_new_tokens = model, max_new_tokens
        self.analyzer = analyzer or SemanticAnalyzer(model)

    def observe(self, clip: Clip) -> Window:
        window = _window(clip)
        prompt = caption_prompt(clip.start, clip.end)
        window.caption = _timed(window, "observe", lambda: self.model.generate(prompt, clip, self.max_new_tokens))
        return self.analyzer.analyze(window)
