type MeetWorkerConfig = { meetingId: string; runtimeId: string; bridgeId: string; socketUrl: string };

export {};

const PREFIX = '#front-desk-meet=';
const encoded = location.hash.startsWith(PREFIX) ? location.hash.slice(PREFIX.length) : sessionStorage.getItem('frontDeskMeetWorker');

if (encoded) {
  sessionStorage.setItem('frontDeskMeetWorker', encoded);
  try {
    const normalized = encoded.replace(/-/g, '+').replace(/_/g, '/');
    const decoded = Uint8Array.from(atob(normalized + '='.repeat((4 - normalized.length % 4) % 4)), character => character.charCodeAt(0));
    const config = JSON.parse(new TextDecoder().decode(decoded)) as MeetWorkerConfig;
    const relay = ensureRelayElement();
    const port = chrome.runtime.connect({ name: 'front-desk-meet' });
    let reconnectAttempt = 0;
    let intentionallyClosed = false;
    let reconnectTimer: number | undefined;
    const emit = (message: object) => {
      relay.setAttribute('data-incoming', JSON.stringify(message));
      document.dispatchEvent(new Event('front-desk-meet-incoming'));
    };
    port.onMessage.addListener(message => {
      relay.setAttribute('data-last-message', JSON.stringify(message));
      emit(message);
      if (message.kind === 'open')
        reconnectAttempt = 0;
      const retryableClose = message.code === 1001 || message.code === 1006 || message.code === 1011 || message.code === 1012 || message.code === 1013;
      if (message.kind === 'close' && !intentionallyClosed && retryableClose) {
        const delay = Math.min(30_000, 500 * 2 ** reconnectAttempt++);
        reconnectTimer = window.setTimeout(() => {
          reconnectTimer = undefined;
          if (!intentionallyClosed)
            port.postMessage({ kind: 'connect', url: config.socketUrl, meetingId: config.meetingId, runtimeId: config.runtimeId, bridgeId: config.bridgeId });
        }, delay);
      }
    });
    if (!config.meetingId || !config.runtimeId || !config.bridgeId || !config.socketUrl)
      throw new Error('Meet worker identity is incomplete.');
    port.postMessage({ kind: 'connect', url: config.socketUrl, meetingId: config.meetingId, runtimeId: config.runtimeId, bridgeId: config.bridgeId });
    document.addEventListener('front-desk-meet-outgoing', () => {
      const raw = relay.getAttribute('data-outgoing');
      if (!raw)
        return;
      const message = JSON.parse(raw) as { kind: string; text?: string; binary?: string; code?: number; reason?: string };
      if (message.kind === 'close')
        intentionallyClosed = true;
      port.postMessage(message);
    });
    window.addEventListener('pagehide', () => {
      intentionallyClosed = true;
      if (reconnectTimer !== undefined)
        window.clearTimeout(reconnectTimer);
      port.postMessage({ kind: 'close', code: 1000, reason: 'Meet page closed' });
      port.disconnect();
    }, { once: true });
  } catch (error) {
    console.error('[Front Desk Meet Relay]', error);
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
