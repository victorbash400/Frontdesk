/**
 * Copyright (c) Microsoft Corporation.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import { debugLog } from './relayConnection';
import { PendingConnections } from './pendingConnection';
import { ConnectedBrowser, isNonDebuggableUrl } from './connectedTabGroup';
import { relayDecision, validRelayIdentity, type MeetRelayIdentity } from './meetIdentity';

type PageMessage = {
  type: 'connectionRequested';
  mcpRelayUrl: string;
} | {
  type: 'getTabs';
} | {
  type: 'connectToTab';
  // Picked in the connect page; absent on the token-bypass path where no tab
  // selection happens.
  tab?: chrome.tabs.Tab;
  clientName?: string;
} | {
  type: 'getConnectionStatus';
} | {
  type: 'disconnect';
  connectionId: number;
};

class PlaywrightExtension {
  private _connections = new Map<number, ConnectedBrowser>();
  private _lastConnectionId = 0;
  private _pendingConnections = new PendingConnections();
  constructor() {
    chrome.runtime.onMessage.addListener(this._onMessage.bind(this));
    chrome.action.onClicked.addListener(this._onActionClicked.bind(this));
  }

  // Promise-based message handling is not supported in Chrome: https://issues.chromium.org/issues/40753031
  private _onMessage(message: PageMessage, sender: chrome.runtime.MessageSender, sendResponse: (response: any) => void) {
    switch (message.type) {
      case 'connectionRequested': {
        const selectorTabId = sender.tab!.id!;
        this._releaseConnectPage(selectorTabId).then(() => {
          this._pendingConnections.create(selectorTabId, message.mcpRelayUrl);
          sendResponse({ success: true });
        });
        return true;
      }
      case 'getTabs':
        this._getTabs(sender.tab?.id).then(
            tabs => sendResponse({ success: true, tabs, currentTabId: sender.tab?.id }),
            (error: any) => sendResponse({ success: false, error: error.message }));
        return true;
      case 'connectToTab': {
        // Token-bypass (no specific pick) falls back to the connect page itself
        // so `ConnectedTabGroup` always has a concrete tab to start from. Both
        // sender.tab and UI-supplied tabs come from chrome.tabs.query / runtime
        // message sender, where `id` is always defined.
        this._connectBrowser(sender.tab!.id!, message.clientName).then(
            () => sendResponse({ success: true }),
            (error: any) => sendResponse({ success: false, error: error.message }));
        return true; // Return true to indicate that the response will be sent asynchronously
      }
      case 'getConnectionStatus':
        sendResponse({
          connections: [...this._connections].map(([id, group]) => ({
            id,
            clientName: group.clientName,
            connectedTabIds: group.connectedTabIds(),
          })),
        });
        return false;
      case 'disconnect':
        this._connections.get(message.connectionId)?.close('User disconnected');
        sendResponse({ success: true });
        return false;
    }
  }

  private async _connectBrowser(selectorTabId: number, clientName: string | undefined): Promise<void> {
    try {
      const connection = await this._pendingConnections.take(selectorTabId);
      if (!connection)
        throw new Error('Pending client connection closed');

      const id = ++this._lastConnectionId;
      const selectorTab = await chrome.tabs.get(selectorTabId);
      const returnTabId = await this._returnTabId(selectorTab);
      const browser = new ConnectedBrowser(connection, clientName, returnTabId);
      browser.onclose = () => this._connections.delete(id);
      this._connections.set(id, browser);
      const selectedTab = await this._initialTab(selectorTabId, returnTabId);
      await browser.initialize(selectedTab);
      await chrome.tabs.remove(selectorTabId).catch(() => {});
    } catch (error: any) {
      debugLog('Failed to connect browser:', error.message);
      throw error;
    }
  }

  private async _initialTab(selectorTabId: number, returnTabId: number | undefined): Promise<chrome.tabs.Tab> {
    const selectorTab = await chrome.tabs.get(selectorTabId);
    const returnTab = returnTabId === undefined ? undefined : await chrome.tabs.get(returnTabId).catch(() => undefined);
    const frontDeskUrl = returnTab?.url && /^https?:/.test(returnTab.url) ? new URL("/browser-bridge", returnTab.url).toString() : undefined;
    if (!frontDeskUrl)
      throw new Error('Front Desk must be open before Browser Use can connect.');
    return chrome.tabs.create({
      url: frontDeskUrl,
      active: false,
      windowId: selectorTab.windowId,
      index: selectorTab.index + 1,
    });
  }

  private async _returnTabId(selectorTab: chrome.tabs.Tab): Promise<number | undefined> {
    const tabs = await chrome.tabs.query({ windowId: selectorTab.windowId });
    const frontDeskTab = tabs.find(tab => tab.id !== selectorTab.id && (
      tab.title === 'Front Desk'
      || tab.url?.startsWith('http://localhost:3000')
      || tab.url?.startsWith('http://127.0.0.1:3000')
    ));
    return frontDeskTab?.id ?? selectorTab.openerTabId;
  }

  // Chrome may create the connect page inside the active client's group.
  private async _releaseConnectPage(tabId: number): Promise<void> {
    for (const browser of this._connections.values()) {
      if (browser.connectedTabIds().includes(tabId)) {
        browser.releaseTab(tabId);
        return;
      }
    }
  }

  private async _getTabs(selectorTabId: number | undefined): Promise<chrome.tabs.Tab[]> {
    const tabs = await chrome.tabs.query({});
    const connectedTabIds = this._connectedTabIds();
    return tabs.filter(tab => !isNonDebuggableUrl(tab.url) && (tab.id === selectorTabId || !connectedTabIds.has(tab.id!)));
  }

  private _connectedTabIds(): Set<number> {
    return new Set([...this._connections.values()].flatMap(group => group.connectedTabIds()));
  }

  private async _onActionClicked(): Promise<void> {
    await chrome.tabs.create({
      url: chrome.runtime.getURL('status.html'),
      active: true
    });
  }
}

new PlaywrightExtension();

type ActiveMeetRelay = MeetRelayIdentity & { port: chrome.runtime.Port; socket: WebSocket };
const meetRelays = new Map<string, ActiveMeetRelay>();
chrome.tabs.onRemoved.addListener(tabId => {
  for (const [meetingId, relay] of meetRelays) {
    if (relay.tabId !== tabId)
      continue;
    relay.socket.close(1000, 'Meet tab closed');
    meetRelays.delete(meetingId);
  }
});

chrome.runtime.onConnect.addListener(port => {
  if (port.name !== 'front-desk-meet')
    return;
  const tabId = port.sender?.tab?.id;
  let socket: WebSocket | undefined;
  port.onMessage.addListener(message => {
    if (message.kind === 'connect' && typeof message.url === 'string') {
      const identity = { meetingId: message.meetingId, runtimeId: message.runtimeId, bridgeId: message.bridgeId, tabId };
      if (!validRelayIdentity(identity)) {
        port.postMessage({ kind: 'rejected', reason: 'Meet relay identity is incomplete.' });
        return;
      }
      const current = meetRelays.get(identity.meetingId);
      if (current) {
        const decision = relayDecision(current, identity);
        if (decision === 'reject-duplicate-tab') {
          port.postMessage({ kind: 'rejected', reason: 'This meeting runtime already owns another Chrome tab.' });
          void chrome.tabs.remove(identity.tabId);
          return;
        }
        current.socket.close(4001, decision === 'replace-runtime' ? 'Meeting runtime replaced' : 'Bridge transport replaced');
        if (decision === 'replace-runtime')
          void chrome.tabs.remove(current.tabId);
      }
      socket?.close(4001, 'Bridge transport replaced');
      const relaySocket = new WebSocket(message.url);
      socket = relaySocket;
      const relay: ActiveMeetRelay = { ...identity, port, socket: relaySocket };
      meetRelays.set(identity.meetingId, relay);
      relaySocket.binaryType = 'arraybuffer';
      relaySocket.addEventListener('open', () => {
        if (meetRelays.get(identity.meetingId)?.socket !== relaySocket)
          return;
        relaySocket.send(JSON.stringify({ type: 'bridge_registered', ...identity, tabId: String(identity.tabId) }));
        port.postMessage({ kind: 'open', tabId: identity.tabId });
      });
      relaySocket.addEventListener('message', event => {
        if (meetRelays.get(identity.meetingId)?.socket !== relaySocket)
          return;
        if (event.data instanceof ArrayBuffer)
          port.postMessage({ kind: 'message', binary: bytesToBase64(new Uint8Array(event.data)) });
        else
          port.postMessage({ kind: 'message', text: String(event.data) });
      });
      relaySocket.addEventListener('close', event => {
        if (meetRelays.get(identity.meetingId)?.socket !== relaySocket)
          return;
        meetRelays.delete(identity.meetingId);
        port.postMessage({ kind: 'close', code: event.code, reason: event.reason });
      });
      return;
    }
    if (message.kind === 'close') {
      socket?.close(message.code, message.reason);
      if (tabId !== undefined && message.reason === 'Meeting complete')
        void chrome.tabs.remove(tabId);
      return;
    }
    if (message.kind === 'message' && socket?.readyState === WebSocket.OPEN) {
      if (message.binary) {
        const bytes = base64ToBytes(message.binary);
        socket.send(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer);
      } else {
        socket.send(message.text || '');
      }
    }
  });
  port.onDisconnect.addListener(() => {
    socket?.close(1000, 'Meet tab closed');
    for (const [meetingId, relay] of meetRelays) {
      if (relay.socket === socket)
        meetRelays.delete(meetingId);
    }
  });
});

function bytesToBase64(bytes: Uint8Array): string {
  let binary = '';
  for (const byte of bytes)
    binary += String.fromCharCode(byte);
  return btoa(binary);
}

function base64ToBytes(value: string): Uint8Array {
  return Uint8Array.from(atob(value), character => character.charCodeAt(0));
}
