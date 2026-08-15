# Repository instructions

This repository contains the public implementation of the standalone **Interruptible Voice Presentation** application. Private planning material lives in the ignored `voice_presentation_handoff/` directory and must not be copied into commits or public documentation.

## Environment

- Run Python through the workspace's configured conda environment, which currently provides Python 3.12.
- Keep provider SDKs behind adapters and keep the domain core import-free from LiveKit, OpenAI, Google, or browser SDKs.
- Never commit credentials. Use environment variables and a documented `.env.example`.

## Required engineering workflow

- Invoke `$spec-first-testing` before implementing or changing behavior. Write the expectation handout and tests from requirements, not from the generated implementation.
- Invoke `$build-in-verified-slices` for new features, integrations, or pipelines. Introduce one meaningful boundary at a time and record exit evidence.
- Preserve all earlier test gates when advancing a slice.
- Distinguish deterministic tests from qualitative observation cases; retain transcripts, logs, screenshots, or recordings for the latter.
- Prefer the smallest end-to-end proof over broad scaffolding or UI polish.

## Product invariants

- Keep the page quiet until the user or Start button begins the presentation.
- Application code owns state and validates every transition.
- Keep the semantic presentation cursor separate from the visible slide.
- Advance a narration beat only after verified playout completion. Interruption preserves the active beat.
- Wait after answering by default; explicit “answer and continue” permission authorizes direct resumption.
- Use grounded, disclosed extended-knowledge, clarification, and out-of-scope answer modes.
- Use one generative voice model for the MVP, plus deterministic fake and transport-probe runtimes.
- Never parse generated prose to decide slide navigation.
