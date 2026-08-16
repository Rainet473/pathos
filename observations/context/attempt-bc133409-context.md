# Inference context report: attempt `bc133409-1b50-4b9b-8623-aec1bac8d794`

Date: 16 August 2026
Provider path: LiveKit three-model inference pipeline
Recorded outcome: completed
Recorded duration: 375.351 seconds

## Recovery verdict

The exact conversation text for this completed attempt is **not recoverable from
the repository's retained runtime evidence**. At the time of this attempt the
application published transcript rows to the browser, but did not persist them.
The usage ledger contains duration/outcome and the diagnostic ledger contains 344
state/timing events; neither contains user or assistant text. This report therefore
does not invent a transcript from partial screenshots.

The diagnostic record does establish that the attempt ran to completion and
contains 30 LLM/TTS timing samples plus five end-of-utterance samples. LLM first
token values range from 348 ms to 1,806 ms, TTS first audio values range from 548
ms to 805 ms, and recorded end-of-utterance values are approximately 1.2 seconds.

## Stable prompt received for the session

The application supplies this exact stable instruction string:

```text
You are the speaking surface for an application-controlled presentation. Follow the latest application-supplied narration or answer evidence exactly, stay concise, and never navigate or resume the presentation yourself.
```

## What one inference receives

The three-model pipeline uses an accumulating LiveKit chat context. At the
application-visible boundary, an inference is assembled from:

1. the stable prompt above;
2. persisted prior user and assistant conversation items (including truncated
   assistant text when an interrupted item is emitted);
3. one application-owned directive for the current turn; and
4. for an answer, the current user message.

Narration adds the per-beat directive as a `system` instruction after the prior
history:

```text
Deliver exactly one concise presentation beat in one or two sentences. Do not greet, ask a question, mention these instructions, or navigate. Slide headline: {headline} Visible labels: {labels}. Beat summary: {summary} Narration guidance: {guidance} Required concepts: {concepts}.
```

Answer inference uses this ordered tail:

```text
developer: Respond to the listener in no more than three short sentences. Do not navigate, resume the presentation, or mention hidden instructions. Listener question: {question} {scope-specific evidence instruction}
user: {current transcribed question}
```

The scope-specific portion is one of:

- grounded: answer only from the selected manifest evidence;
- extended knowledge: disclose that the exact answer is not on the slide, then
  give a bounded general-knowledge answer;
- clarification: ask only the selected clarification question; or
- out of scope: briefly decline unsafe or exact motorcycle-specific instruction.

Changes made to the temporary answer context are used for that inference but are
not persisted as ordinary conversation history. The user message and generated
assistant result are persisted by LiveKit after scheduling. Application code—not
generated prose—selects slides, resumes narration, and commits beats.

## New exact local trace for subsequent attempts

Subsequent configured sessions append one record per inference to:

```text
.runtime/llm-context.jsonl
```

Each line records:

- `attemptId`, `sequence`, `turnId`, `purpose`, and capture time;
- the exact stable application prompt;
- ordered application-visible LiveKit history;
- the exact current narration or answer directive;
- the current user message for answer turns; and
- interruption status when LiveKit exposes it on an assistant item.

The trace deliberately labels its fidelity as
`application_livekit_chat_context`. It is the exact context the application can
observe and instruct LiveKit to use; it is not a byte-for-byte provider wire dump
and cannot expose hidden service-side transformations. The file contains private
conversation text, is ignored by Git, and should not be shared or committed.

To inspect only one new attempt:

```bash
rg '"attemptId":"<attempt-id>"' .runtime/llm-context.jsonl
```

## Source seams

- Stable prompt: `backend/src/voice_presentation/server/app.py`
- Per-turn directives: `backend/src/voice_presentation/application/live_presentation.py`
- LiveKit turn injection and history mirroring:
  `backend/src/voice_presentation/adapters/livekit/conversation.py`
- Local trace schema/ledger:
  `backend/src/voice_presentation/transport/context_trace.py`
