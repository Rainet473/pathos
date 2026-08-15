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
}

export class LiveKitProbeTransport {
  private readonly room: Room;
  private readonly microphoneFactory: typeof createLocalAudioTrack;
  private microphone: LocalAudioTrack | null = null;
  private readonly attachedAudio = new Set<HTMLMediaElement>();
  private session: ProbeSessionResponse | null = null;
  private startedAt = 0;
  private disconnectRequested = false;

  constructor(
    private readonly callbacks: LiveKitProbeCallbacks,
    dependencies: LiveKitProbeDependencies = {},
  ) {
    this.room = dependencies.roomFactory?.() ?? new Room({ adaptiveStream: false, dynacast: false });
    this.microphoneFactory = dependencies.microphoneFactory ?? createLocalAudioTrack;
    this.room.on(RoomEvent.DataReceived, (payload, participant, _kind, topic) => {
      if (topic !== CONTROL_TOPIC || !participant?.identity.startsWith("probe-worker-")) return;
      const status = parseStatusPacket(payload);
      if (status !== null) this.callbacks.onStatus(status);
    });
    this.room.on(RoomEvent.TrackSubscribed, (track, _publication, participant) => {
      if (participant.identity.startsWith("probe-worker-") && track.kind === Track.Kind.Audio) {
        this.attachReplayTrack(track);
      }
    });
    this.room.on(RoomEvent.AudioPlaybackStatusChanged, (playing) => {
      if (!playing) this.callbacks.onAudioPlaybackBlocked();
    });
    this.room.on(RoomEvent.Disconnected, () => {
      this.stopLocalMicrophone();
      if (!this.disconnectRequested) this.callbacks.onDisconnected();
    });
  }

  async primeAudio(): Promise<void> {
    await this.room.startAudio();
  }

  async connect(session: ProbeSessionResponse): Promise<void> {
    this.disconnectRequested = false;
    this.session = session;
    this.startedAt = performance.now();
    await this.room.connect(session.serverUrl, session.participantToken, {
      autoSubscribe: true,
    });
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
