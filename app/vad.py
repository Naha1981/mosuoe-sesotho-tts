from __future__ import annotations

from dataclasses import dataclass
import math
import struct


@dataclass
class VADConfig:
    sample_rate: int = 16000
    frame_ms: int = 20
    speech_threshold: float = 0.015
    min_speech_ms: int = 240
    end_silence_ms: int = 640
    pre_roll_ms: int = 160


@dataclass
class VADEvent:
    kind: str
    audio: bytes = b""


class EnergyVAD:
    """Small dependency-free VAD for the prototype.

    Input is mono signed 16-bit PCM. This is intentionally simple and replaceable;
    production phone audio should move to a stronger VAD once real recordings are
    available for tuning.
    """

    def __init__(self, config: VADConfig | None = None) -> None:
        self.config = config or VADConfig()
        self.frame_bytes = int(self.config.sample_rate * self.config.frame_ms / 1000) * 2
        self.pre_roll_frames = max(1, self.config.pre_roll_ms // self.config.frame_ms)
        self.min_speech_frames = max(1, self.config.min_speech_ms // self.config.frame_ms)
        self.end_silence_frames = max(1, self.config.end_silence_ms // self.config.frame_ms)
        self.reset()

    def reset(self) -> None:
        self.in_speech = False
        self.speech_frames = 0
        self.silence_frames = 0
        self.pre_roll: list[bytes] = []
        self.current: list[bytes] = []

    def _energy(self, frame: bytes) -> float:
        if len(frame) < 2:
            return 0.0
        count = len(frame) // 2
        samples = struct.unpack(f"<{count}h", frame[: count * 2])
        mean_square = sum(sample * sample for sample in samples) / (count * 32768.0 * 32768.0)
        return math.sqrt(mean_square)

    def feed(self, frame: bytes) -> list[VADEvent]:
        if not frame:
            return []
        if len(frame) != self.frame_bytes:
            raise ValueError(f"Expected {self.frame_bytes} bytes, received {len(frame)}")

        speech = self._energy(frame) >= self.config.speech_threshold
        events: list[VADEvent] = []

        if not self.in_speech:
            self.pre_roll.append(frame)
            self.pre_roll = self.pre_roll[-self.pre_roll_frames :]

            if speech:
                self.in_speech = True
                self.speech_frames = 1
                self.silence_frames = 0
                self.current = list(self.pre_roll)
                events.append(VADEvent("speech_started"))
            return events

        self.current.append(frame)
        if speech:
            self.speech_frames += 1
            self.silence_frames = 0
        else:
            self.silence_frames += 1

        if self.silence_frames >= self.end_silence_frames and self.speech_frames >= self.min_speech_frames:
            utterance = b"".join(self.current)
            events.append(VADEvent("utterance", utterance))
            self.reset()
        return events
