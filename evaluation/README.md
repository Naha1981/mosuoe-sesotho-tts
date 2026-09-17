# Lesotho Sesotho evaluation harness

This folder defines the acceptance workflow for proving that the voice agent works with real speakers in Lesotho.

## 1. Build a consented test set

Create `evaluation/manifest.jsonl` with one JSON object per recording:

```json
{"audio":"evaluation/audio/001.wav","reference":"...","speaker_id":"S001","district":"Maseru","environment":"quiet","phone_like":false}
```

Required fields:

- `audio`: local WAV/FLAC path.
- `reference`: human-verified transcript of exactly what the speaker said.
- `speaker_id`: anonymised speaker identifier.
- `district`: district/location label where appropriate.
- `environment`: quiet, street, vehicle, office, etc.
- `phone_like`: whether the recording approximates a telephone channel.

Do not put names, phone numbers or other unnecessary personal information into the manifest.

## 2. Run the benchmark

From the repository root:

```powershell
uv run python evaluation/evaluate_asr.py --manifest evaluation/manifest.jsonl
```

The script reports per-utterance WER and aggregate WER. It also writes a machine-readable report to `evaluation/results/asr_report.json`.

## 3. Acceptance discipline

The repository intentionally does **not** declare a final WER threshold yet. First collect representative recordings from multiple Lesotho speakers and environments; then agree the production acceptance threshold from observed requirements.

Compare results at minimum across:

- individual speakers;
- quiet versus noisy recordings;
- normal versus phone-like audio;
- short versus long utterances.

A model performing well on generic `sot` data is not, by itself, proof of Lesotho-specific speech performance.
