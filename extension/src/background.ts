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

import { debugLog, RelayConnection } from './relayConnection';
import { PendingConnections } from './pendingConnection';
import { cloudAppOrigins, isAppOrigin, isCloudRelay } from './cloudConfig';
import { ConnectedBrowser, isNonDebuggableUrl } from './connectedTabGroup';
import { relayDecision, validRelayIdentity, type MeetRelayIdentity } from './meetIdentity';

type PageMessage = {
  type: 'openCloudConnection';
  relayUrl: string;
} | {
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
} | {
  type: 'registerMeetRelay';
  meetingId: string;
  runtimeId: string;
  bridgeId: string;
} | {
  type: 'meetRelayIncoming';
  runtimeId: string;
  tabId: number;
  message: object;
} | {
  type: 'closeMeetTab';
  meetingId: string;
  runtimeId: string;
  bridgeId: string;
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
      case 'openCloudConnection': {
        if (!sender.tab?.url || !isAppOrigin(new URL(sender.tab.url).origin) || !isCloudRelay(message.relayUrl)) {
          sendResponse({ success: false, error: 'Untrusted cloud browser connection.' });
          return false;
        }
        const url = new URL(chrome.runtime.getURL('connect.html'));
        url.searchParams.set('mcpRelayUrl', message.relayUrl);
        url.searchParams.set('client', JSON.stringify({ name: 'Front Desk Cloud' }));
        url.searchParams.set('protocolVersion', '2');
        chrome.tabs.create({ url: url.toString(), openerTabId: sender.tab.id, windowId: sender.tab.windowId })
          .then(() => sendResponse({ success: true }), error => sendResponse({ success: false, error: String(error) }));
        return true;
      }
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
      case 'registerMeetRelay':
        if (sender.tab?.id === undefined) {
          sendResponse({ accepted: false, reason: 'Meet relay tab identity is missing.' });
          return false;
        }
        void registerMeetRelay({
          meetingId: message.meetingId,
          runtimeId: message.runtimeId,
          bridgeId: message.bridgeId,
          tabId: sender.tab.id,
        }).then(sendResponse);
        return true;
      case 'meetRelayIncoming':
        void chrome.tabs.sendMessage(message.tabId, message);
        return false;
      case 'closeMeetTab':
        if (sender.tab?.id === undefined) {
          sendResponse({ success: false });
          return false;
        }
        void closeMeetTab({
          meetingId: message.meetingId,
          runtimeId: message.runtimeId,
          bridgeId: message.bridgeId,
          tabId: sender.tab.id,
        }).then(() => sendResponse({ success: true }));
        return true;
    }
  }

  private async _connectBrowser(selectorTabId: number, clientName: string | undefined): Promise<void> {
    let connection: RelayConnection | undefined;
    try {
      connection = await this._pendingConnections.take(selectorTabId);
      if (!connection)
        throw new Error('Pending client connection closed');

      const id = ++this._lastConnectionId;
      const selectorTab = await chrome.tabs.get(selectorTabId);
      const returnTabId = await this._returnTabId(selectorTab);
      const browser = new ConnectedBrowser(connection, clientName, returnTabId);
      browser.onclose = () => this._connections.delete(id);
      this._connections.set(id, browser);
      const { tab, url } = await this._initialTab(selectorTabId, returnTabId);
      await browser.initialize(tab, url);
      await chrome.tabs.remove(selectorTabId).catch(() => {});
    } catch (error: any) {
      debugLog('Failed to connect browser:', error.message);
      connection?.close(error.message || 'Browser initialization failed');
      throw error;
    }
  }

  private async _initialTab(selectorTabId: number, returnTabId: number | undefined): Promise<{ tab: chrome.tabs.Tab; url: string }> {
    const selectorTab = await chrome.tabs.get(selectorTabId);
    const returnTab = returnTabId === undefined ? undefined : await chrome.tabs.get(returnTabId).catch(() => undefined);
    const frontDeskUrl = returnTab?.url && /^https?:/.test(returnTab.url) ? new URL("/browser-bridge", returnTab.url).toString() : undefined;
    if (!frontDeskUrl)
      throw new Error('Front Desk must be open before Browser Use can connect.');
    const tab = await chrome.tabs.create({
      url: frontDeskUrl,
      active: false,
      windowId: returnTab!.windowId,
      index: returnTab!.index + 1,
    });
    return { tab, url: frontDeskUrl };
  }

  private async _returnTabId(selectorTab: chrome.tabs.Tab): Promise<number | undefined> {
    const tabs = await chrome.tabs.query({});
    const frontDeskTab = tabs.find(tab => tab.id !== selectorTab.id && (
      tab.title === 'Front Desk'
      || cloudAppOrigins.some((origin: string) => tab.url?.startsWith(origin))
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

const ACTIVE_MEET_RELAY_KEY = 'frontDeskActiveMeetRelay';

chrome.tabs.onRemoved.addListener(tabId => {
  void chrome.storage.local.get(ACTIVE_MEET_RELAY_KEY).then(result => {
    const stored = result[ACTIVE_MEET_RELAY_KEY] as MeetRelayIdentity | undefined;
    if (stored?.tabId === tabId)
      return chrome.storage.local.remove(ACTIVE_MEET_RELAY_KEY);
  });
});

async function closeMeetTab(identity: MeetRelayIdentity): Promise<void> {
  const result = await chrome.storage.local.get(ACTIVE_MEET_RELAY_KEY);
  const active = result[ACTIVE_MEET_RELAY_KEY] as MeetRelayIdentity | undefined;
  if (!active || relayDecision(active, identity) !== 'same-tab')
    return;
  await chrome.storage.local.remove(ACTIVE_MEET_RELAY_KEY);
  await chrome.tabs.remove(identity.tabId).catch(() => {});
}

async function registerMeetRelay(identity: MeetRelayIdentity): Promise<{ accepted: boolean; reason?: string; tabId?: number; localPlaybackMuted?: boolean }> {
  if (!validRelayIdentity(identity))
    return { accepted: false, reason: 'Meet relay identity is incomplete.' };
  const stored = (await chrome.storage.local.get(ACTIVE_MEET_RELAY_KEY))[ACTIVE_MEET_RELAY_KEY] as MeetRelayIdentity | undefined;
  if (stored) {
    const decision = relayDecision(stored, identity);
    if (decision === 'reject-duplicate-tab') {
      await chrome.tabs.remove(identity.tabId).catch(() => {});
      return { accepted: false, reason: 'This meeting runtime already owns another Chrome tab.' };
    }
    if (stored.tabId !== identity.tabId)
      await chrome.tabs.remove(stored.tabId).catch(() => {});
  }
  await chrome.storage.local.set({ [ACTIVE_MEET_RELAY_KEY]: identity });
  await chrome.tabs.update(identity.tabId, { muted: false });
  await ensureMeetTransport();
  return { accepted: true, tabId: identity.tabId, localPlaybackMuted: false };
}

async function ensureMeetTransport(): Promise<void> {
  if (await chrome.offscreen.hasDocument())
    return;
  await chrome.offscreen.createDocument({
    url: 'offscreen.html',
    reasons: [chrome.offscreen.Reason.WORKERS],
    justification: 'Keep the identified Google Meet media WebSocket alive while the meeting is silent.',
  });
}
