# Contributing

## Start from observable behavior

Behavior changes begin with an expectation handout in `expectations/` and a red
test derived from that handout. New external boundaries advance as the smallest
observable slice; retain the corresponding evidence under `observations/`.

Do not infer success from a passing unit test when the claim is acoustic or
browser-visible. Keep attempt IDs and sanitized observations for manual voice
checks, while leaving raw transcripts and context logs private.

## Preserve the core invariants

- Stay quiet until the listener starts.
- Keep application state authoritative.
- Keep visible slide separate from semantic cursor.
- Commit narration only after verified playout completion.
- Preserve the interrupted beat.
- Wait after answers unless continuation was explicitly authorized.
- Disclose grounded, extended, clarification, and out-of-scope modes.
- Never parse generated prose to decide navigation.

## Environment and checks

Use the active Python 3.12 conda environment; launch scripts deliberately do
not select or activate an environment on your behalf.

```bash
python -m pip install -e ".[test]"
cd frontend && npm ci && cd ..
./scripts/check.sh
```

External-provider observations may spend credits and require separate, explicit
execution. Never make them part of the default offline test gate.

## Code organization

Keep SDKs behind adapters and domain code import-free from provider/browser
packages. Extract a base class only when behavior and invariants are genuinely
shared; use composition or dedicated modules when option names hide different
semantics. Preserve established import contracts when moving modules.

Keep production composition small. Fake and transport-probe implementations are
valuable regression harnesses, but should be mounted only by explicit test or
development composition.

## Secrets and evidence

Never commit `.env`, credentials, `.runtime/`, raw microphone transcripts, or
raw model-context captures. Use fake values in tests and sanitized summaries in
`observations/`.

Private planning material is not public documentation and must not be copied
into changes.
