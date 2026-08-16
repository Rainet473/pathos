# Advantages

1. **Application-owned behavior:** Pathos controls navigation, interruption,
   continuation, and beat completion instead of trusting generated prose.

2. **Replaceable voice models:** LiveKit Inference, Gemini Live, and OpenAI
   Realtime adapters share one small session factory contract.

3. **Fast path before search:** The planner answers from current context when it
   can and searches the packaged deck only when more support is needed.

4. **Validated grounding:** Conversation turns and presentation evidence have
   stable IDs that are checked before an answer is spoken.

5. **Portable presentations:** Any reviewed deck using the normalized slide and
   narration contract can reuse the same runtime.

6. **Cache-aware observability:** Pathos records provider-reported cache usage,
   latency, and token counts without depending on cache hits for correctness.

7. **Clear answer boundaries:** Grounded answers, disclosed model knowledge,
   clarification, and out-of-scope responses are visible application states.

8. **Repeatable evaluation:** Deterministic tests cover races and state changes,
   while private local traces support qualitative voice evaluation.

9. **Quiet start:** No room, microphone, model connection, or heavy LiveKit
   client is created until the listener presses Start.
