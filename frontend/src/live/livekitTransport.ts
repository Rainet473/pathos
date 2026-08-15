import {
  Room,
  RoomEvent,
  Track,
  createLocalAudioTrack,
  type LocalAudioTrack,
  type RemoteTrack,
} from "livekit-client";

import type { LiveSessionResponse, VoiceBackendIdentity } from "./protocol";
import {
  CONVERSATION_DIAGNOSTICS_TOPIC,
  parseConversationDiagnosticEvent,
  type ConversationDiagnosticEvent,
} from "./diagnostics";
import type { NormalizedAgentState, TranscriptEntry } from "./state";
import {
  PRESENTATION_COMMAND_TOPIC,
  PRESENTATION_STATE_TOPIC,
  parsePresentationStateUpdate,
  type PresentationStateUpdate,
} from "./presentation";

export interface LiveKitConversationCallbacks {
  onConnected: (backend: VoiceBackendIdentity) => void;
  onAgentState: (state: NormalizedAgentState) => void;
  onLocalSpeechWhileAgentSpeaking: () => void;
  onTranscript: (entry: TranscriptEntry) => void;
  onDiagnostic: (event: ConversationDiagnosticEvent) => void;
  onPresentation: (event: PresentationStateUpdate) => void;
  onDisconnected: () => void;
  onAudioPlaybackBlocked: () => void;
}

interface AudioElementHost {
  append(element: HTMLMediaElement): void;
}

export interface LiveKitConversationDependencies {
  roomFactory?: () => Room;
  microphoneFactory?: typeof createLocalAudioTrack;
  sessionTimeoutMs?: number;
  audioElementHost?: AudioElementHost;
}

const DEFAULT_SESSION_TIMEOUT_MS = 175_000;

export class LiveKitConversationTransport {
  private readonly room: Room;
  private readonly microphoneFactory: typeof createLocalAudioTrack;
  private readonly sessionTimeoutMs: number;
  private readonly audioElementHost: AudioElementHost;
  private readonly attachedAudio = new Set<HTMLMediaElement>();
  private microphone: LocalAudioTrack | null = null;
  private session: LiveSessionResponse | null = null;
  private agentState: NormalizedAgentState = "listening";
  private disconnectRequested = false;
  private disconnected = false;
  private sessionTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private readonly callbacks: LiveKitConversationCallbacks,
    dependencies: LiveKitConversationDependencies = {},
  ) {
    this.room = dependencies.roomFactory?.() ?? new Room({ adaptiveStream: false, dynacast: false });
    this.microphoneFactory = dependencies.microphoneFactory ?? createLocalAudioTrack;
    this.sessionTimeoutMs = dependencies.sessionTimeoutMs ?? DEFAULT_SESSION_TIMEOUT_MS;
    this.audioElementHost = dependencies.audioElementHost ?? document.body;
    if (this.sessionTimeoutMs <= 0 || this.sessionTimeoutMs > 180_000) {
      throw new Error("live browser session timeout must be at most three minutes");
    }

    this.room.on(RoomEvent.TrackSubscribed, (track, _publication, participant) => {
      if (participant.identity.startsWith("voice-worker-") && track.kind === Track.Kind.Audio) {
        this.attachAgentAudio(track);
      }
    });
    this.room.on(RoomEvent.ParticipantAttributesChanged, (changed, participant) => {
      if (!participant.identity.startsWith("voice-worker-")) return;
      const normalized = normalizeAgentState(changed["lk.agent.state"]);
      if (normalized === null) return;
      this.agentState = normalized;
      this.callbacks.onAgentState(normalized);
    });
    this.room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
      if (
        this.agentState === "speaking" &&
        this.session !== null &&
        speakers.some((participant) => participant.identity === this.session?.participantIdentity)
      ) {
        this.callbacks.onLocalSpeechWhileAgentSpeaking();
      }
    });
    this.room.on(RoomEvent.TranscriptionReceived, (segments, participant) => {
      if (this.session === null || participant === undefined) return;
      const role = participant.identity.startsWith("voice-worker-")
        ? "agent"
        : participant.identity === this.session.participantIdentity
          ? "user"
          : null;
      if (role === null) return;
      for (const segment of segments) {
        const text = segment.text.trim();
        if (!text) continue;
        this.callbacks.onTranscript({
          id: segment.id,
          role,
          text,
          final: segment.final,
        });
      }
    });
    this.room.on(RoomEvent.DataReceived, (payload, participant, _kind, topic) => {
      if (
        this.session === null ||
        participant === undefined ||
        !participant.identity.startsWith("voice-worker-")
      ) return;
      if (topic === CONVERSATION_DIAGNOSTICS_TOPIC) {
        const event = parseConversationDiagnosticEvent(payload);
        if (event === null || event.attemptId !== this.session.attemptId) return;
        this.callbacks.onDiagnostic(event);
        return;
      }
      if (topic === PRESENTATION_STATE_TOPIC) {
        const event = parsePresentationStateUpdate(payload);
        if (event === null || event.attemptId !== this.session.attemptId) return;
        this.callbacks.onPresentation(event);
      }
    });
    this.room.on(RoomEvent.AudioPlaybackStatusChanged, (playing) => {
      if (!playing) this.callbacks.onAudioPlaybackBlocked();
    });
    this.room.on(RoomEvent.ParticipantDisconnected, (participant) => {
      if (!participant.identity.startsWith("voice-worker-") || this.disconnectRequested) return;
      this.callbacks.onDisconnected();
      void this.disconnect();
    });
    this.room.on(RoomEvent.Disconnected, () => {
      this.releaseLocalMedia();
      if (!this.disconnectRequested) this.callbacks.onDisconnected();
    });
  }

  primeAudio(): void {
    void this.room.startAudio().catch(() => undefined);
  }

  async connect(session: LiveSessionResponse): Promise<void> {
    this.session = session;
    this.disconnectRequested = false;
    this.disconnected = false;
    await this.room.connect(session.serverUrl, session.participantToken, {
      autoSubscribe: true,
    });
    this.microphone = await this.microphoneFactory({
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
      channelCount: 1,
    });
    await this.room.localParticipant.publishTrack(this.microphone, {
      source: Track.Source.Microphone,
    });
    this.sessionTimer = setTimeout(() => {
      if (this.session === null) return;
      this.callbacks.onDisconnected();
      void this.disconnect();
    }, this.sessionTimeoutMs);
    this.callbacks.onConnected(session.backend);
  }

  async unlockAudio(): Promise<void> {
    await this.room.startAudio();
  }

  async continuePresentation(): Promise<void> {
    if (this.session === null) {
      throw new Error("live presentation is not connected");
    }
    await this.room.localParticipant.publishData(
      new TextEncoder().encode(JSON.stringify({ action: "continue" })),
      { reliable: true, topic: PRESENTATION_COMMAND_TOPIC },
    );
  }

  async disconnect(): Promise<void> {
    if (this.disconnected) return;
    this.disconnected = true;
    this.disconnectRequested = true;
    if (this.sessionTimer !== null) {
      clearTimeout(this.sessionTimer);
      this.sessionTimer = null;
    }
    const microphone = this.microphone;
    this.microphone = null;
    if (microphone !== null) {
      try {
        await this.room.localParticipant.unpublishTrack(microphone);
      } finally {
        microphone.stop();
      }
    }
    this.releaseAttachedAudio();
    try {
      await this.room.disconnect();
    } finally {
      this.session = null;
    }
  }

  private attachAgentAudio(track: RemoteTrack): void {
    const element = track.attach();
    element.autoplay = true;
    element.dataset.liveVoiceAudio = "true";
    element.style.display = "none";
    this.audioElementHost.append(element);
    this.attachedAudio.add(element);
  }

  private releaseLocalMedia(): void {
    this.microphone?.stop();
    this.microphone = null;
    this.releaseAttachedAudio();
  }

  private releaseAttachedAudio(): void {
    for (const element of this.attachedAudio) element.remove();
    this.attachedAudio.clear();
  }
}

function normalizeAgentState(value: string | undefined): NormalizedAgentState | null {
  return value === "listening" || value === "thinking" || value === "speaking"
    ? value
    : null;
}
