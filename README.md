# NahaLabs Lesotho Sesotho AI Calling Agent

Prototype for a voice agent that can **hear spoken Sesotho and answer in Sesotho**, with the language target explicitly framed as **Lesotho Sesotho**, not a generic South African voice.

## Prototype loop

`Browser microphone -> ASR -> Sesotho conversation brain -> Sesotho TTS -> browser speaker`

## Live-call loop

`Caller -> Telephony/media gateway -> PCM audio stream -> VAD -> ASR -> conversation brain -> TTS -> caller`

The live prototype exposes a provider-neutral WebSocket at `/api/calls/{call_id}/stream`. See `docs/REALTIME_STREAM.md` for the message contract.

The first implementation uses:

- **ASR:** `UBC-NLP/Simba-H` by default. It is a 94M-parameter African ASR model whose language coverage includes Southern Sotho (`sot`).
- **TTS:** `UBC-NLP/Simba-TTS-sot`, a dedicated Southern Sotho TTS model.
- **Brain:** Google Gemini through the `google-genai` SDK. The brain is instructed to use Lesotho Sesotho conventions and to avoid pretending that South African Sesotho is the target accent.
- **Audio:** WAV microphone capture in the browser, with 16 kHz mono PCM for the realtime stream.
- **VAD:** dependency-free energy-based detector for the prototype, replaceable after field evaluation.

## Why this is deliberately not called "Lesotho-trained" yet

Current open speech resources clearly distinguish Southern Sotho as a language, but the same language code is used across Lesotho and South Africa. We therefore treat **Lesotho voice adaptation as a project layer** that must be validated with real Lesotho speakers and recordings rather than inferred from the language code alone.

## Run locally

### 1. Requirements

- Windows 10/11
- Python 3.11+ recommended
- Git
- A working microphone and speakers/headphones
- A Gemini API key for the conversational brain

### 2. Install dependencies

```powershell
uv venv
.\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
```

### 3. Environment

Copy `.env.example` to `.env` and add your Gemini API key.

### 4. Start

```powershell
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open:

`http://127.0.0.1:8000`

The first ASR/TTS request downloads model weights from Hugging Face.

## Prototype controls

- **Start speaking** records from the browser microphone.
- **Stop** sends the WAV to the backend.
- The backend transcribes the speech, generates a Sesotho response, synthesizes audio, and returns the complete turn.
- The UI shows the recognised text and the agent response for verification.

## Lesotho speech acceptance harness

The `evaluation/` folder provides the first measurement layer for the core requirement: understanding real Sesotho spoken by people in Lesotho.

Create a consented recording set and copy `evaluation/manifest.example.jsonl` to a working manifest. Each record stores an audio path, human-verified reference transcript, anonymised speaker ID, district/location label, recording environment, and whether the audio is phone-like.

Run:

```powershell
uv run python evaluation/evaluate_asr.py --manifest evaluation/manifest.jsonl
```

The benchmark reports per-recording WER and an aggregate WER in `evaluation/results/asr_report.json`. It deliberately does not hard-code a final production threshold until representative Lesotho recordings have been collected and reviewed.

## Realtime voice stream

The WebSocket stream accepts 16 kHz mono signed 16-bit PCM frames and automatically detects utterance boundaries. During agent playback, the client can report `playback_started`; caller speech then triggers an `interrupt` event so the client/carrier can stop current TTS playback. See `docs/REALTIME_STREAM.md` for the protocol.

## Engineering stages

1. Collect a small, consented **Lesotho speech validation set** and benchmark ASR.
2. Benchmark TTS for naturalness, pronunciation and Lesotho linguistic conventions.
3. **Implemented:** realtime PCM frames, automatic turn detection and barge-in signalling.
4. Connect a provider-neutral telephony/media adapter, then connect a suitable SIP/telephony provider.
5. Add call logging, consent/disclosure, escalation-to-human and audit trails.
6. Build a ministerial demo scenario around a non-sensitive public-service workflow.

## Important prototype boundary

This is a technology demonstration, not a claim that the current models are already a production-grade **Lesotho-accent** system. The acceptance gate is real speaker evaluation in Lesotho.
