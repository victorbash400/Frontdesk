type MeetWorkerConfig = { meetingId: string; runtimeId: string; bridgeId: string; socketUrl: string };
type RelayMessage = { kind: string; text?: string; binary?: string; code?: number; reason?: string; tabId?: number };

export {};

const PREFIX = '#front-desk-meet=';
const encoded = location.hash.startsWith(PREFIX) ? location.hash.slice(PREFIX.length) : sessionStorage.getItem('frontDeskMeetWorker');

if (encoded)
  void startRelay(encoded);

async function startRelay(encodedConfig: string): Promise<void> {
  sessionStorage.setItem('frontDeskMeetWorker', encodedConfig);
  try {
    const normalized = encodedConfig.replace(/-/g, '+').replace(/_/g, '/');
    const decoded = Uint8Array.from(atob(normalized + '='.repeat((4 - normalized.length % 4) % 4)), character => character.charCodeAt(0));
    const config = JSON.parse(new TextDecoder().decode(decoded)) as MeetWorkerConfig;
    if (!config.meetingId || !config.runtimeId || !config.bridgeId || !config.socketUrl)
      throw new Error('Meet worker identity is incomplete.');

    const registration = await chrome.runtime.sendMessage({
      type: 'registerMeetRelay',
      meetingId: config.meetingId,
      runtimeId: config.runtimeId,
      bridgeId: config.bridgeId,
    }) as { accepted?: boolean; reason?: string; tabId?: number; localPlaybackMuted?: boolean } | undefined;
    const relay = ensureRelayElement();
    if (!registration?.accepted) {
      emit(relay, { kind: 'rejected', reason: registration?.reason || 'Meet relay registration failed.' });
      return;
    }
    const identity = { meetingId: config.meetingId, runtimeId: config.runtimeId, bridgeId: config.bridgeId, tabId: registration.tabId };
    chrome.runtime.onMessage.addListener(message => {
      if (message.type !== 'meetRelayIncoming' || message.runtimeId !== config.runtimeId)
        return;
      const incoming = message.message as RelayMessage;
      emit(relay, incoming);
      if (incoming.kind === 'open') {
        void chrome.runtime.sendMessage({
          type: 'meetRelayOutgoing',
          ...identity,
          message: {
            kind: 'message',
            text: JSON.stringify({
              type: 'diagnostic',
              stage: 'playback.tab_audio_available',
              details: { tabId: registration.tabId, muted: registration.localPlaybackMuted === true },
            }),
          },
        });
      }
    });
    document.addEventListener('front-desk-meet-outgoing', () => {
      const raw = relay.getAttribute('data-outgoing');
      if (raw)
        void chrome.runtime.sendMessage({ type: 'meetRelayOutgoing', ...identity, message: JSON.parse(raw) });
    });
    window.addEventListener('pagehide', () => {
      void chrome.runtime.sendMessage({
        type: 'meetRelayOutgoing',
        ...identity,
        message: { kind: 'close', code: 1000, reason: 'Meet page closed' },
      });
    }, { once: true });
    await chrome.runtime.sendMessage({ type: 'meetRelayConnect', ...identity, socketUrl: config.socketUrl });
  } catch (error) {
    console.error('[Front Desk Meet Relay]', error);
  }
}

function emit(relay: HTMLElement, message: RelayMessage): void {
  relay.setAttribute('data-last-message', JSON.stringify(message));
  relay.setAttribute('data-incoming', JSON.stringify(message));
  document.dispatchEvent(new Event('front-desk-meet-incoming'));
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
