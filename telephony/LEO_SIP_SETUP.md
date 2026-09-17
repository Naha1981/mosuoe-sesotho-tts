# LEO Lesotho SIP trunk -> Mosuoe AI

## Why LEO is the first carrier target

LEO publicly lists **SIP Trunks Configuration**, VoIP systems, hosted PABX and call-centre services in Lesotho. This makes LEO a practical first carrier to approach for a SIP trunk and Lesotho DID. The carrier still needs to confirm the exact SIP interconnection, DID routing, authentication method, codecs and commercial terms for NahaLabs.

## What NahaLabs must request from LEO

Ask for:

1. A Lesotho inbound DID/telephone number for the prototype.
2. SIP trunk service that can deliver inbound calls to an Asterisk/PJSIP endpoint.
3. SIP authentication method:
   - registration username/password, or
   - source-IP authentication.
4. SIP proxy/registrar hostname or IP and port.
5. Provider signalling IP ranges if IP authentication is used.
6. RTP/media requirements and provider IP ranges.
7. Supported codecs. The prototype is prepared for G.711/ulaw or alaw into Asterisk.
8. Any required caller-ID/DID formatting.
9. Whether the DID can be routed directly to the supplied SIP trunk.
10. Whether a static public IP is required/expected for the customer endpoint.

LEO currently publishes `+266 2221 5000` and `support@leo.co.ls` as contact details. Use the official LEO channel to request the enterprise SIP-trunk quote and technical interconnection details; do not put credentials in this repository.

## NahaLabs media path

```text
Lesotho caller
    |
    v
LEO Lesotho DID / SIP trunk
    |
    v
Asterisk + PJSIP
    |
    | AudioSocket TCP :9019
    v
Mosuoe FastAPI
    |
    +--> 8 kHz phone PCM
    |       -> 16 kHz
    |       -> Lesotho speech ASR
    |       -> Gemini conversation brain
    |       -> Simba-TTS-sot
    |       -> 8 kHz PCM
    |
    v
Asterisk
    |
    v
LEO
    |
    v
Caller hears Sesotho
```

Asterisk's `AudioSocket()` application provides a bidirectional TCP audio path. Its default dialplan application format is 16-bit, 8 kHz, mono PCM, which is why the Mosuoe bridge resamples phone audio to 16 kHz for the current ASR and back to 8 kHz for telephone playback.

## Files

- `telephony/asterisk/pjsip.conf.example` — provider-neutral PJSIP trunk template.
- `telephony/asterisk/extensions.conf.example` — inbound DID routing into AudioSocket.
- `app/audiosocket.py` — AudioSocket protocol server and realtime AI bridge.

## Important deployment requirement

For a genuine external telephone call, Asterisk must be reachable by the carrier for SIP signalling and RTP. A local Windows laptop behind NAT is not automatically suitable for production telephony. For the first live test, use either:

- an appropriately configured public/static-IP network with firewall/NAT rules, or
- a Linux server/VM with a public IP.

Do not expose the Mosuoe AudioSocket port `9019` to the public internet. Keep it reachable only from the local Asterisk process/network.

## Acceptance test

The first live acceptance test is intentionally simple:

1. Call the Lesotho DID from a normal phone.
2. Asterisk answers the call.
3. Mosuoe says: `Lumela. Ke mothusi wa Lesotho. Nka o thusa ka eng kajeno?`
4. Caller speaks a short Lesotho-Sesotho sentence.
5. VAD detects the utterance.
6. ASR produces a transcript.
7. Gemini generates a short Sesotho response.
8. TTS produces the response.
9. Asterisk sends the response back to the caller.
10. Caller interrupts while Mosuoe is speaking; playback is flushed and the new utterance is processed.

The acceptance test is not considered passed until an actual Lesotho phone call completes this loop.
