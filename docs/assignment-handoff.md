# Assignment handoff

## Delivered product

The repository contains a standalone, application-controlled voice presentation
for the packaged six-slide motorcycle deck. It starts quietly, narrates through a
LiveKit STT/LLM/TTS pipeline, accepts spoken interruptions, plans bounded
follow-up answers against authored material and retained conversation, and
commits narration only after verified audio playout.

The browser may show a slide independently of the semantic narration cursor.
Browsing during active answer playout now abandons the answer, preserves that
cursor, clears automatic-continuation permission, and pauses. Continue restores
the semantic slide and replays its uncommitted narration beat.

## Run and demonstrate

1. Complete the setup in the repository `README.md` using one active Python 3.12
   conda environment.
2. Start `./scripts/run-backend.sh` and `./scripts/run-frontend.sh` in separate
   terminals.
3. Open <http://localhost:5173>.
4. Follow `docs/demo-script.md` for the concise five-minute public walkthrough.

The complete deterministic release gate is:

```bash
./scripts/check.sh
```

Paid provider observations and microphone behavior are deliberately separate
from that offline gate.

## Ownership boundaries

- `domain/` owns state and validates transitions without provider imports.
- `application/` owns use cases, evidence selection, and generation directives.
- `adapters/livekit/` translates provider events and correlates speech handles.
- `transport/` owns public schemas, diagnostics, lifecycle, and usage records.
- `frontend/` renders application state; generated prose never selects slides.

The default release provider is the LiveKit Inference pipeline. Gemini and
OpenAI realtime modules are retained only as explicit optional comparison
adapters. Fake speech handles and lightweight collaborators exist under tests,
not as product endpoints.

## Verification and acceptance state

- KI-001, KI-003, and KI-006 are closed for this assignment by user acceptance
  after live testing on 17 August 2026.
- KI-004 is implemented with red-first domain, application, adapter, and frontend
  tests. Its remaining gate is the live acoustic check in demo step 4.
- The quiet-start screen was visually checked at desktop and 390 px width without
  granting microphone access.
- Detailed limitations and mitigation status live in
  `observations/known-issues.md`; slice evidence lives in `observations/slices/`.

## Cleanup decisions

The release surface has no fake or probe HTTP endpoints. The obsolete
`conversation.py` compatibility re-exports for launcher and private agent
construction were removed; callers now import from the modules that own those
responsibilities.

The browser now loads the LiveKit transport only after Start. The production
build's initial JavaScript bundle fell from 710.72 kB to 214.49 kB; the on-demand
transport chunk is 496.93 kB and the previous oversized-chunk warning is gone.

The following were intentionally retained:

- deterministic tests and historical slice records, because they are regression
  and decision evidence rather than runtime scaffolding;
- provider-neutral protocols and dependency-injection seams used at external
  boundaries;
- optional Gemini/OpenAI adapters, because they are documented comparison paths,
  not hidden production dependencies.

## Explicitly deferred

- Generic PPTX/content ingestion and `additional-context.json` loading (KI-005).
- Broader transcript reconstruction across provider interruption boundaries
  (KI-002).
- General recovery from arbitrary acronym transcription errors (KI-007).
- Public deployment, long-duration load testing, and license selection.

Do not commit `.env`, `.runtime/`, raw transcripts, model-context captures, or
private planning material. Sanitize any recording before sharing it publicly.
