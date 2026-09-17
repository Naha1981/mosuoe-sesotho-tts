# Lesotho Sesotho AI Calling Agent — Engineering Plan

## Mission

Build a working voice agent that a person in Lesotho can call, speak to naturally in Sesotho, and receive a spoken Sesotho response.

## Architecture

```text
PHONE / BROWSER
      |
      v
 TELEPHONY ADAPTER
      |
      v
 AUDIO GATEWAY + VAD
      |
      v
 LESOTHO ASR
      |
      v
 CONVERSATION / TOOL AGENT
      |
      v
 LESOTHO SESOTHO TTS
      |
      v
 AUDIO GATEWAY
      |
      v
 PHONE / BROWSER
```

The telephony layer is intentionally separated from speech intelligence. This lets us test the language loop without committing to a carrier/provider before the voice quality is proven.

## Phase 0 — Current browser proof

**Status: coded**

- Browser microphone capture.
- WAV audio upload.
- Southern Sotho ASR using Simba-H by default.
- Gemini conversation brain.
- Southern Sotho TTS using Simba-TTS-sot.
- Spoken response returned to browser.
- Conversation history held in the browser for the demo.

## Phase 1 — Lesotho language validation

**Acceptance gate before ministerial voice demo**

Create a consented validation pack with native Lesotho speakers covering:

- Common greetings and politeness forms.
- Public-service vocabulary.
- Names of Lesotho places and institutions.
- Numbers, dates, times and currency values.
- Code-switching between Sesotho and English.
- Fast, slow, elderly and younger speakers.
- Telephone-quality audio, background noise and interruptions.

Measure:

- ASR word error rate (WER).
- Character error rate (CER).
- Named-entity accuracy.
- Number/date accuracy.
- Human rating of TTS pronunciation and naturalness.
- False-response / hallucination rate.

## Phase 2 — Lesotho adaptation

Use the validated Lesotho recordings to fine-tune or adapt the speech stack where licensing and dataset consent permit it.

Do not use identity-sensitive speaker cloning. The objective is **language/accent coverage**, not impersonation of a real official or citizen.

## Phase 3 — Real calling

Add a telephony adapter behind the existing voice interface.

Required capabilities:

- Inbound and outbound call control.
- 8 kHz telephony audio handling.
- Barge-in / caller interruption.
- Voice activity detection.
- Silence timeout.
- Retry on packet/audio failure.
- Human escalation.
- Call recording controls where legally permitted.
- Audit log and call ID.
- AI disclosure at the start of the call.

## Phase 4 — Government-service agent

Only after the language gate passes, add a constrained public-service workflow with verified data sources and explicit escalation rules.

Initial design principle:

**Answer only from approved information or verified tools. When confidence is insufficient, escalate.**

## Phase 5 — Ministerial demonstration

Demo sequence:

1. Incoming call.
2. AI identifies itself as an AI assistant.
3. Caller speaks natural Lesotho Sesotho.
4. Agent answers in Sesotho.
5. Caller interrupts and changes topic.
6. Agent recovers the conversation.
7. Agent handles a number/date/place correctly.
8. Agent escalates an uncertain request to a human.
9. Dashboard shows transcript, response, latency and outcome.

## Definition of done for v1

A native Lesotho speaker can complete a 5–10 minute conversation over a phone-quality audio channel with understandable pronunciation, reliable recognition of common words/numbers/names, and safe escalation when the system is uncertain.
