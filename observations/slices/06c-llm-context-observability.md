# Verified slice: LLM inference-context observability

## Hypothesis

The application can expose the prompt/context it constructs for each inference
without coupling domain policy to LiveKit types or claiming access to hidden
provider-side prompt transformations.

## Observable path

```text
stable instructions + conversation items + GenerationDirective
  -> provider-neutral context mirror
  -> append-only local JSONL
  -> operator-readable attempt report
```

## Entry gate

- [x] Exact application prompt and directive templates were source-traced.
- [x] Existing runtime logs were checked for the latest attempt transcript.
- [x] The missing historical text was identified; it will not be fabricated.
- [x] Trace tests first failed at collection because the module did not exist.
- [x] Adapter integration first failed because no context-ledger boundary existed.

## Exit gate

- [x] Narration and answer role ordering is covered.
- [x] Local JSONL writing and provider-ID de-duplication are covered.
- [x] Live adapter integration is covered.
- [x] Historical recovery limits, fidelity, and privacy are documented.

## Automated evidence: 16 August 2026

- Focused context and LiveKit bridge gate: 8 passed.
- Full Python regression: 206 passed, one opt-in paid test skipped.
- The previous attempt report records the evidence gap instead of reconstructing
  missing user/assistant text from screenshots.
