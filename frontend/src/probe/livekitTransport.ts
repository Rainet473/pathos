import {
  Room,
  RoomEvent,
  Track,
  createLocalAudioTrack,
  type LocalAudioTrack,
  type RemoteTrack,
} from "livekit-client";

import {
  CONTROL_TOPIC,
  createControlPacket,
  parseStatusPacket,
  type ProbeSessionResponse,
  type ProbeStatusPacket,
} from "./protocol";

export interface LiveKitProbeCallbacks {
  onStatus: (status: ProbeStatusPacket) => void;
  onDisconnected: () => void;
  onAudioPlaybackBlocked: () => void;
}

export interface LiveKitProbeDependencies {
  roomFactory?: () => Room;
  microphoneFactory?: typeof createLocalAudioTrack;
  sessionTimeoutMs?: number;
}

const DEFAULT_SESSION_TIMEOUT_MS = 55_000;
const REPLAY_ACK_TIMEOUT_MS = 500;

export class LiveKitProbeTransport {
  private readonly room: Room;
  private readonly microphoneFactory: typeof createLocalAudioTrack;
  private microphone: LocalAudioTrack | null = null;
  private readonly attachedAudio = new Set<HTMLMediaElement>();
  private session: ProbeSessionResponse | null = null;
  private startedAt = 0;
  private disconnectRequested = false;
  private terminalStatusReceived = false;
  private sessionTimer: ReturnType<typeof setTimeout> | null = null;
  private readonly sessionTimeoutMs: number;

  constructor(
    private readonly callbacks: LiveKitProbeCallbacks,
    dependencies: LiveKitProbeDependencies = {},
  ) {
    this.room = dependencies.roomFactory?.() ?? new Room({ adaptiveStream: false, dynacast: false });
    this.microphoneFactory = dependencies.microphoneFactory ?? createLocalAudioTrack;
    this.sessionTimeoutMs = dependencies.sessionTimeoutMs ?? DEFAULT_SESSION_TIMEOUT_MS;
    if (this.sessionTimeoutMs <= 0 || this.sessionTimeoutMs >= 60_000) {
      throw new Error("probe browser session timeout must be below one minute");
    }
    this.room.on(RoomEvent.DataReceived, (payload, participant, _kind, topic) => {
      if (topic !== CONTROL_TOPIC || !participant?.identity.startsWith("probe-worker-")) return;
      const status = parseStatusPacket(payload);
      if (status !== null) void this.deliverStatus(status);
    });
    this.room.on(RoomEvent.TrackSubscribed, (track, _publication, participant) => {
      if (participant.identity.startsWith("probe-worker-") && track.kind === Track.Kind.Audio) {
        this.attachReplayTrack(track);
      }
    });
    this.room.on(RoomEvent.AudioPlaybackStatusChanged, (playing) => {
      if (!playing) this.callbacks.onAudioPlaybackBlocked();
    });
    this.room.on(RoomEvent.ParticipantDisconnected, (participant) => {
      if (!participant.identity.startsWith("probe-worker-") || this.disconnectRequested) return;
      if (!this.terminalStatusReceived) this.callbacks.onDisconnected();
      void this.disconnect();
    });
    this.room.on(RoomEvent.Disconnected, () => {
      this.stopLocalMicrophone();
      if (!this.disconnectRequested) this.callbacks.onDisconnected();
    });
  }

  primeAudio(): void {
    // startAudio emits AudioPlaybackStatusChanged on failure. Consume the
    // rejection here because this call must remain inside the initial gesture.
    void this.room.startAudio().catch(() => undefined);
  }

  async connect(session: ProbeSessionResponse): Promise<void> {
    this.disconnectRequested = false;
    this.terminalStatusReceived = false;
    this.session = session;
    this.startedAt = performance.now();
    await this.room.connect(session.serverUrl, session.participantToken, {
      autoSubscribe: true,
    });
    this.sessionTimer = setTimeout(() => {
      if (this.session === null) return;
      this.callbacks.onDisconnected();
      void this.disconnect();
    }, this.sessionTimeoutMs);
  }

  async startCapture(): Promise<void> {
    const session = this.requiredSession();
    if (this.microphone !== null) return;
    this.microphone = await this.microphoneFactory({
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
      channelCount: 1,
    });
    await this.room.localParticipant.publishTrack(this.microphone, {
      source: Track.Source.Microphone,
    });
    await this.room.localParticipant.publishData(
      createControlPacket("capture_started", session.attemptId, this.elapsedMs()),
      { reliable: true, topic: CONTROL_TOPIC },
    );
  }

  async stopCapture(): Promise<void> {
    const session = this.requiredSession();
    const microphone = this.microphone;
    if (microphone === null) return;
    this.microphone = null;
    try {
      await this.room.localParticipant.publishData(
        createControlPacket("capture_stopped", session.attemptId, this.elapsedMs()),
        { reliable: true, topic: CONTROL_TOPIC },
      );
    } finally {
      try {
        await this.room.localParticipant.unpublishTrack(microphone);
      } finally {
        microphone.stop();
      }
    }
  }

  async unlockAudio(): Promise<void> {
    await this.room.startAudio();
  }

  async disconnect(): Promise<void> {
    this.disconnectRequested = true;
    if (this.sessionTimer !== null) {
      clearTimeout(this.sessionTimer);
      this.sessionTimer = null;
    }
    this.stopLocalMicrophone();
    for (const element of this.attachedAudio) {
      element.remove();
    }
    this.attachedAudio.clear();
    try {
      await this.room.disconnect();
    } finally {
      this.session = null;
    }
  }

  private attachReplayTrack(track: RemoteTrack): void {
    const element = track.attach();
    element.autoplay = true;
    element.dataset.probeAudio = "true";
    element.style.display = "none";
    document.body.append(element);
    this.attachedAudio.add(element);
  }

  private async deliverStatus(status: ProbeStatusPacket): Promise<void> {
    if (status.type === "replay_completed" || status.type === "failed") {
      this.terminalStatusReceived = true;
    }
    this.callbacks.onStatus(status);
    if (
      status.type === "replay_completed" &&
      this.session !== null &&
      status.attemptId === this.session.attemptId
    ) {
      try {
        await Promise.race([
          this.room.localParticipant.publishData(
            createControlPacket("replay_acknowledged", status.attemptId, this.elapsedMs()),
            { reliable: true, topic: CONTROL_TOPIC },
          ),
          new Promise<void>((resolve) => setTimeout(resolve, REPLAY_ACK_TIMEOUT_MS)),
        ]);
      } catch {
        // The terminal status is still actionable if its acknowledgement fails.
      }
    }
  }

  private requiredSession(): ProbeSessionResponse {
    if (this.session === null) throw new Error("probe transport is not connected");
    return this.session;
  }

  private stopLocalMicrophone(): void {
    this.microphone?.stop();
    this.microphone = null;
  }

  private elapsedMs(): number {
    return Math.max(0, performance.now() - this.startedAt);
  }
}
