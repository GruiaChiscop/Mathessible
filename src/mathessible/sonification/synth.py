"""A small real-time synthesiser for graph exploration.

The instruments are Mathessible's own, made to AudioFunctions+'s settings (its Tone.js clarinet and
guitar): a two-operator FM voice with a slow attack, and a plucked voice, a burst of pink noise, low-passed,
in a comb filter. Y controls pitch, x controls stereo position, and a quiet noise layer marks negative values.
The earcons are generated here too, to the length, pitch and level measured from AudioFunctions+'s; none of
its code or sound files is used.
"""

from __future__ import annotations

import math
import threading

import numpy as np

from mathessible.sonification.graph import Sound

SAMPLE_RATE = 48_000
BLOCK_SIZE = 512
GAIN = 0.398  # The FM voice: AudioFunctions+'s -8 dB.
ATTACK, RELEASE = 0.21, 0.05  # Its envelope, seconds.
PLUCK_LEVEL = 0.6
PLUCK_RESONANCE = 0.99  # The comb's feedback.
PLUCK_DAMPENING = 500.0  # The low-pass on the burst, Hz.
PLUCK_RELEASE = 1.0  # A stopped note's feedback falls to nothing in this many seconds.

# Each earcon's peak, and its (pitch, seconds) parts under one decay.
_EARCONS: dict[str, tuple[float, tuple[tuple[float, float], ...]]] = {
    "edge": (0.098, ((830.0, 0.14), (787.0, 0.14))),  # -20 dB.
    "start": (0.14, ((762.0, 0.016), (825.0, 0.016), (889.0, 0.031))),  # -15 dB.
    "axis": (0.117, ((530.0, 0.083), (1036.0, 0.083))),  # -12 dB.
    "gap": (0.038, ((2176.0, 0.033),)),  # -25 dB.
    "bookmark": (0.25, ((3988.0, 0.34), (2737.0, 0.34))),  # -12 dB.
    "tick": (0.126, ((1046.5, 0.05),)),  # -18 dB, C6.
}
_NEUTRAL = (0.1, ((500.0, 0.06),))


def stereo_gains(position: float) -> tuple[float, float]:
    """Equal-power stereo gains for a pan from -1 (left) to 1 (right)."""
    position = max(-1.0, min(1.0, position))
    angle = (position + 1.0) * math.pi / 4
    return math.cos(angle), math.sin(angle)


def earcon(kind: str, sample_rate: int = SAMPLE_RATE, position: float | None = None) -> np.ndarray:
    """A generated stereo earcon, in the middle or panned to `position`; an unknown kind is a short neutral
    tick."""
    peak, parts = _EARCONS.get(kind, _NEUTRAL)
    pitches = np.concatenate([np.full(max(1, round(seconds * sample_rate)), pitch) for pitch, seconds in parts])
    count = len(pitches)
    phase = 2 * np.pi * np.cumsum(pitches) / sample_rate
    decay = np.exp(-3 * np.arange(count) / count)  # To 5% at its end.
    fade = np.minimum(1.0, np.arange(count) / max(1.0, 0.002 * sample_rate))  # No click at its start.
    fade *= np.minimum(1.0, (count - np.arange(count)) / max(1.0, 0.002 * sample_rate))
    mono = (np.sin(phase) * decay * fade * peak).astype(np.float32)
    left, right = (1.0, 1.0) if position is None else stereo_gains(position)
    return np.column_stack((mono * left, mono * right))


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
        self._envelope = 0.0
        # The UI asks for a pluck or its end; only the audio thread (render) touches the pluck's buffer.
        self._pluck_pending: float | None = None
        self._pluck_stop = False
        self._pluck_buffer = np.empty(0, dtype=np.float64)
        self._pluck_index = 0
        self._pluck_resonance = PLUCK_RESONANCE
        self._pluck_releasing = False
        self._pink = np.zeros(3, dtype=np.float64)
        self._random = np.random.default_rng()
        self._earcons: list[list] = []  # [signal, frames played]: they sound together, not in turn.

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
            if sound.strike and sound.discrete and sound.frequency is not None:
                self._pluck_pending = sound.frequency
            if sound.discrete and sound.frequency is None:
                self._pluck_pending, self._pluck_stop = None, True
            self._sound = sound

    def play_earcon(self, kind: str, position: float | None = None) -> None:
        with self._lock:
            self._earcons.append([earcon(kind, self.sample_rate, position), 0])

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
            earcons = list(self._earcons)
            pluck_pending, self._pluck_pending = self._pluck_pending, None
            pluck_stop, self._pluck_stop = self._pluck_stop, False

        target_frequency = sound.frequency or self._frequency
        target = 1.0 if sound.frequency is not None and not sound.discrete else 0.0
        output = np.zeros((frames, 2), dtype=np.float32)
        # Across a block, so that the pitch moves without a click.
        frequencies = np.linspace(self._frequency, target_frequency, frames, endpoint=True)
        seconds = ATTACK if target > self._envelope else RELEASE
        ramp = np.arange(1, frames + 1) / (seconds * self.sample_rate)
        envelope = (
            np.minimum(target, self._envelope + ramp)
            if target > self._envelope
            else np.maximum(target, self._envelope - ramp)
        )
        detune = 2 ** (3 / 1200)
        modulation_steps = frequencies * 2 / self.sample_rate
        modulator = (self._modulator_phase + np.cumsum(modulation_steps)) % 1.0
        triangle = (8 / math.pi**2) * (
            np.sin(2 * np.pi * modulator)
            - np.sin(6 * np.pi * modulator) / 9
            + np.sin(10 * np.pi * modulator) / 25
            - np.sin(14 * np.pi * modulator) / 49
        )
        # The modulation rises with the tone: its envelope's attack is nearly the same.
        instantaneous = frequencies * detune + frequencies * triangle * envelope
        carrier = (self._carrier_phase + np.cumsum(instantaneous / self.sample_rate)) % 1.0
        mono = np.sin(2 * np.pi * carrier) * envelope * GAIN
        left, right = stereo_gains(sound.pan)
        output[:, 0], output[:, 1] = mono * left, mono * right
        if pluck_stop:
            self._pluck_releasing = True
        if pluck_pending is not None:
            self._strike_pluck(pluck_pending)
        if sound.discrete and self._pluck_buffer.size:
            pluck = self._render_pluck(frames)
            output[:, 0] += pluck * left
            output[:, 1] += pluck * right
        if sound.negative:
            # This is a background sign, not another point at x: keep it centred.
            noise = self._pink_noise(frames) * 0.0158  # -36 dB.
            output[:, 0] += noise
            output[:, 1] += noise

        for playing in earcons:
            signal, played = playing
            amount = min(frames, len(signal) - played)
            output[:amount] += signal[played : played + amount]
            playing[1] = played + amount
        with self._lock:
            self._earcons = [playing for playing in self._earcons if playing[1] < len(playing[0])]

        self._frequency, self._envelope = float(frequencies[-1]), float(envelope[-1])
        self._carrier_phase, self._modulator_phase = float(carrier[-1]), float(modulator[-1])
        return np.clip(output, -1, 1)

    def _strike_pluck(self, pitch: float) -> None:
        """A new note: a burst of low-passed pink noise, one period long, in the comb's delay line."""
        period = max(2, round(self.sample_rate / pitch))
        burst = self._pink_noise(period)
        coefficient = 1 - math.exp(-2 * math.pi * PLUCK_DAMPENING / self.sample_rate)
        state = 0.0
        for index, sample in enumerate(burst):
            state += coefficient * (sample - state)
            burst[index] = state
        self._pluck_buffer = burst * (PLUCK_LEVEL / max(1e-9, float(np.max(np.abs(burst)))))
        self._pluck_index = 0
        self._pluck_resonance, self._pluck_releasing = PLUCK_RESONANCE, False

    def _render_pluck(self, frames: int) -> np.ndarray:
        """The comb filter: the delay line read round and round, each pass quieter."""
        result = np.empty(frames, dtype=np.float64)
        size = len(self._pluck_buffer)
        done = 0
        while done < frames:
            amount = min(frames - done, size - self._pluck_index)
            part = slice(self._pluck_index, self._pluck_index + amount)
            result[done : done + amount] = self._pluck_buffer[part]
            self._pluck_buffer[part] *= self._pluck_resonance
            done += amount
            self._pluck_index = (self._pluck_index + amount) % size
        if self._pluck_releasing:
            self._pluck_resonance -= PLUCK_RESONANCE * frames / (PLUCK_RELEASE * self.sample_rate)
            if self._pluck_resonance <= 0:
                self._pluck_buffer = np.empty(0, dtype=np.float64)
                self._pluck_releasing = False
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
