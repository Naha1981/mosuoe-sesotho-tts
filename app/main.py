from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from .audiosocket import start_audiosocket_server  # noqa: E402
from .call import calls  # noqa: E402
from .realtime import handle_realtime_call  # noqa: E402
from .services import engine  # noqa: E402
from .telephony import CallEvent, gateway  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    audio_server = await start_audiosocket_server()
    app.state.audio_socket_server = audio_server
    yield
    audio_server.close()
    await audio_server.wait_closed()


app = FastAPI(
    title="NahaLabs Lesotho Sesotho AI Calling Agent",
    version="0.5.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> JSONResponse:
    result = engine.health()
    result["telephony"] = {
        "adapter": "asterisk-audiosocket",
        "audio_socket": "0.0.0.0:9019",
        "status": "listening",
    }
    return JSONResponse(result)


@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)) -> JSONResponse:
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="No audio received")
    try:
        text = engine.transcribe(data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ASR failed: {exc}") from exc
    return JSONResponse({"text": text})


@app.post("/api/tts")
async def tts(payload: dict) -> StreamingResponse:
    text = str(payload.get("text", "")).strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
    try:
        audio = engine.synthesize(text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"TTS failed: {exc}") from exc
    return StreamingResponse(iter([audio]), media_type="audio/wav")


@app.post("/api/turn")
async def turn(audio: UploadFile = File(...), history: str = Form("[]")) -> StreamingResponse:
    audio_data = await audio.read()
    if not audio_data:
        raise HTTPException(status_code=400, detail="No audio received")
    try:
        parsed_history = json.loads(history)
        if not isinstance(parsed_history, list):
            parsed_history = []
    except json.JSONDecodeError:
        parsed_history = []
    try:
        transcript = engine.transcribe(audio_data)
        if not transcript:
            raise HTTPException(status_code=422, detail="No speech recognised")
        response_text = engine.respond(transcript, parsed_history)
        output_audio = engine.synthesize(response_text)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Voice turn failed: {exc}") from exc
    return StreamingResponse(iter([output_audio]), media_type="audio/wav", headers={
        "X-Transcript": transcript.encode("utf-8").hex(),
        "X-Response-Text": response_text.encode("utf-8").hex(),
    })


@app.post("/api/calls/{call_id}/start")
def start_call(call_id: str, caller: str | None = None) -> JSONResponse:
    result = gateway.start(
        CallEvent(
            event_type="call.started",
            call_id=call_id,
            caller=caller,
            metadata={"provider": "api"},
        )
    )
    return JSONResponse(result)


@app.post("/api/calls/{call_id}/text")
def call_text(call_id: str, payload: dict) -> JSONResponse:
    text = str(payload.get("text", "")).strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
    try:
        result = gateway.receive_text(
            CallEvent(event_type="call.text", call_id=call_id, text=text)
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Call session not found") from exc
    return JSONResponse(result)


@app.post("/api/calls/{call_id}/audio")
async def call_audio(call_id: str, audio: UploadFile = File(...)) -> StreamingResponse:
    audio_data = await audio.read()
    if not audio_data:
        raise HTTPException(status_code=400, detail="No audio received")
    if calls.get(call_id) is None:
        raise HTTPException(status_code=404, detail="Call session not found")

    try:
        transcript = engine.transcribe(audio_data)
        if not transcript:
            raise HTTPException(status_code=422, detail="No speech recognised")
        result = gateway.receive_text(
            CallEvent(event_type="call.audio", call_id=call_id, text=transcript)
        )
        output_audio = engine.synthesize(result["text"])
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Call audio failed: {exc}") from exc

    return StreamingResponse(
        iter([output_audio]),
        media_type="audio/wav",
        headers={
            "X-Transcript": transcript.encode("utf-8").hex(),
            "X-Response-Text": result["text"].encode("utf-8").hex(),
        },
    )


@app.websocket("/api/calls/{call_id}/stream")
async def call_stream(websocket: WebSocket, call_id: str) -> None:
    await handle_realtime_call(websocket, call_id)


@app.delete("/api/calls/{call_id}")
def end_call(call_id: str) -> JSONResponse:
    return JSONResponse(gateway.end(call_id))
