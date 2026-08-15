import type { ContinuationPreference, FakeSessionSnapshot } from "./state";

export type FakePresentationAction =
  | { type: "start" }
  | { type: "complete_playout" }
  | { type: "continue" }
  | {
      type: "interrupt_and_ask";
      question: string;
      continuationPreference: ContinuationPreference;
    };

export async function createFakeSession(): Promise<FakeSessionSnapshot> {
  return requestSnapshot("/api/fake/sessions", { method: "POST" });
}

export async function applyFakeAction(
  sessionId: string,
  action: FakePresentationAction,
): Promise<FakeSessionSnapshot> {
  return requestSnapshot(`/api/fake/sessions/${encodeURIComponent(sessionId)}/actions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(action),
  });
}

async function requestSnapshot(path: string, init: RequestInit): Promise<FakeSessionSnapshot> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let message = `Offline presentation request failed (${response.status}).`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string" && body.detail) message = body.detail;
    } catch {
      // Keep the bounded status-based message when the response is not JSON.
    }
    throw new Error(message);
  }
  return (await response.json()) as FakeSessionSnapshot;
}
