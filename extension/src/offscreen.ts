type RelayIdentity = { meetingId: string; runtimeId: string; bridgeId: string; tabId: number };
type RelayMessage = { kind: string; text?: string; binary?: string; code?: number; reason?: string };
type ActiveRelay = RelayIdentity & { socket: WebSocket; socketUrl: string; intentionallyClosed: boolean; reconnectAttempt: number };

let active: ActiveRelay | undefined;

chrome.runtime.onMessage.addListener(message => {
  if (message.type === 'meetRelayConnect') {
    connect(message as RelayIdentity & { socketUrl: string });
    return;
  }
  if (message.type !== 'meetRelayOutgoing' || !active || message.runtimeId !== active.runtimeId)
    return;
  const outgoing = message.message as RelayMessage;
  if (outgoing.kind === 'close') {
    active.intentionallyClosed = true;
    active.socket.close(outgoing.code, outgoing.reason);
    return;
  }
  if (outgoing.kind !== 'message' || active.socket.readyState !== WebSocket.OPEN)
    return;
  if (outgoing.binary) {
    const bytes = base64ToBytes(outgoing.binary);
    active.socket.send(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer);
  } else {
    active.socket.send(outgoing.text || '');
  }
});

function connect(config: RelayIdentity & { socketUrl: string }): void {
  if (active)
    active.socket.close(4001, 'Meeting runtime replaced');
  open({ ...config, socket: undefined as never, intentionallyClosed: false, reconnectAttempt: 0 });
}

function open(relay: ActiveRelay): void {
  const socket = new WebSocket(relay.socketUrl);
  active = { ...relay, socket };
  socket.binaryType = 'arraybuffer';
  socket.addEventListener('open', () => {
    if (active?.socket !== socket)
      return;
    active.reconnectAttempt = 0;
    socket.send(JSON.stringify({ type: 'bridge_registered', meetingId: relay.meetingId, runtimeId: relay.runtimeId, bridgeId: relay.bridgeId, tabId: String(relay.tabId) }));
    socket.send(JSON.stringify({ type: 'diagnostic', stage: 'relay.offscreen_connected', details: { tabId: relay.tabId } }));
    sendIncoming(relay, { kind: 'open', tabId: relay.tabId });
  });
  socket.addEventListener('message', event => {
    if (active?.socket !== socket)
      return;
    sendIncoming(relay, event.data instanceof ArrayBuffer
      ? { kind: 'message', binary: bytesToBase64(new Uint8Array(event.data)) }
      : { kind: 'message', text: String(event.data) });
  });
  socket.addEventListener('close', event => {
    if (active?.socket !== socket)
      return;
    sendIncoming(relay, { kind: 'close', code: event.code, reason: event.reason });
    if (active.intentionallyClosed)
      return;
    const retryable = event.code === 1001 || event.code === 1006 || event.code === 1011 || event.code === 1012 || event.code === 1013;
    if (!retryable)
      return;
    const delay = Math.min(30_000, 500 * 2 ** active.reconnectAttempt++);
    const next = active;
    window.setTimeout(() => {
      if (active === next)
        open(next);
    }, delay);
  });
}

function sendIncoming(identity: RelayIdentity, message: RelayMessage & { tabId?: number }): void {
  void chrome.runtime.sendMessage({ type: 'meetRelayIncoming', runtimeId: identity.runtimeId, tabId: identity.tabId, message });
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
