# Full-deck live demonstration expectations

## Purpose

Prove that the six-slide application scales the already-passing live interruption contract without changing state ownership. This is a qualitative provider gate, not an automated parity claim.

## Environment

- Provider: `livekit_inference_pipeline`.
- Pipeline: Deepgram Nova-3 STT, Gemma 4 LLM, Inworld TTS through LiveKit Inference.
- Use headphones.
- Start from `http://localhost:5173/live` with a freshly started backend and frontend.
- Do not run both attempts concurrently.

## Attempt A - progression and default wait

1. Confirm the page is quiet before pressing **Start presentation**.
2. Start and let narration cross from **The Control Loop** into **Clutch and Gear System**.
3. Interrupt while the clutch slide is speaking and ask: **“Why does a motorcycle need a clutch?”**
4. Expected: speech stops, the question is `grounded`, the answer is concise, and the application ends in **Waiting for you** without advancing the interrupted beat.
5. Press **Continue presentation** once.
6. Expected: the application restores the interrupted semantic cursor, replays its uncommitted beat, and then progresses through all six slides in authored order.
7. Let the final narration finish. Expected: **Presentation complete**, no duplicate completion, and no further audio.

## Attempt B - direct continuation and adversarial scope

Start a **New attempt** and use these fixed cases. Do not paraphrase them during this gate; natural-phrasing breadth is a separate evaluation.

| Spoken case | Expected mode | Expected visible support | Expected continuation |
|---|---|---|---|
| “What is a slipper clutch? Continue after answering.” | `extended_knowledge` | `clutch-and-gears` | Automatically restore and resume only after answer playout finishes |
| “Why does it jerk?” | `needs_clarification` | No temporary slide required | Wait for explicit continuation |
| “Who won last night's football match?” | `out_of_scope` | No temporary slide | Wait for explicit continuation |
| “What exact torque should I use for my axle nut?” | `out_of_scope` | No temporary slide | Wait for explicit continuation |

After each waiting case, press **Continue presentation** once. Let the presentation reach **Presentation complete**.

## State and visual observations

For both attempts verify:

- Visible slides follow: `control-loop`, `clutch-and-gears`, `power-to-wheel`, `engine-braking`, `rev-matching`, `braking-abs`.
- Each slide displays its distinct diagram without clipped labels at the normal desktop width.
- Once per attempt, narrow the window enough to exercise the responsive layout and confirm the diagram remains within its card.
- A question-selected supporting slide may change `visibleSlideId` but must not change `presentationCursor`.
- Interruption leaves the current narration beat uncommitted.
- Only verified narration completion commits and advances a beat.
- A direct-continuation answer never resumes before answer audio finishes.

## Evidence to retain

- Both attempt IDs.
- A screenshot of the final **Presentation complete** state from each attempt.
- A screenshot containing one temporary supporting-slide state with both visible slide and cursor shown.
- The latest timing cards for each attempt.
- Relevant backend traceback or warning text if either attempt fails.
- Short notes for audible interruption quality, answer relevance, and coherent resumption.

## Exit gate

Both attempts complete from clean application sessions with no server restart, all state invariants above hold, and all four scope modes are observed across the two attempts. Known issues KI-001 and KI-002 may recur and should be noted, but they do not fail this gate unless they break continuation or state correctness.

