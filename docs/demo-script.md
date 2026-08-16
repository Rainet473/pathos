# Live presentation demo script

This five-minute script demonstrates the application-owned presentation cursor,
spoken interruption, grounded follow-ups, manual browsing, and deterministic
continuation behavior. Use headphones to prevent acoustic echo.

## Prepare

1. Activate the configured Python 3.12 conda environment.
2. Copy `.env.example` to `.env` and supply the LiveKit credentials.
3. Start `./scripts/run-backend.sh` and `./scripts/run-frontend.sh` in separate
   terminals.
4. Open <http://localhost:5173> and begin screen-and-audio recording.

Before selecting **Start presentation**, point out that the page is quiet and
disconnected: no room, microphone, or model session exists yet.

## Demonstrate

1. Select **Start presentation** and allow the first narration beat to begin.
2. Interrupt naturally:

   > What did you mean by the motorcycle response?

   Confirm that the unfinished narration beat remains uncommitted and the answer
   uses the retained conversation.
3. Ask a cross-slide question with explicit continuation:

   > Explain ABS, then continue your presentation.

   Confirm that the braking slide appears for the answer, then the semantic slide
   restores and the preserved narration beat resumes after answer audio finishes.
4. During a later answer, select another slide with Previous, Next, or the slide
   picker. Confirm that the answer stops, the selected slide remains visible, and
   the presentation waits. Select **Continue presentation** and confirm that the
   semantic slide restores and narration resumes—not the abandoned answer.
5. Ask a related but unsupported question:

   > Explain AWS, then continue your presentation.

   Confirm that the application discloses the presentation boundary rather than
   pretending the answer is grounded in the deck.
6. Let the presentation reach the final slide and complete. Browse to an earlier
   slide and confirm that the semantic cursor remains at the completed final beat.

## Success rubric

- Speech stops promptly when interrupted or abandoned by browsing.
- A narration beat commits only after verified narration playout.
- Visible slides may change without moving the semantic cursor.
- Default answers wait; explicit answer-and-continue resumes only after answer
  playout.
- The transcript, scope/source disclosure, domain events, and timing cards remain
  coherent with what was heard.
- No credentials or `.runtime` logs appear in the recording or repository.

Stop the session explicitly when the demonstration is finished. Retain the
recording privately if it contains voice or transcript data; publish only a
reviewed, intentionally sanitized artifact.
