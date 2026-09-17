from __future__ import annotations

import asyncio
import io
import struct
import uuid
import wave

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from .call import calls
from .services import engine
from .vad import EnergyVAD, VADConfig

AUDIO_SOCKET_HOST = "0.0.0.0"
AUDIO_SOCKET_PORT = 9019
AUDIO_TYPE = 0x10
UUID_TYPE = 0x01
HANGUP_TYPE = 0x00
ERROR_TYPE = 0xFF
FRAME_BYTES_8K = 320


def _frame(kind: int, payload: bytes = b"") -> bytes:
    return bytes((kind,)) + struct.pack(">H", len(payload)) + payload


def _resample_pcm(pcm: bytes, source_rate: int, target_rate: int) -> bytes:
    if source_rate == target_rate:
        return pcm
    samples = np.frombuffer(pcm, dtype="<i2")
    if samples.size == 0:
        return b""
    converted = resample_poly(samples.astype(np.float32), target_rate, source_rate)
    converted = np.clip(converted, -32768, 32767).astype("<i2")
    return converted.tobytes()


def _wav_to_pcm(audio_wav: bytes, target_rate: int = 8000) -> bytes:
    samples, sample_rate = sf.read(io.BytesIO(audio_wav), dtype="int16", always_2d=False)
    if getattr(samples, "ndim", 1) > 1:
        samples = samples.mean(axis=1).astype(np.int16)
    pcm = np.asarray(samples, dtype=np.int16).tobytes()
    return _resample_pcm(pcm, int(sample_rate), target_rate)


def _pcm_to_wav(pcm: bytes, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return buffer.getvalue()


class AudioSocketConnection:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.call_id: str | None = None
        self.playback_task: asyncio.Task | None = None
        self.closed = False

    async def send(self, kind: int, payload: bytes = b"") -> None:
        self.writer.write(_frame(kind, payload))
        await self.writer.drain()

    async def send_audio(self, pcm8k: bytes) -> None:
        pcm8k = pcm8k[: len(pcm8k) - (len(pcm8k) % 2)]
        for offset in range(0, len(pcm8k), FRAME_BYTES_8K):
            chunk = pcm8k[offset : offset + FRAME_BYTES_8K]
            if len(chunk) < FRAME_BYTES_8K:
                chunk += b"\x00" * (FRAME_BYTES_8K - len(chunk))
            await self.send(AUDIO_TYPE, chunk)
            await asyncio.sleep(0.020)

    async def flush_playback(self) -> None:
        if self.playback_task and not self.playback_task.done():
            self.playback_task.cancel()
            try:
                await self.playback_task
            except asyncio.CancelledError:
                pass
        self.playback_task = None

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        await self.flush_playback()
        self.writer.close()
        await self.writer.wait_closed()


async def _respond(connection: AudioSocketConnection, pcm8k: bytes) -> None:
    pcm16k = _resample_pcm(pcm8k, 8000, 16000)
    transcript = await asyncio.to_thread(engine.transcribe, _pcm_to_wav(pcm16k, 16000))
    if not transcript:
        response = "Ke kopa o phete seo hape."
    else:
        session = calls.get(connection.call_id or "")
        if session is None:
            return
        response = await asyncio.to_thread(session.process_text, transcript)

    if connection.call_id:
        session = calls.get(connection.call_id)
        if session:
            session.metadata["last_transcript"] = transcript
            session.metadata["last_response"] = response

    output_wav = await asyncio.to_thread(engine.synthesize, response)
    await connection.send_audio(_wav_to_pcm(output_wav, 8000))


async def handle_audiosocket(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    connection = AudioSocketConnection(reader, writer)
    vad = EnergyVAD(VADConfig(sample_rate=8000, frame_ms=20))

    try:
        while True:
            header = await reader.readexactly(3)
            kind = header[0]
            length = struct.unpack(">H", header[1:3])[0]
            payload = await reader.readexactly(length) if length else b""

            if kind == UUID_TYPE:
                if len(payload) != 16:
                    raise ValueError("Invalid AudioSocket UUID payload")
                connection.call_id = str(uuid.UUID(bytes=payload))
                session = calls.create(connection.call_id)
                session.metadata.update({"provider": "asterisk-audiosocket"})
                greeting = "Lumela. Ke mothusi wa Lesotho. Nka o thusa ka eng kajeno?"
                session.add_turn("model", greeting)
                greeting_wav = await asyncio.to_thread(engine.synthesize, greeting)
                connection.playback_task = asyncio.create_task(
                    connection.send_audio(_wav_to_pcm(greeting_wav, 8000))
                )
                continue

            if kind == AUDIO_TYPE:
                if len(payload) != FRAME_BYTES_8K:
                    continue
                for event in vad.feed(payload):
                    if event.kind == "speech_started":
                        await connection.flush_playback()
                    elif event.kind == "utterance":
                        await connection.flush_playback()
                        connection.playback_task = asyncio.create_task(
                            _respond(connection, event.audio)
                        )
                continue

            if kind in (HANGUP_TYPE, ERROR_TYPE):
                break
    except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError):
        pass
    finally:
        await connection.flush_playback()
        if connection.call_id:
            calls.remove(connection.call_id)
        await connection.close()


async def start_audiosocket_server(host: str = AUDIO_SOCKET_HOST, port: int = AUDIO_SOCKET_PORT):
    return await asyncio.start_server(handle_audiosocket, host, port)
