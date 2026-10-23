"""How MathCAT reads a single character on its own ("open paren", "comma").

Reading in the built equation is MathCAT's; the symbol dictionary only
echoes what is typed. But MathCAT reads some leaves as their whole
structure (an interval's parens: "the open interval from a to b"), and a
few readings are of characters, not nodes (inside "4345", a selection).
For those, MathCAT reads the character alone, as `<math><mo>(</mo></math>`.
That needs an expression of its own, and MathCAT keeps one per thread
(its state is thread-local), so one long-lived worker thread does it,
never touching the equation being read. Starting MathCAT there costs
~40 ms (initialize, then the first speech loads its rules); every
character after that ~0.05 ms. `warm_up` pays the start in the
background, with the common characters, as soon as a navigator exists.
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Iterable
from xml.sax.saxutils import escape

Settings = tuple[str, str, str]  # (language, speech style, verbosity)

_CACHE: dict[tuple[Settings, str], str] = {}
_LOCK = threading.Lock()
_REQUESTS: queue.Queue[tuple[Settings, tuple[str, ...], queue.Queue[dict[str, str]] | None]] = queue.Queue()
_WORKER: threading.Thread | None = None
# What a built equation's characters mostly are: read ahead by `warm_up`.
COMMON = "()[]{}⟨⟩|‖,;:.!+-−±×·÷/=≠<>≤≥≈∈∉⊂⊆∪∩∞→←↔⇒⇔∑∏∫√′'0123456789"


def _tag(character: str) -> str:
    if character.isdigit():
        return "mn"
    return "mi" if character.isalpha() else "mo"


def _serve() -> None:
    """The worker: MathCAT initialized once (again only when the language/style changes)."""
    try:
        import matex_mathcat
    except ImportError:
        matex_mathcat = None
    current: Settings | None = None
    while True:
        settings, characters, reply = _REQUESTS.get()
        found: dict[str, str] = {}
        if matex_mathcat is not None:
            try:
                if settings != current:
                    matex_mathcat.initialize(*settings)
                    current = settings
                for character in characters:
                    tag = _tag(character)
                    matex_mathcat.set_expression(f"<math><{tag}>{escape(character)}</{tag}></math>")
                    found[character] = matex_mathcat.speak_expression().strip()
            except (OSError, RuntimeError, ValueError):
                current = None
        with _LOCK:
            for character in characters:
                _CACHE[(settings, character)] = found.get(character) or character
        if reply is not None:
            reply.put(found)


def _submit(settings: Settings, characters: tuple[str, ...], reply: queue.Queue[dict[str, str]] | None) -> None:
    global _WORKER
    with _LOCK:
        if _WORKER is None or not _WORKER.is_alive():
            _WORKER = threading.Thread(target=_serve, name="matex-lone-speech", daemon=True)
            _WORKER.start()
    _REQUESTS.put((settings, characters, reply))


def warm_up(language: str = "en", speech_style: str = "SimpleSpeak", verbosity: str = "Medium") -> None:
    """Start the worker and read the common characters, without waiting for it."""
    settings = (language, speech_style, verbosity)
    with _LOCK:
        missing = tuple(c for c in COMMON if (settings, c) not in _CACHE)
    if missing:
        _submit(settings, missing, None)


def lone_speeches(
    characters: Iterable[str], language: str = "en", speech_style: str = "SimpleSpeak", verbosity: str = "Medium"
) -> dict[str, str]:
    """MathCAT's speech of each character alone; an empty reading falls back to the character itself."""
    settings = (language, speech_style, verbosity)
    wanted = {character for character in characters if character}
    with _LOCK:
        missing = tuple(c for c in wanted if (settings, c) not in _CACHE)
    if missing:
        reply: queue.Queue[dict[str, str]] = queue.Queue()
        _submit(settings, missing, reply)
        try:
            reply.get(timeout=2)
        except queue.Empty:
            pass  # MathCAT is stuck: fall back to the characters themselves.
    with _LOCK:
        return {c: _CACHE.get((settings, c), c) for c in wanted}


def lone_speech(
    character: str, language: str = "en", speech_style: str = "SimpleSpeak", verbosity: str = "Medium"
) -> str:
    if character == " ":
        return "space"  # MathCAT says nothing for spacing; a selection of spaces still says what it is.
    return lone_speeches((character,), language, speech_style, verbosity).get(character, character)
