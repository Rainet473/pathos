# Expectation handout: local LLM inference-context trace

## User-visible outcome

An operator can inspect one local JSONL record per model inference and see the
stable application prompt, ordered persisted conversation history, current
application directive, and current user message. The trace is explicitly an
application/LiveKit chat-context view, not a claim about a provider's private
wire serialization or hidden service-side instructions.

## Inputs, outputs and boundaries

- Inputs: stable session instructions, provider conversation-item events, and
  application `GenerationDirective` values.
- Output: `.runtime/llm-context.jsonl` by default.
- Boundary: append-only local observability; no browser publication and no
  external logging service.
- Non-goal: retroactively reconstructing conversations that were not persisted.

## Invariants

- Every record names the attempt, application turn, and narration/answer purpose.
- The stable instructions are recorded verbatim.
- Narration records add the per-beat directive as a system instruction.
- Answer records add the answer evidence directive as a developer instruction
  followed by the current user message.
- Persisted user/assistant history retains interruption-truncated assistant text
  when LiveKit emits it.
- Provider message IDs are de-duplicated.
- The trace stays local and its privacy implications are documented.

## Exit criteria

- [ ] Tests fail before the trace implementation exists.
- [ ] Ordered message-role tests pass.
- [ ] JSONL append and provider-ID de-duplication tests pass.
- [ ] Configured live sessions receive the trace ledger.
- [ ] A readable report explains the latest attempt's recovery limits.
