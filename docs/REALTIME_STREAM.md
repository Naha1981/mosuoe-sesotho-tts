# Realtime voice stream

The prototype exposes a provider-neutral WebSocket at:

`/api/calls/{call_id}/stream`

The stream expects **16 kHz, mono, signed 16-bit PCM** in small frames. The current VAD uses 20 ms frames.

## Client -> server

Start the stream:

```json
{"type":"start","sample_rate":16000}
```

Send PCM frames as base64:

```json
{"type":"audio","audio":"<base64 PCM16 mono>"}
```

When the server returns TTS audio and the client begins playback:

```json
{"type":"playback_started"}
```

When playback finishes:

```json
{"type":"playback_finished"}
```

End the stream:

```json
{"type":"stop"}
```

## Server -> client

The server can emit:

- `ready`
- `started`
- `speech_started`
- `processing`
- `transcript`
- `response`
- `audio`
- `interrupt`
- `error`
- `stopped`

The `audio` message contains a base64-encoded WAV response. A carrier adapter should translate its incoming media packets into the PCM frames above and translate the returned WAV into the carrier's outbound audio format.

## Barge-in behaviour

When the caller starts speaking while the client reports that the agent is playing audio, the server emits `interrupt`. The client/carrier should immediately stop playing the current TTS response and continue sending caller audio.

## Current boundary

The VAD is an intentionally small energy-based implementation for prototype work. It is not yet the production speech detector. Once real Lesotho phone recordings are collected, VAD thresholds and a stronger VAD can be evaluated against those recordings.
