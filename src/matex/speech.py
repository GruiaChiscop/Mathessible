from __future__ import annotations

from typing import Protocol


class AssistiveOutput(Protocol):
    def announce(self, text: str, interrupt: bool = True) -> None: ...


class ConsoleOutput:
    def announce(self, text: str, interrupt: bool = True) -> None:
        print(f"[MateX] {text}")


class PrismOutput:
    def __init__(self) -> None:
        from prism import Context

        self._context = Context()
        self._backend = self._context.create_best()

    def announce(self, text: str, interrupt: bool = True) -> None:
        features = self._backend.features
        if features.supports_output:
            self._backend.output(text, interrupt)
        else:
            self._backend.speak(text, interrupt)


def create_output() -> AssistiveOutput:
    try:
        return PrismOutput()
    except (ImportError, RuntimeError, ValueError, OSError):
        return ConsoleOutput()

