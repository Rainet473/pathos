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
import {
  CONVERSATION_TRANSCRIPT_TOPIC,
  parseConversationTranscriptUpdate,
} from "./transcript";
import {
  CONVERSATION_LIFECYCLE_TOPIC,
  parseConversationLifecycleUpdate,
  type LiveSessionEndReason,
} from "./lifecycle";

export interface LiveKitConversationCallbacks {
  onConnected: (backend: VoiceBackendIdentity) => void;
  onAgentState: (state: NormalizedAgentState) => void;
  onLocalSpeechWhileAgentSpeaking: () => void;
  onTranscript: (entry: TranscriptEntry) => void;
  onDiagnostic: (event: ConversationDiagnosticEvent) => void;
  onPresentation: (event: PresentationStateUpdate) => void;
  onEnded: (reason: LiveSessionEndReason) => void;
  onDisconnected: () => void;
  onAudioPlaybackBlocked: () => void;
}

interface AudioElementHost {
  append(element: HTMLMediaElement): void;
}

export interface LiveKitConversationDependencies {
  roomFactory?: () => Room;
  microphoneFactory?: typeof createLocalAudioTrack;
  audioElementHost?: AudioElementHost;
}

export class LiveKitConversationTransport {
  private readonly room: Room;
  private readonly microphoneFactory: typeof createLocalAudioTrack;
  private readonly audioElementHost: AudioElementHost;
  private readonly attachedAudio = new Set<HTMLMediaElement>();
  private microphone: LocalAudioTrack | null = null;
  private session: LiveSessionResponse | null = null;
  private agentState: NormalizedAgentState = "listening";
  private disconnectRequested = false;
  private disconnected = false;
  private idleTimeoutMs = 0;
  private idleTimer: ReturnType<typeof setTimeout> | null = null;
  private absoluteTimer: ReturnType<typeof setTimeout> | null = null;
  private terminalReason: LiveSessionEndReason | null = null;
  private lastTranscriptSequence = 0;

  constructor(
    private readonly callbacks: LiveKitConversationCallbacks,
    dependencies: LiveKitConversationDependencies = {},
  ) {
    this.room = dependencies.roomFactory?.() ?? new Room({ adaptiveStream: false, dynacast: false });
    this.microphoneFactory = dependencies.microphoneFactory ?? createLocalAudioTrack;
    this.audioElementHost = dependencies.audioElementHost ?? document.body;

    this.room.on(RoomEvent.TrackSubscribed, (track, _publication, participant) => {
      if (participant.identity.startsWith("voice-worker-") && track.kind === Track.Kind.Audio) {
        this.touchActivity();
        this.attachAgentAudio(track);
      }
    });
    this.room.on(RoomEvent.ParticipantAttributesChanged, (changed, participant) => {
      if (!participant.identity.startsWith("voice-worker-")) return;
      const normalized = normalizeAgentState(changed["lk.agent.state"]);
      if (normalized === null) return;
      this.touchActivity();
      this.agentState = normalized;
      this.callbacks.onAgentState(normalized);
    });
    this.room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
      if (speakers.length > 0) this.touchActivity();
      if (
        this.agentState === "speaking" &&
        this.session !== null &&
        speakers.some((participant) => participant.identity === this.session?.participantIdentity)
      ) {
        this.callbacks.onLocalSpeechWhileAgentSpeaking();
      }
    });
    this.room.on(RoomEvent.DataReceived, (payload, participant, _kind, topic) => {
      if (
        this.session === null ||
        participant === undefined ||
        !participant.identity.startsWith("voice-worker-")
      ) return;
      if (topic === CONVERSATION_LIFECYCLE_TOPIC) {
        const update = parseConversationLifecycleUpdate(payload);
        if (update === null || update.attemptId !== this.session.attemptId) return;
        this.finishNormally(update.reason);
        return;
      }
      if (topic === CONVERSATION_DIAGNOSTICS_TOPIC) {
        const event = parseConversationDiagnosticEvent(payload);
        if (event === null || event.attemptId !== this.session.attemptId) return;
        this.touchActivity();
        this.callbacks.onDiagnostic(event);
        return;
      }
      if (topic === CONVERSATION_TRANSCRIPT_TOPIC) {
        const update = parseConversationTranscriptUpdate(payload);
        if (
          update === null ||
          update.attemptId !== this.session.attemptId ||
          update.sequence <= this.lastTranscriptSequence
        ) return;
        this.touchActivity();
        this.lastTranscriptSequence = update.sequence;
        this.callbacks.onTranscript(update.entry);
        return;
      }
      if (topic === PRESENTATION_STATE_TOPIC) {
        const event = parsePresentationStateUpdate(payload);
        if (event === null || event.attemptId !== this.session.attemptId) return;
        this.touchActivity();
        this.callbacks.onPresentation(event);
      }
    });
    this.room.on(RoomEvent.AudioPlaybackStatusChanged, (playing) => {
      if (playing) this.touchActivity();
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
    this.lastTranscriptSequence = 0;
    this.disconnectRequested = false;
    this.disconnected = false;
    this.terminalReason = null;
    validateLifecyclePolicy(session);
    this.idleTimeoutMs = session.idleTimeoutSeconds * 1_000;
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
    this.touchActivity();
    this.absoluteTimer = setTimeout(() => {
      this.finishNormally("absolute_timeout");
    }, session.absoluteTimeoutSeconds * 1_000);
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

  async navigateToSlide(slideId: string): Promise<void> {
    if (this.session === null) {
      throw new Error("live presentation is not connected");
    }
    const normalizedSlideId = slideId.trim();
    if (!normalizedSlideId) {
      throw new Error("slide id cannot be blank");
    }
    await this.room.localParticipant.publishData(
      new TextEncoder().encode(
        JSON.stringify({ action: "navigate", slideId: normalizedSlideId }),
      ),
      { reliable: true, topic: PRESENTATION_COMMAND_TOPIC },
    );
  }

  async disconnect(): Promise<void> {
    if (this.disconnected) return;
    this.disconnected = true;
    this.disconnectRequested = true;
    this.clearLifecycleTimers();
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
      this.idleTimeoutMs = 0;
      this.lastTranscriptSequence = 0;
    }
  }

  private touchActivity(): void {
    if (this.session === null || this.terminalReason !== null || this.disconnected) return;
    if (this.idleTimer !== null) clearTimeout(this.idleTimer);
    this.idleTimer = setTimeout(() => {
      this.finishNormally("idle_timeout");
    }, this.idleTimeoutMs);
  }

  private finishNormally(reason: LiveSessionEndReason): void {
    if (this.session === null || this.terminalReason !== null || this.disconnected) return;
    this.terminalReason = reason;
    this.callbacks.onEnded(reason);
    void this.disconnect();
  }

  private clearLifecycleTimers(): void {
    if (this.idleTimer !== null) {
      clearTimeout(this.idleTimer);
      this.idleTimer = null;
    }
    if (this.absoluteTimer !== null) {
      clearTimeout(this.absoluteTimer);
      this.absoluteTimer = null;
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

function validateLifecyclePolicy(session: LiveSessionResponse): void {
  if (
    !Number.isFinite(session.idleTimeoutSeconds) ||
    !Number.isFinite(session.absoluteTimeoutSeconds) ||
    session.idleTimeoutSeconds <= 0 ||
    session.absoluteTimeoutSeconds <= 0 ||
    session.idleTimeoutSeconds >= session.absoluteTimeoutSeconds ||
    session.absoluteTimeoutSeconds > 900
  ) {
    throw new Error("live session returned an invalid lifecycle policy");
  }
}

function normalizeAgentState(value: string | undefined): NormalizedAgentState | null {
  return value === "listening" || value === "thinking" || value === "speaking"
    ? value
    : null;
}
