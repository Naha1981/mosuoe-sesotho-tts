import math
import struct

import pytest

from app.realtime import pcm_to_wav
from app.vad import EnergyVAD, VADConfig


def pcm_frame(amplitude: int, sample_rate: int = 16000, frame_ms: int = 20) -> bytes:
    count = sample_rate * frame_ms // 1000
    samples = [int(amplitude * math.sin(2 * math.pi * 440 * i / sample_rate)) for i in range(count)]
    return struct.pack(f"<{count}h", *samples)


def test_vad_emits_utterance_after_silence():
    vad = EnergyVAD(
        VADConfig(
            min_speech_ms=40,
            end_silence_ms=40,
            pre_roll_ms=20,
        )
    )
    events = []
    for _ in range(3):
        events.extend(vad.feed(pcm_frame(5000)))
    for _ in range(3):
        events.extend(vad.feed(pcm_frame(0)))

    assert any(event.kind == "speech_started" for event in events)
    utterances = [event.audio for event in events if event.kind == "utterance"]
    assert len(utterances) == 1
    assert len(utterances[0]) > 0


def test_vad_rejects_wrong_frame_size():
    vad = EnergyVAD()
    with pytest.raises(ValueError):
        vad.feed(b"\x00" * 10)


def test_pcm_to_wav_has_expected_header():
    wav = pcm_to_wav(pcm_frame(1000))
    assert wav[:4] == b"RIFF"
    assert wav[8:12] == b"WAVE"
