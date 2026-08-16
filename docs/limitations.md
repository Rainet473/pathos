# Limitations

Pathos is a focused reference implementation, not a general presentation
platform or production voice-agent service. The limits below are intentional and
should be visible when evaluating or extending it.

## Reasoning adds follow-up latency

A normal narration turn can stream directly, but a follow-up question first
passes through endpoint detection, bounded planning, validation, answer
generation, and TTS. Questions that require deck search add another provider
round trip.

Across retained reasoning attempts, accepted non-search planning had a 1.653 s
median while accepted search planning had a 3.393 s median. These small local
samples are diagnostic evidence, not a production latency guarantee. The
application timeout is deliberately high enough to protect correctness during
harder planning, so worst-case waiting can be much longer than the median.

## Retrieval is lexical, local, and bounded

`MaterialSearch` performs deterministic phrase, keyword, alias, and token-overlap
matching over the normalized deck. It does not use embeddings, a vector database,
semantic reranking, or external web search.

Paraphrases outside the authored vocabulary can therefore miss relevant
material. Questions beyond the package can use disclosed model knowledge only
when policy allows; the agent cannot browse the web to verify current facts.

## The agent does not see slide pixels

The speaking and planning models receive authored labels, narration guidance,
deep dives, related terms, and a textual visual description. They do not inspect
the rendered slide image itself.

Charts, spatial relationships, annotations, and text that exist only in pixels
are unavailable unless the content package describes them. Image understanding
would require a new multimodal evidence boundary and validation policy.

## Provider caching is not guaranteed

Pathos records cached-token counts reported by the provider, but it cannot force
cache creation, retention, eviction, or pricing behavior. Some valid complete
runs reported zero cached tokens. Stable prompt structure may help a provider,
but no speed or cost reduction should be promised without fresh measurements for
the selected model and workload.

## Raw slide decks are not plug-and-play

The runtime contract is portable, but a raw PPTX or PDF does not automatically
provide semantic slide IDs, narration beats, evidence segments, terminology,
deep dives, or visual descriptions. The packaged motorcycle PPTX is retained as
an authoring source; generic import and review tooling are not implemented.

## Model portability is broader than transport portability

The `VoiceSessionFactory` makes the voice backend replaceable inside the current
architecture. LiveKit still owns the room, WebRTC transport, agent events, and
speech handles. Supporting another transport would require a new adapter for
those lifecycle and media semantics.

The LiveKit Inference pipeline is the verified release default. Gemini Live and
OpenAI Realtime are optional comparison adapters and do not imply equivalent
latency, endpointing, interruption, or answer quality.

## Speech recognition remains probabilistic

Short acronyms and interrupted fragments can be transcribed incorrectly or split
across provider turns. Authored terminology hints handle bounded cases such as
`ABS` versus `A B S` and can request clarification for one plausible neighbor,
but arbitrary correction would risk silently changing user intent.

The transcript preserves actual provider text; it does not invent missing words
to make an interrupted sentence look complete.

## Session context is bounded and local

Reasoning uses the active session's retained logical turns and packaged deck.
There is no cross-session semantic memory, user profile, or knowledge base. Local
JSONL diagnostics are useful for evaluation but are not a multi-tenant telemetry
system.

## Production operations are unfinished

Public deployment, authentication beyond the current live-session bootstrap,
load/concurrency characterization, durable centralized telemetry, accessibility
evaluation with assistive technology, and a software license decision remain
outside the current release evidence.
