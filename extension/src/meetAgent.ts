import { pcmPacket, resampleMono } from './audioPcm';
import { AGENT_EARS_NAME, isAudioDeviceLabel } from './agentAudioDevices';
import { AGENT_MICROPHONE_NAME, isAgentMicrophoneLabel } from './agentMicrophone';

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
  const socket = new WorkerSocket(config);
  audio.connect(socket);
  await audio.installDevices();
  installPeerVideoCapture(audio);
  const controls = new MeetControls(socket, audio);
  socket.addEventListener('open', () => {
    console.log('[Front Desk Meet] Media socket connected');
    socket.diagnostic('worker.started', {
      audioCapture: AGENT_EARS_NAME,
      playbackRate: PLAYBACK_RATE,
      microphone: AGENT_MICROPHONE_NAME,
    });
    socket.send(JSON.stringify({ type: 'browser_ready' }));
  });
  socket.addEventListener('close', () => console.warn('[Front Desk Meet] Media socket closed'));
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

  constructor(private readonly config: MeetWorkerConfig) {
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
        console.error('[Front Desk Meet] Relay stopped', message);
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
    this.diagnostic('worker.closing', { code, reason });
    this.write({ kind: 'close', code, reason });
  }

  diagnostic(stage: string, details: Record<string, string | number | boolean> = {}): void {
    const correlated = {
      meetingId: this.config.meetingId,
      runtimeId: this.config.runtimeId,
      bridgeId: this.config.bridgeId,
      ...details,
    };
    console.log('[Front Desk Meet]', stage, correlated);
    if (this.readyState === WebSocket.OPEN)
      this.send(JSON.stringify({ type: 'diagnostic', stage, details: correlated }));
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
  private socket?: WorkerSocket;
  private microphoneDeviceId?: string;
  private captureSource?: MediaStreamAudioSourceNode;
  private captureProcessor?: ScriptProcessorNode;
  private captureSink?: GainNode;
  private capturePacketCount = 0;
  private capturePeak = 0;
  private playbackPacketCount = 0;
  private playbackTime = 0;

  connect(socket: WorkerSocket): void {
    this.socket = socket;
  }

  async installDevices(): Promise<void> {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const microphone = devices.find(device => device.kind === 'audioinput' && isAgentMicrophoneLabel(device.label));
    const writer = devices.find(device => device.kind === 'audiooutput' && isAgentMicrophoneLabel(device.label));
    const ears = devices.find(device => device.kind === 'audioinput' && isAudioDeviceLabel(device.label, AGENT_EARS_NAME));
    if (!microphone || !writer || !ears)
      throw new Error('Agent Mike and Agent Ears must both be installed.');
    const sinkContext = this.context as AudioContext & { setSinkId?: (sinkId: string) => Promise<void> };
    if (!sinkContext.setSinkId)
      throw new Error('This Chrome version cannot route Front Desk audio to Agent Mike.');
    await sinkContext.setSinkId(writer.deviceId);
    this.microphoneDeviceId = microphone.deviceId;
    this.socket?.diagnostic('microphone.device_bound', {
      name: AGENT_MICROPHONE_NAME,
      inputDeviceId: microphone.deviceId,
      outputDeviceId: writer.deviceId,
    });

    const earsStream = await navigator.mediaDevices.getUserMedia({
      audio: { deviceId: { exact: ears.deviceId } },
      video: false,
    });
    this.captureInput(earsStream);
    this.socket?.diagnostic('capture.agent_ears_bound', {
      name: AGENT_EARS_NAME,
      inputDeviceId: ears.deviceId,
    });

    const native = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia = async constraints => {
      const wantsAudio = Boolean(constraints?.audio);
      const wantsVideo = Boolean(constraints?.video);
      if (!wantsAudio)
        return native(constraints);
      this.socket?.diagnostic('microphone.agent_mike_requested', { wantsVideo });
      const stream = await native({
        audio: { deviceId: { exact: this.microphoneDeviceId! } },
        video: wantsVideo ? constraints?.video : false,
      });
      return stream;
    };
  }

  private captureInput(stream: MediaStream): void {
    const source = this.context.createMediaStreamSource(stream);
    const processor = this.context.createScriptProcessor(2048, 2, 1);
    const silentSink = this.context.createGain();
    silentSink.gain.value = 0;
    processor.onaudioprocess = event => this.processAudio(event.inputBuffer);
    source.connect(processor);
    processor.connect(silentSink);
    silentSink.connect(this.context.destination);
    this.captureSource = source;
    this.captureProcessor = processor;
    this.captureSink = silentSink;
  }

  private processAudio(buffer: AudioBuffer): void {
    if (this.socket?.readyState !== WebSocket.OPEN || !buffer.numberOfChannels)
      return;
    const mono = new Float32Array(buffer.length);
    for (let channel = 0; channel < buffer.numberOfChannels; channel++) {
      const input = buffer.getChannelData(channel);
      for (let index = 0; index < mono.length; index++)
        mono[index] += input[index] / buffer.numberOfChannels;
    }
    const samples = resampleMono(mono, buffer.sampleRate, CAPTURE_RATE);
    this.capturePacketCount += 1;
    const peak = pcmPeak(samples);
    this.capturePeak = Math.max(this.capturePeak, peak);
    document.documentElement.dataset.frontDeskAudioPeak = String(peak);
    this.socket.send(pcmPacket(AUDIO_CHANNEL, samples));
    if (this.capturePacketCount === 1 || this.capturePacketCount % 100 === 0) {
      this.socket.diagnostic('capture.audio_summary', {
        packets: this.capturePacketCount,
        samples: samples.length,
        sourceRate: buffer.sampleRate,
        peak: this.capturePeak,
      });
      this.capturePeak = 0;
    }
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
    this.playbackPacketCount += 1;
    if (this.playbackPacketCount === 1 || this.playbackPacketCount % 50 === 0) {
      this.socket?.diagnostic('playback.audio_summary', {
        packets: this.playbackPacketCount,
        bytes: bytes.byteLength,
        contextState: this.context.state,
      });
    }
    const samples = new Float32Array(Math.floor(bytes.byteLength / 2));
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    for (let index = 0; index < samples.length; index++)
      samples[index] = view.getInt16(index * 2, true) / 0x8000;
    const buffer = this.context.createBuffer(1, samples.length, PLAYBACK_RATE);
    buffer.copyToChannel(samples, 0);
    const source = this.context.createBufferSource();
    source.buffer = buffer;
    source.connect(this.context.destination);
    const now = this.context.currentTime;
    this.playbackTime = Math.max(now + 0.02, this.playbackTime);
    source.start(this.playbackTime);
    this.playbackTime += buffer.duration;
  }

  activate(): void {
    void this.context.resume();
    this.socket?.diagnostic('playback.activated', { contextState: this.context.state });
  }

  send(message: object): void {
    if (this.socket?.readyState === WebSocket.OPEN)
      this.socket.send(JSON.stringify(message));
  }

  close(): void {
    this.captureSource?.disconnect();
    this.captureProcessor?.disconnect();
    this.captureSink?.disconnect();
    void this.context.close();
  }
}

function pcmPeak(samples: Float32Array): number {
  let peak = 0;
  for (const sample of samples)
    peak = Math.max(peak, Math.round(Math.abs(sample) * 0x7fff));
  return peak;
}

function installPeerVideoCapture(audio: MeetAudioBridge): void {
  const NativePeerConnection = window.RTCPeerConnection;
  window.RTCPeerConnection = class extends NativePeerConnection {
    constructor(configuration?: RTCConfiguration) {
      super(configuration);
      this.addEventListener('track', event => {
        if (event.track.kind === 'video')
          audio.captureVideo(event.track);
      });
    }
  };
}

class MeetControls {
  private observer?: MutationObserver;
  private joined = false;
  private cameraDisabled = false;
  private participantReported?: boolean;
  private speakerState: 'closed' | 'settings' | 'speaker' | 'ready' = 'closed';
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
    this.socket.diagnostic('controls.leave', { leaveButtonFound: Boolean(findButton(/leave call|leave meeting|hang up/i)) });
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
      this.socket.diagnostic('controls.admit_clicked');
      button.click();
    }
    const participant = participantState();
    const hasClient = participant.count >= 2;
    if (hasClient !== this.participantReported) {
      this.participantReported = hasClient;
      this.socket.diagnostic('controls.participant_state', { present: hasClient, ...participant });
      if (this.socket.readyState === WebSocket.OPEN)
        this.socket.send(JSON.stringify({ type: hasClient ? 'participant_arrived' : 'participant_left' }));
    }
    this.configureSpeaker();
    const camera = findButton(/turn off camera/i);
    if (camera && !this.cameraDisabled) {
      this.cameraDisabled = true;
      this.socket.diagnostic('controls.camera_disabled');
      camera.click();
    }
    if (this.joined)
      return;
    if (this.speakerState !== 'ready')
      return;
    const join = findButton(/join now|ask to join|switch here/i);
    if (join && !join.disabled) {
      this.joined = true;
      this.audio.activate();
      this.socket.diagnostic('controls.join_clicked', { label: join.getAttribute('aria-label') || join.textContent || '' });
      join.click();
      this.socket.addEventListener('open', () => this.socket.send(JSON.stringify({ type: 'browser_joined' })), { once: true });
      if (this.socket.readyState === WebSocket.OPEN)
        this.socket.send(JSON.stringify({ type: 'browser_joined' }));
    }
  }

  private configureSpeaker(): void {
    if (this.speakerState === 'ready')
      return;
    const earsOption = findInteractiveDevice(AGENT_EARS_NAME);
    if (earsOption) {
      earsOption.click();
      this.speakerState = 'ready';
      this.socket.diagnostic('controls.speaker_configured', { speaker: AGENT_EARS_NAME });
      queueMicrotask(() => findButton(/close dialogue/i)?.click());
      return;
    }
    const speaker = findButton(/^speaker:/i);
    if (speaker) {
      if (this.speakerState !== 'speaker') {
        this.speakerState = 'speaker';
        speaker.click();
      }
      return;
    }
    const settings = findInteractiveExact('Settings');
    if (settings) {
      if (this.speakerState !== 'settings') {
        this.speakerState = 'settings';
        settings.click();
      }
      return;
    }
    if (this.speakerState === 'closed') {
      const moreOptions = document.querySelector<HTMLButtonElement>('button[aria-label="More options"]');
      if (moreOptions && moreOptions.offsetParent !== null)
        moreOptions.click();
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

type ParticipantState = { count: number; source: 'meet_badge' | 'people_control' | 'participant_ids' | 'fail_closed' };

function participantState(): ParticipantState {
  const badgeCounts = [...document.querySelectorAll<HTMLElement>('[animatable][jscontroller]')]
    .filter(element => element.offsetParent !== null && /^\d+$/.test(element.textContent?.trim() || ''))
    .map(element => Number.parseInt(element.textContent!.trim(), 10));
  const peopleControl = [...document.querySelectorAll<HTMLElement>('button, [role="button"]')].find(element =>
    /^people\b/i.test(`${element.getAttribute('aria-label') || ''} ${element.textContent || ''}`.trim()) && element.offsetParent !== null,
  );
  const visibleCount = peopleControl?.textContent?.match(/\d+/)?.[0]
    || peopleControl?.getAttribute('aria-label')?.match(/\d+/)?.[0];
  const participantIds = new Set(
    [...document.querySelectorAll<HTMLElement>('[data-participant-id]')]
      .map(element => element.dataset.participantId)
      .filter((value): value is string => Boolean(value)),
  );
  const badgeCount = badgeCounts.length ? Math.max(...badgeCounts) : undefined;
  const count = badgeCount ?? (visibleCount ? Number.parseInt(visibleCount, 10) : Math.max(1, participantIds.size));
  const source = badgeCount !== undefined ? 'meet_badge' : visibleCount ? 'people_control' : participantIds.size ? 'participant_ids' : 'fail_closed';
  document.documentElement.setAttribute('data-front-desk-participant-debug', JSON.stringify({
    source,
    participantIds: [...participantIds],
    count,
  }));
  return { count, source };
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

function findInteractiveExact(text: string): HTMLElement | undefined {
  return [...document.querySelectorAll<HTMLElement>('button, [role="button"], [role="menuitem"], [role="option"]')]
    .find(element => element.offsetParent !== null && element.textContent?.trim() === text);
}

function findInteractiveDevice(name: string): HTMLElement | undefined {
  return [...document.querySelectorAll<HTMLElement>('button, [role="button"], [role="menuitemradio"], [role="option"]')]
    .find(element => element.offsetParent !== null && isAudioDeviceLabel(element.textContent?.trim() || '', name));
}

initialize();
