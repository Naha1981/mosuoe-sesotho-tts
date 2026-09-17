from __future__ import annotations

import asyncio
import base64
import binascii
import io
import json
import wave

from fastapi import WebSocket, WebSocketDisconnect

from .call import calls
from .services import engine
from .vad import EnergyVAD


def pcm_to_wav(pcm: bytes, sample_rate: int = 16000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return buffer.getvalue()


async def _respond(call_id: str, pcm: bytes, sample_rate: int) -> tuple[str, str, bytes]:
    audio_wav = pcm_to_wav(pcm, sample_rate)
    transcript = await asyncio.to_thread(engine.transcribe, audio_wav)
    if not transcript:
        return "", "Ke kopa o phete seo hape.", b""

    session = calls.get(call_id)
    if session is None:
        raise KeyError(call_id)

    response = await asyncio.to_thread(session.process_text, transcript)
    output_audio = await asyncio.to_thread(engine.synthesize, response)
    return transcript, response, output_audio


async def _send_audio(websocket: WebSocket, output_audio: bytes, text: str, message_type: str = "audio") -> None:
    await websocket.send_json({"type": "response", "text": text})
    await websocket.send_json(
        {
            "type": message_type,
            "format": "wav",
            "audio": base64.b64encode(output_audio).decode("ascii"),
        }
    )


async def handle_realtime_call(websocket: WebSocket, call_id: str) -> None:
    """Realtime browser/voice-provider audio stream.

    Client messages:
      {"type":"start","sample_rate":16000}
      {"type":"audio","audio":"<base64 PCM16 mono>"}
      {"type":"playback_started"}
      {"type":"playback_finished"}
      {"type":"stop"}

    Server messages include ready, started, speech_started, processing, transcript,
    response, audio, interrupt, stopped and error.
    """
    await websocket.accept()
    session = calls.get(call_id)
    if session is None:
        await websocket.send_json({"type": "error", "detail": "Call session not found"})
        await websocket.close(code=4404)
        return

    vad = EnergyVAD()
    sample_rate = 16000
    speaking_task: asyncio.Task | None = None
    agent_speaking = False

    async def cancel_speaking() -> None:
        nonlocal speaking_task
        if speaking_task is not None and not speaking_task.done():
            speaking_task.cancel()
            try:
                await speaking_task
            except asyncio.CancelledError:
                pass
        speaking_task = None

    async def interrupt_agent() -> None:
        nonlocal agent_speaking
        await cancel_speaking()
        if agent_speaking:
            agent_speaking = False
            await websocket.send_json({"type": "interrupt"})

    async def send_greeting() -> None:
        nonlocal agent_speaking
        greeting = "Lumela. Ke mothusi wa Lesotho. Nka o thusa ka eng kajeno?"
        output_audio = await asyncio.to_thread(engine.synthesize, greeting)
        await _send_audio(websocket, output_audio, greeting, message_type="audio")
        agent_speaking = True

    async def process_utterance(pcm: bytes) -> None:
        nonlocal speaking_task, agent_speaking
        try:
            await websocket.send_json({"type": "processing"})
            transcript, response, output_audio = await _respond(call_id, pcm, sample_rate)
            if not transcript:
                await websocket.send_json({"type": "response", "text": response})
                return
            await websocket.send_json({"type": "transcript", "text": transcript})
            await _send_audio(websocket, output_audio, response)
            agent_speaking = True
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await websocket.send_json({"type": "error", "detail": f"Realtime turn failed: {exc}"})
        finally:
            speaking_task = None

    try:
        await websocket.send_json({"type": "ready", "call_id": call_id, "sample_rate": sample_rate})

        while True:
            message = await websocket.receive_text()
            payload = json.loads(message)
            kind = payload.get("type")

            if kind == "start":
                sample_rate = int(payload.get("sample_rate", 16000))
                if sample_rate != 16000:
                    await websocket.send_json({"type": "error", "detail": "Realtime stream requires 16000 Hz PCM"})
                    continue
                await websocket.send_json({"type": "started", "sample_rate": sample_rate})
                await send_greeting()
                continue

            if kind == "playback_started":
                agent_speaking = True
                continue

            if kind == "playback_finished":
                agent_speaking = False
                await websocket.send_json({"type": "listening"})
                continue

            if kind == "audio":
                raw = base64.b64decode(payload.get("audio", ""), validate=True)
                for event in vad.feed(raw):
                    if event.kind == "speech_started":
                        if speaking_task is not None and not speaking_task.done():
                            await cancel_speaking()
                            await websocket.send_json({"type": "interrupt"})
                        elif agent_speaking:
                            await interrupt_agent()
                        await websocket.send_json({"type": "speech_started"})
                    elif event.kind == "utterance":
                        await cancel_speaking()
                        speaking_task = asyncio.create_task(process_utterance(event.audio))
                continue

            if kind == "stop":
                await cancel_speaking()
                agent_speaking = False
                await websocket.send_json({"type": "stopped"})
                break

            await websocket.send_json({"type": "error", "detail": f"Unknown message type: {kind}"})
    except WebSocketDisconnect:
        await cancel_speaking()
    except (ValueError, json.JSONDecodeError, binascii.Error) as exc:
        await websocket.send_json({"type": "error", "detail": str(exc)})
        await websocket.close(code=4400)
