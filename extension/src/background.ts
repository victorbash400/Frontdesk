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
      const selectedTab = await this._initialTab(selectorTabId);
      await browser.initialize(selectedTab);
      await chrome.tabs.remove(selectorTabId).catch(() => {});
    } catch (error: any) {
      debugLog('Failed to connect browser:', error.message);
      throw error;
    }
  }

  private async _initialTab(selectorTabId: number): Promise<chrome.tabs.Tab> {
    const selectorTab = await chrome.tabs.get(selectorTabId);
    return chrome.tabs.create({
      // Playwright cannot navigate an extension-created about:blank target:
      // Chrome treats it as extension-owned and rejects Page.navigate. Start
      // on a normal permitted page so the first browser_navigate can reuse it.
      url: 'https://example.com/',
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
