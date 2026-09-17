from __future__ import annotations

import io
import json
import os
import threading
from dataclasses import dataclass
from typing import Any

import numpy as np
import soundfile as sf
import torch
from scipy.signal import resample_poly
from scipy.io import wavfile
from transformers import AutoProcessor, AutoModelForCTC, VitsModel, AutoTokenizer, pipeline

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover
    genai = None
    types = None

ASR_DEFAULT = "UBC-NLP/Simba-H"
TTS_DEFAULT = "UBC-NLP/Simba-TTS-sot"
GEMINI_DEFAULT = "gemini-flash-latest"


@dataclass
class Settings:
    asr_model: str = os.getenv("ASR_MODEL", ASR_DEFAULT)
    tts_model: str = os.getenv("TTS_MODEL", TTS_DEFAULT)
    gemini_model: str = os.getenv("GEMINI_MODEL", GEMINI_DEFAULT)
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")


class VoiceEngine:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self._asr = None
        self._tts_model = None
        self._tts_tokenizer = None
        self._tts_lock = threading.Lock()
        self._brain = None

        # Predictable CPU behaviour on the user's laptop.
        torch.set_num_threads(max(1, min(8, os.cpu_count() or 2)))

    @property
    def asr(self):
        if self._asr is None:
            self._asr = pipeline(
                "automatic-speech-recognition",
                model=self.settings.asr_model,
                device=-1,
            )
        return self._asr

    def transcribe(self, audio_bytes: bytes) -> str:
        audio, sample_rate = sf.read(io.BytesIO(audio_bytes), dtype="float32", always_2d=False)
        if audio.ndim == 2:
            audio = np.mean(audio, axis=1)
        audio = np.asarray(audio, dtype=np.float32)

        if sample_rate != 16_000:
            audio = resample_poly(audio, 16_000, sample_rate).astype(np.float32)
            sample_rate = 16_000

        result = self.asr({"array": audio, "sampling_rate": sample_rate})
        return str(result["text"]).strip()

    def _load_tts(self) -> None:
        if self._tts_model is not None:
            return
        with self._tts_lock:
            if self._tts_model is not None:
                return
            self._tts_model = VitsModel.from_pretrained(self.settings.tts_model)
            self._tts_tokenizer = AutoTokenizer.from_pretrained(self.settings.tts_model)
            self._tts_model.eval()

    def synthesize(self, text: str) -> bytes:
        self._load_tts()
        inputs = self._tts_tokenizer(text, return_tensors="pt")
        with torch.no_grad():
            waveform = self._tts_model(**inputs).waveform

        audio = waveform.squeeze().cpu().numpy().astype(np.float32)
        buffer = io.BytesIO()
        wavfile.write(buffer, int(self._tts_model.config.sampling_rate), audio)
        return buffer.getvalue()

    def _fallback_reply(self, user_text: str) -> str:
        normalized = user_text.lower().strip()
        if any(token in normalized for token in ("lumela", "dumela", "hello", "hello")):
            return "Lumela. Ke mothusi wa NahaLabs. Nka o thusa ka eng kajeno?"
        if "leboha" in normalized or "thanks" in normalized:
            return "Ke a leboha. Nka o thusa ka eng hape?"
        return (
            "Ke a o utlwa. Ke mothusi wa Lesotho ya buang Sesotho. "
            "Ka kopo mpolelle hanyane hore nka o thusa jwang."
        )

    def respond(self, user_text: str, history: list[dict[str, str]] | None = None) -> str:
        if not self.settings.gemini_api_key or genai is None:
            return self._fallback_reply(user_text)

        if self._brain is None:
            self._brain = genai.Client(api_key=self.settings.gemini_api_key)

        history = history or []
        recent = history[-8:]
        transcript = "\n".join(
            f"{item.get('role', 'user')}: {item.get('text', '')}" for item in recent
        )
        prompt = (
            "Conversation history:\n"
            f"{transcript}\n\n"
            f"Current caller: {user_text}\n\n"
            "Respond to the caller now."
        )
        system_instruction = (
            "You are a professional voice assistant for a Lesotho public-service prototype. "
            "Speak natural, respectful Sesotho intended for speakers in Lesotho. "
            "Do not claim that South African Sesotho pronunciation is the target. "
            "Prefer concise spoken sentences, normally 1-3 short sentences. "
            "Do not invent government facts, names, policies, dates or services. "
            "When uncertain, say that you need to verify the information or transfer to a human agent. "
            "You are an AI and should disclose that naturally when the caller asks who is speaking."
        )

        response = self._brain.models.generate_content(
            model=self.settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.35,
                max_output_tokens=160,
            ),
        )
        text = (response.text or "").strip()
        return text or self._fallback_reply(user_text)

    def health(self) -> dict[str, Any]:
        return {
            "asr_model": self.settings.asr_model,
            "tts_model": self.settings.tts_model,
            "gemini_configured": bool(self.settings.gemini_api_key),
            "asr_loaded": self._asr is not None,
            "tts_loaded": self._tts_model is not None,
        }


engine = VoiceEngine()
