from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EditState:
    source: str
    caret: int


class EditHistory:
    def __init__(self, source: str = "", caret: int = 0):
        self._states = [EditState(source, caret)]
        self._index = 0

    @property
    def current(self) -> EditState:
        return self._states[self._index]

    @property
    def can_undo(self) -> bool:
        return self._index > 0

    @property
    def can_redo(self) -> bool:
        return self._index + 1 < len(self._states)

    def reset(self, source: str, caret: int) -> None:
        self._states = [EditState(source, caret)]
        self._index = 0

    def push(self, source: str, caret: int) -> None:
        state = EditState(source, caret)
        if state == self.current:
            return
        del self._states[self._index + 1 :]
        self._states.append(state)
        self._index += 1

    def undo(self) -> EditState | None:
        if not self.can_undo:
            return None
        self._index -= 1
        return self.current

    def redo(self) -> EditState | None:
        if not self.can_redo:
            return None
        self._index += 1
        return self.current
