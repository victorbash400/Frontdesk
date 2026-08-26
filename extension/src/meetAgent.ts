type MeetWorkerConfig = {
  meetingId: string;
  runtimeId: string;
  bridgeId: string;
  socketUrl: string;
};

export {};

type WindowWithMeetWorker = Window & {
  __frontDeskMeetWorker?: boolean;
  webkitAudioContext?: typeof AudioContext;
};

const workerWindow = window as WindowWithMeetWorker;
const CONFIG_PREFIX = '#front-desk-meet=';
const AUDIO_CHANNEL = 1;
const VIDEO_CHANNEL = 2;
const CAPTURE_RATE = 16_000;
const PLAYBACK_RATE = 24_000;

function initialize(): void {
  if (workerWindow.__frontDeskMeetWorker)
    return;
  const config = readConfig();
  if (config) {
    workerWindow.__frontDeskMeetWorker = true;
    start(config).catch(error => console.error('[Front Desk Meet]', error));
  }
}

function readConfig(): MeetWorkerConfig | undefined {
  try {
    const encoded = location.hash.startsWith(CONFIG_PREFIX) ? location.hash.slice(CONFIG_PREFIX.length) : sessionStorage.getItem('frontDeskMeetWorker');
    if (!encoded)
      return undefined;
    sessionStorage.setItem('frontDeskMeetWorker', encoded);
    const payload = JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(paddedBase64(encoded)), character => character.charCodeAt(0)))) as MeetWorkerConfig;
    if (!payload.meetingId || !payload.runtimeId || !payload.bridgeId || !payload.socketUrl)
      return undefined;
    history.replaceState(null, '', `${location.pathname}${location.search}`);
    return payload;
  } catch {
    return undefined;
  }
}

function paddedBase64(value: string): string {
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/');
  return normalized + '='.repeat((4 - normalized.length % 4) % 4);
}

async function start(config: MeetWorkerConfig): Promise<void> {
  console.log('[Front Desk Meet] Starting worker', config.meetingId);
  const audio = new MeetAudioBridge();
  audio.installMicrophone();
  const socket = new WorkerSocket();
  audio.connect(socket);
  installPeerCapture(audio);
  const controls = new MeetControls(socket, audio);
  socket.addEventListener('open', () => {
    console.log('[Front Desk Meet] Media socket connected');
    socket.send(JSON.stringify({ type: 'browser_ready' }));
  });
  socket.addEventListener('message', rawEvent => {
    const event = rawEvent as MessageEvent;
    if (event.data instanceof ArrayBuffer) {
      const packet = new Uint8Array(event.data);
      if (packet[0] === AUDIO_CHANNEL)
        audio.play(packet.subarray(1));
      return;
    }
    const message = JSON.parse(String(event.data)) as { type?: string };
    if (message.type === 'meeting_complete' || message.type === 'error')
      controls.leave();
  });
  controls.observe();
}

class WorkerSocket extends EventTarget {
  readyState: number = WebSocket.CONNECTING;
  private readonly relay = ensureRelayElement();

  constructor() {
    super();
    const receive = () => {
      const raw = this.relay.getAttribute('data-incoming');
      if (!raw)
        return;
      const message = JSON.parse(raw) as { kind: string; text?: string; binary?: string };
      if (message.kind === 'open') {
        this.readyState = WebSocket.OPEN;
        this.dispatchEvent(new Event('open'));
      } else if (message.kind === 'close' || message.kind === 'rejected') {
        this.readyState = WebSocket.CLOSED;
        this.dispatchEvent(new CloseEvent('close'));
      } else {
        this.dispatchEvent(new MessageEvent('message', { data: message.binary ? base64ToBytes(message.binary).buffer : message.text || '' }));
      }
    };
    document.addEventListener('front-desk-meet-incoming', receive);
    if (this.relay.hasAttribute('data-incoming'))
      queueMicrotask(receive);
  }

  send(data: string | ArrayBufferView): void {
    this.write(typeof data === 'string'
      ? { kind: 'message', text: data }
      : { kind: 'message', binary: bytesToBase64(new Uint8Array(data.buffer, data.byteOffset, data.byteLength)) });
  }

  close(code = 1000, reason = ''): void {
    this.write({ kind: 'close', code, reason });
  }

  private write(message: object): void {
    this.relay.setAttribute('data-outgoing', JSON.stringify(message));
    document.dispatchEvent(new Event('front-desk-meet-outgoing'));
  }
}

function ensureRelayElement(): HTMLElement {
  const existing = document.querySelector<HTMLElement>('front-desk-meet-relay');
  if (existing)
    return existing;
  const relay = document.createElement('front-desk-meet-relay');
  relay.style.display = 'none';
  (document.documentElement || document).appendChild(relay);
  return relay;
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = '';
  for (const byte of bytes)
    binary += String.fromCharCode(byte);
  return btoa(binary);
}

function base64ToBytes(value: string): Uint8Array {
  return Uint8Array.from(atob(value), character => character.charCodeAt(0));
}

class MeetAudioBridge {
  private readonly context = new AudioContext({ sampleRate: PLAYBACK_RATE });
  private readonly microphone = this.context.createMediaStreamDestination();
  private socket?: WorkerSocket;
  private readonly captureContexts = new Set<AudioContext>();
  private playbackTime = 0;

  connect(socket: WorkerSocket): void {
    this.socket = socket;
  }

  outgoingTrack(): MediaStreamTrack {
    return this.microphone.stream.getAudioTracks()[0];
  }

  isOutgoingTrack(track: MediaStreamTrack): boolean {
    return track === this.outgoingTrack();
  }

  installMicrophone(): void {
    const native = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia = async constraints => {
      const wantsAudio = Boolean(constraints?.audio);
      const wantsVideo = Boolean(constraints?.video);
      if (!wantsAudio)
        return native(constraints);
      const stream = new MediaStream([this.outgoingTrack()]);
      if (wantsVideo) {
        const video = await native({ video: constraints?.video, audio: false });
        for (const track of video.getVideoTracks())
          stream.addTrack(track);
      }
      return stream;
    };
  }

  capture(stream: MediaStream): void {
    const tracks = stream.getAudioTracks();
    if (!tracks.length)
      return;
    const context = new AudioContext({ sampleRate: CAPTURE_RATE });
    this.captureContexts.add(context);
    void context.resume();
    const source = context.createMediaStreamSource(new MediaStream(tracks));
    const processor = context.createScriptProcessor(2048, 1, 1);
    const silence = context.createGain();
    silence.gain.value = 0;
    processor.onaudioprocess = event => {
      if (this.socket?.readyState !== WebSocket.OPEN)
        return;
      const samples = event.inputBuffer.getChannelData(0);
      const packet = new Uint8Array(1 + samples.length * 2);
      packet[0] = AUDIO_CHANNEL;
      const view = new DataView(packet.buffer);
      for (let index = 0; index < samples.length; index++)
        view.setInt16(1 + index * 2, Math.max(-1, Math.min(1, samples[index])) * 0x7fff, true);
      this.socket.send(packet);
    };
    source.connect(processor).connect(silence).connect(context.destination);
    for (const track of tracks)
      track.addEventListener('ended', () => {
        this.captureContexts.delete(context);
        void context.close();
      }, { once: true });
  }

  captureVideo(track: MediaStreamTrack): void {
    const video = document.createElement('video');
    video.srcObject = new MediaStream([track]);
    video.muted = true;
    void video.play();
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    let lastFrame = 0;
    const frame = (timestamp: number) => {
      if (this.socket?.readyState !== WebSocket.OPEN || track.readyState === 'ended')
        return;
      if (timestamp - lastFrame >= 1000 && video.videoWidth && video.videoHeight && context) {
        lastFrame = timestamp;
        const scale = Math.min(1, 768 / video.videoWidth);
        canvas.width = Math.round(video.videoWidth * scale);
        canvas.height = Math.round(video.videoHeight * scale);
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        canvas.toBlob(blob => {
          if (!blob || this.socket?.readyState !== WebSocket.OPEN)
            return;
          void blob.arrayBuffer().then(buffer => {
            const packet = new Uint8Array(buffer.byteLength + 1);
            packet[0] = VIDEO_CHANNEL;
            packet.set(new Uint8Array(buffer), 1);
            this.socket?.send(packet);
          });
        }, 'image/jpeg', 0.72);
      }
      video.requestVideoFrameCallback(frame);
    };
    video.requestVideoFrameCallback(frame);
  }

  play(bytes: Uint8Array): void {
    void this.context.resume();
    const samples = new Float32Array(Math.floor(bytes.byteLength / 2));
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    for (let index = 0; index < samples.length; index++)
      samples[index] = view.getInt16(index * 2, true) / 0x8000;
    const buffer = this.context.createBuffer(1, samples.length, PLAYBACK_RATE);
    buffer.copyToChannel(samples, 0);
    const source = this.context.createBufferSource();
    source.buffer = buffer;
    source.connect(this.microphone);
    const now = this.context.currentTime;
    this.playbackTime = Math.max(now + 0.02, this.playbackTime);
    source.start(this.playbackTime);
    this.playbackTime += buffer.duration;
  }

  activate(): void {
    void this.context.resume();
    for (const context of this.captureContexts)
      void context.resume();
  }

  send(message: object): void {
    if (this.socket?.readyState === WebSocket.OPEN)
      this.socket.send(JSON.stringify(message));
  }

  close(): void {
    void this.context.close();
  }
}

function installPeerCapture(audio: MeetAudioBridge): void {
  const NativePeerConnection = window.RTCPeerConnection;
  const nativeReplaceTrack = RTCRtpSender.prototype.replaceTrack;
  RTCRtpSender.prototype.replaceTrack = function(track: MediaStreamTrack | null): Promise<void> {
    const replacement = track?.kind === 'audio' && !audio.isOutgoingTrack(track) ? audio.outgoingTrack() : track;
    return nativeReplaceTrack.call(this, replacement);
  };
  window.RTCPeerConnection = class extends NativePeerConnection {
    constructor(configuration?: RTCConfiguration) {
      super(configuration);
      this.addEventListener('track', event => {
        if (event.track.kind === 'audio')
          audio.capture(event.streams[0] || new MediaStream([event.track]));
        if (event.track.kind === 'video')
          audio.captureVideo(event.track);
      });
    }

    override addTrack(track: MediaStreamTrack, ...streams: MediaStream[]): RTCRtpSender {
      const replacement = track.kind === 'audio' && !audio.isOutgoingTrack(track) ? audio.outgoingTrack() : track;
      return super.addTrack(replacement, ...streams);
    }

    override addTransceiver(trackOrKind: MediaStreamTrack | string, init?: RTCRtpTransceiverInit): RTCRtpTransceiver {
      if (typeof trackOrKind !== 'string' && trackOrKind.kind === 'audio' && !audio.isOutgoingTrack(trackOrKind))
        return super.addTransceiver(audio.outgoingTrack(), init);
      return super.addTransceiver(trackOrKind, init);
    }
  };
}

class MeetControls {
  private observer?: MutationObserver;
  private joined = false;
  private participantReported = false;
  private readonly handledAdmissionButtons = new WeakSet<HTMLButtonElement>();

  constructor(private readonly socket: WorkerSocket, private readonly audio: MeetAudioBridge) {}

  observe(): void {
    this.apply();
    this.socket.addEventListener('open', () => this.reportState());
    this.observer = new MutationObserver(() => this.apply());
    this.observer.observe(document.documentElement, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ['aria-label'],
    });
  }

  leave(): void {
    const leave = findButton(/leave call|leave meeting|hang up/i);
    leave?.click();
    this.socket.close(1000, 'Meeting complete');
    this.observer?.disconnect();
  }

  private apply(): void {
    for (const button of findButtons(/admit|allow to join/i)) {
      if (this.handledAdmissionButtons.has(button))
        continue;
      this.handledAdmissionButtons.add(button);
      button.click();
    }
    const hasClient = participantCount() >= 2;
    if (hasClient !== this.participantReported) {
      this.participantReported = hasClient;
      if (this.socket.readyState === WebSocket.OPEN)
        this.socket.send(JSON.stringify({ type: hasClient ? 'participant_arrived' : 'participant_left' }));
    }
    const camera = findButton(/turn off camera/i);
    if (camera) {
      camera.click();
      return;
    }
    if (this.joined)
      return;
    const join = findButton(/join now|ask to join/i);
    if (join && !join.disabled) {
      this.joined = true;
      this.audio.activate();
      join.click();
      this.socket.addEventListener('open', () => this.socket.send(JSON.stringify({ type: 'browser_joined' })), { once: true });
      if (this.socket.readyState === WebSocket.OPEN)
        this.socket.send(JSON.stringify({ type: 'browser_joined' }));
    }
  }

  private reportState(): void {
    this.socket.send(JSON.stringify({ type: 'browser_ready' }));
    if (this.joined)
      this.socket.send(JSON.stringify({ type: 'browser_joined' }));
    if (this.participantReported)
      this.socket.send(JSON.stringify({ type: 'participant_arrived' }));
  }
}

function participantCount(): number {
  const peopleButton = [...document.querySelectorAll<HTMLButtonElement>('button')].find(button =>
    /^people\b/i.test(button.getAttribute('aria-label') || '') && button.offsetParent !== null,
  );
  const visibleCount = peopleButton?.textContent?.match(/\d+/)?.[0];
  const participantIds = new Set(
    [...document.querySelectorAll<HTMLElement>('[data-participant-id]')]
      .map(element => element.dataset.participantId)
      .filter((value): value is string => Boolean(value)),
  );
  const count = visibleCount ? Number.parseInt(visibleCount, 10) : Math.max(1, participantIds.size);
  document.documentElement.setAttribute('data-front-desk-participant-debug', JSON.stringify({
    source: visibleCount ? 'people_button' : participantIds.size ? 'participant_ids' : 'fail_closed',
    participantIds: [...participantIds],
    count,
  }));
  return count;
}

function findButton(pattern: RegExp): HTMLButtonElement | undefined {
  return findButtons(pattern)[0];
}

function findButtons(pattern: RegExp): HTMLButtonElement[] {
  return [...document.querySelectorAll<HTMLButtonElement>('button')].filter(button => {
    const label = `${button.getAttribute('aria-label') || ''} ${button.textContent || ''}`.trim();
    return pattern.test(label) && button.offsetParent !== null;
  });
}

initialize();
