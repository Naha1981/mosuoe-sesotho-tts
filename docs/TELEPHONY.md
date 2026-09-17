# Telephony integration plan

The voice core is deliberately separated from the carrier layer.

## Current internal contract

The application already exposes a provider-neutral `CallEvent` and `TelephonyGateway`:

- `call.started` -> create session + return greeting
- `call.text` -> send recognised caller text into the conversation session
- `call.audio` -> ASR first, then send the recognised text into the session
- end call -> remove session + return hangup action

The `/api/calls/{call_id}/audio` endpoint is intentionally turn-based. It is a bridge for the prototype while the final media-stream adapter is being selected.

## Carrier options to investigate

### Lesotho carrier/SIP route

Econet Telecom Lesotho publicly lists VoIP, Hosted PABX, Hosted Call Center and related enterprise voice services. LEO publicly offers SIP trunk configuration. These are the most relevant categories to investigate for a local-number production path because the carrier can provide the PSTN/SIP boundary while NahaLabs keeps the AI voice core independent.

### Programmable voice route

Plivo currently lists voice calling to Lesotho and browser/SIP calling, but its published Lesotho pricing page currently says inbound Lesotho calling is not supported. That makes it unsuitable as the assumed final inbound national-number route without additional carrier arrangements.

## Required production media contract

The final adapter must handle:

1. inbound call event and caller ID;
2. 8 kHz telephony audio and codec conversion where required;
3. continuous media frames rather than complete WAV uploads;
4. voice activity / turn detection;
5. barge-in so caller speech can interrupt TTS;
6. outbound audio streaming;
7. hangup and transfer-to-human events;
8. provider call ID mapped to our internal `call_id`;
9. consent / recording state;
10. delivery of a final transcript and call audit record.

## Important boundary

Do not put provider-specific credentials, webhook assumptions or carrier-specific audio handling into `app/services.py`. The ASR, conversation brain and TTS interfaces should remain unchanged when the carrier changes.
