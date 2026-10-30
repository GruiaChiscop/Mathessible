"""A small real-time synthesiser for graph exploration.

The instruments are Mathessible's own two-operator FM "clarinet" and
Karplus--Strong plucked voice, matching AudioFunctions+'s continuous and
discrete roles. Y controls pitch, x controls stereo position, and a quiet
filtered noise layer distinguishes negative values. Earcons are generated here
too; no AudioFunctions+ code or sound file is used.
"""

from __future__ import annotations

import math
import threading
from collections import deque

import numpy as np

from mathessible.sonification.graph import Sound

SAMPLE_RATE = 48_000
BLOCK_SIZE = 512
GAIN = 0.16

_EARCONS: dict[str, tuple[tuple[float, float], ...]] = {
    "edge": ((180.0, 0.07), (120.0, 0.10)),
    "axis": ((700.0, 0.055),),
    "gap": ((170.0, 0.04), (0.0, 0.035), (170.0, 0.04)),
    "bookmark": ((880.0, 0.04), (660.0, 0.04), (880.0, 0.06)),
}


def stereo_gains(position: float) -> tuple[float, float]:
    """Equal-power stereo gains for a pan from -1 (left) to 1 (right)."""
    position = max(-1.0, min(1.0, position))
    angle = (position + 1.0) * math.pi / 4
    return math.cos(angle), math.sin(angle)


def earcon(kind: str, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """A generated stereo earcon; an unknown kind is a short neutral tick."""
    segments = _EARCONS.get(kind, ((500.0, 0.06),))
    pieces: list[np.ndarray] = []
    phase = 0.0
    for pitch, duration in segments:
        count = max(1, round(duration * sample_rate))
        if pitch <= 0:
            pieces.append(np.zeros(count, dtype=np.float32))
            continue
        times = np.arange(count, dtype=np.float64) / sample_rate
        envelope = np.sin(np.pi * np.arange(count, dtype=np.float64) / count) ** 2
        wave = np.sin(phase + 2 * np.pi * pitch * times) * envelope * 0.2
        phase = float((phase + 2 * np.pi * pitch * count / sample_rate) % (2 * np.pi))
        pieces.append(wave.astype(np.float32))
    mono = np.concatenate(pieces)
    return np.column_stack((mono, mono))


class Synthesizer:
    """The real-time graph voice. The UI changes its target; PortAudio asks it for blocks."""

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
        self._lock = threading.Lock()
        self._sound = Sound(None, 0.0, False)
        self._stream: object | None = None
        self._carrier_phase = 0.0
        self._modulator_phase = 0.0
        self._frequency = 220.0
        self._gain = 0.0
        self._strike = 1.0
        self._pluck_pending: float | None = None
        self._pluck_buffer = np.empty(0, dtype=np.float64)
        self._pluck_index = 0
        self._pink = np.zeros(3, dtype=np.float64)
        self._random = np.random.default_rng()
        self._earcons: deque[np.ndarray] = deque()
        self._earcon_offset = 0

    def start(self) -> None:
        """Open the default output device. Import sounddevice only when sound is actually requested."""
        if self._stream is not None:
            return
        import sounddevice as sd

        stream = sd.OutputStream(
            samplerate=self.sample_rate,
            blocksize=BLOCK_SIZE,
            channels=2,
            dtype="float32",
            callback=self._callback,
        )
        stream.start()
        self._stream = stream

    def update(self, sound: Sound) -> None:
        with self._lock:
            if sound.strike:
                self._strike = 0.0
                if sound.discrete and sound.frequency is not None:
                    self._pluck_pending = sound.frequency
            if sound.discrete and sound.frequency is None:
                self._pluck_buffer = np.empty(0, dtype=np.float64)
            self._sound = sound

    def play_earcon(self, kind: str) -> None:
        with self._lock:
            self._earcons.append(earcon(kind, self.sample_rate))

    def silence(self) -> None:
        self.update(Sound(None, 0.0, False))

    def close(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            stream.stop()
            stream.close()

    def render(self, frames: int) -> np.ndarray:
        """Render one stereo block. Public so the signal can be tested without an audio device."""
        with self._lock:
            sound = self._sound
            queued = self._earcons[0] if self._earcons else None
            offset = self._earcon_offset
            pluck_pending, self._pluck_pending = self._pluck_pending, None

        target_frequency = sound.frequency or self._frequency
        target_gain = GAIN if sound.frequency is not None and not sound.discrete else 0.0
        output = np.zeros((frames, 2), dtype=np.float32)
        # Smooth frequency and level across a block; this prevents clicks while the cursor moves.
        frequencies = np.linspace(self._frequency, target_frequency, frames, endpoint=True)
        gains = np.linspace(self._gain, target_gain, frames, endpoint=True)
        detune = 2 ** (3 / 1200)
        modulation_steps = frequencies * 2 / self.sample_rate
        modulator = (self._modulator_phase + np.cumsum(modulation_steps)) % 1.0
        triangle = (8 / math.pi**2) * (
            np.sin(2 * np.pi * modulator)
            - np.sin(6 * np.pi * modulator) / 9
            + np.sin(10 * np.pi * modulator) / 25
            - np.sin(14 * np.pi * modulator) / 49
        )
        instantaneous = frequencies * detune + frequencies * triangle
        carrier = (self._carrier_phase + np.cumsum(instantaneous / self.sample_rate)) % 1.0
        loudness = np.clip((320 / np.maximum(20, frequencies)) ** 0.28, 0.55, 1.15)
        # A gentle strike for discrete notes; continuous mode remains at its sustain level.
        if self._strike < 1.0:
            attack = np.clip(self._strike + np.arange(frames) / (0.04 * self.sample_rate), 0, 1)
            self._strike = float(min(1.0, attack[-1]))
        else:
            attack = 1.0
        mono = np.sin(2 * np.pi * carrier) * gains * loudness * attack
        left, right = stereo_gains(sound.pan)
        output[:, 0], output[:, 1] = mono * left, mono * right
        if pluck_pending is not None:
            period = max(2, round(self.sample_rate / pluck_pending))
            self._pluck_buffer = self._random.uniform(-1, 1, period)
            self._pluck_index = 0
        if sound.discrete and self._pluck_buffer.size:
            pluck = self._render_pluck(frames) * 0.22
            output[:, 0] += pluck * left
            output[:, 1] += pluck * right
        if sound.negative:
            # This is a background sign, not another point at x: keep it centred.
            noise = self._pink_noise(frames) * 0.018
            output[:, 0] += noise
            output[:, 1] += noise

        if queued is not None:
            amount = min(frames, len(queued) - offset)
            output[:amount] += queued[offset : offset + amount]
            with self._lock:
                self._earcon_offset += amount
                if self._earcons and self._earcon_offset >= len(self._earcons[0]):
                    self._earcons.popleft()
                    self._earcon_offset = 0

        self._frequency, self._gain = float(frequencies[-1]), float(gains[-1])
        self._carrier_phase, self._modulator_phase = float(carrier[-1]), float(modulator[-1])
        return np.clip(output, -1, 1)

    def _render_pluck(self, frames: int) -> np.ndarray:
        """A local Karplus--Strong voice for the discrete guitar-like instrument."""
        result = np.empty(frames, dtype=np.float64)
        size = len(self._pluck_buffer)
        for frame in range(frames):
            index = self._pluck_index
            following = (index + 1) % size
            sample = self._pluck_buffer[index]
            self._pluck_buffer[index] = 0.99 * (sample + self._pluck_buffer[following]) / 2
            result[frame] = sample
            self._pluck_index = following
        return result

    def _pink_noise(self, frames: int) -> np.ndarray:
        """A compact three-pole approximation of pink noise, continuous between blocks."""
        white = self._random.standard_normal(frames)
        result = np.empty(frames, dtype=np.float64)
        a = (0.99765, 0.96300, 0.57000)
        b = (0.0990460, 0.2965164, 1.0526913)
        for index, sample in enumerate(white):
            for pole in range(3):
                self._pink[pole] = a[pole] * self._pink[pole] + b[pole] * sample
            result[index] = self._pink.sum() + 0.1848 * sample
        return result / 6

    def _callback(self, outdata: np.ndarray, frames: int, _time: object, _status: object) -> None:
        try:
            outdata[:] = self.render(frames)
        except (ArithmeticError, ValueError, RuntimeError):
            outdata.fill(0)
