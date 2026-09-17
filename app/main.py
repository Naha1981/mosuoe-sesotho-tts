from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from .call import calls  # noqa: E402
from .services import engine  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="NahaLabs Lesotho Sesotho AI Calling Agent", version="0.2.0")
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
    session = calls.create(call_id, caller)
    greeting = "Lumela. Ke mothusi wa Lesotho. Nka o thusa ka eng kajeno?"
    session.add_turn("model", greeting)
    return JSONResponse({"call_id": call_id, "greeting": greeting})

@app.post("/api/calls/{call_id}/text")
def call_text(call_id: str, payload: dict) -> JSONResponse:
    session = calls.get(call_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Call session not found")
    text = str(payload.get("text", "")).strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
    return JSONResponse({"call_id": call_id, "response": session.process_text(text)})

@app.delete("/api/calls/{call_id}")
def end_call(call_id: str) -> JSONResponse:
    calls.remove(call_id)
    return JSONResponse({"call_id": call_id, "ended": True})
