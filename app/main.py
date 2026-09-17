from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from .services import engine  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="NahaLabs Lesotho Sesotho AI Calling Agent",
    version="0.1.0",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> JSONResponse:
    return JSONResponse(engine.health())


@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)) -> JSONResponse:
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="No audio received")
    try:
        text = engine.transcribe(data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"ASR failed: {exc}") from exc
    return JSONResponse({"text": text})


@app.post("/api/tts")
async def tts(payload: dict) -> StreamingResponse:
    text = str(payload.get("text", "")).strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
    try:
        audio = engine.synthesize(text)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"TTS failed: {exc}") from exc
    return StreamingResponse(
        iter([audio]),
        media_type="audio/wav",
        headers={"Content-Disposition": "inline; filename=sesotho-response.wav"},
    )


@app.post("/api/turn")
async def turn(
    audio: UploadFile = File(...),
    history: str = Form("[]"),
) -> StreamingResponse:
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
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Voice turn failed: {exc}") from exc

    headers = {
        "Content-Disposition": "inline; filename=sesotho-agent-turn.wav",
        "X-Transcript": transcript.encode("utf-8").hex(),
        "X-Response-Text": response_text.encode("utf-8").hex(),
    }
    return StreamingResponse(iter([output_audio]), media_type="audio/wav", headers=headers)
