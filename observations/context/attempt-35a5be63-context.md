# Context audit: attempt `35a5be63-5af1-447d-871d-e76ce8cdc3b8`

## Scope and fidelity

This is a sanitized audit of the application-visible LiveKit chat context and
local timing diagnostics. It is not a provider wire capture and does not claim
to expose undocumented provider-side instructions, tokenization, or caches.
The raw JSONL files remain ignored because they contain microphone transcripts
and prompt text.

## Observed session

- Date: 16 August 2026.
- Context captures: 35.
- Answer turns: 7.
- Largest captured chat context: 42 messages.
- Interrupted assistant messages retained in final history: 4.
- LLM first-token latency across 35 reported turns: 410 ms minimum, 722 ms
  median, and 1.928 s maximum.
- TTS first-audio latency across 35 reported turns: 523 ms minimum, 657 ms
  median, and 804 ms maximum.
- End-of-turn detection across 7 reported user turns: 1.200 s minimum, 1.201 s
  median, and 1.202 s maximum.

The measurements do not show turn-by-turn latency accumulation as context grew.
They describe provider-stage timings after turn detection; they are not a single
mouth-to-ear latency measurement.

## State and navigation result

The retained screenshots and user observation show that:

- narration started on the semantic cursor while the listener could browse;
- browsing interrupted narration without committing the active beat;
- visible slide and presentation cursor could differ without corrupting either;
- explicit answer-and-continue resumed application-owned narration; and
- the presentation completed with the deck still browsable.

One completed-state screenshot shows visible slide `clutch-and-gears` while the
semantic cursor remains `braking-abs · beat 4`. This is the intended separation,
not stale UI state.

## What the model-facing context contained

The application-visible trace contains:

1. stable speaking-surface instructions;
2. application-supplied narration or answer directives;
3. user transcript messages;
4. assistant transcript messages; and
5. interruption markers on assistant messages whose playout did not finish.

Application code, rather than model prose, still owns slide selection, answer
mode, cursor changes, and beat commitment.

## Deferred defect discovered by the audit

Two referential follow-ups were falsely classified as `out_of_scope`: one about
“this ratio” and one about “the jerk you mentioned.” The required antecedents
were present in the conversation or deck material. The failure therefore sits
in deterministic question preparation, which currently resolves the latest
utterance without a bounded conversational antecedent. It is tracked as KI-006
and does not invalidate transport, context capture, interruption, or cursor
semantics.
