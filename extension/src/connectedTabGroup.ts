/**
 * Derived from Microsoft Playwright's browser extension under Apache-2.0.
 * Front Desk connects every debuggable tab instead of limiting a client to a
 * manually managed Chrome tab group.
 */

import { RelayConnection, debugLog } from './relayConnection';

const NON_DEBUGGABLE_SCHEMES = ['chrome:', 'chrome-extension:', 'edge:', 'devtools:'];
const CONNECTED_BADGE = { text: 'FD', color: '#20201e', title: 'Controlled by Front Desk' };

export function isNonDebuggableUrl(url: string | undefined): boolean {
  return !url || NON_DEBUGGABLE_SCHEMES.some(scheme => url.startsWith(scheme));
}

export class ConnectedBrowser {
  readonly clientName: string | undefined;
  private _connection: RelayConnection;
  private _knownTabIds = new Set<number>();
  private _onTabCreatedListener: (tab: chrome.tabs.Tab) => void;
  private _onTabUpdatedListener: (tabId: number, changeInfo: chrome.tabs.OnUpdatedInfo, tab: chrome.tabs.Tab) => void;
  private _onTabRemovedListener: (tabId: number) => void;

  onclose?: () => void;

  constructor(connection: RelayConnection, clientName: string | undefined) {
    this.clientName = clientName;
    this._connection = connection;
    this._connection.onclose = () => this._onConnectionClose();
    this._connection.ontabattached = tabId => void this._onTabAttached(tabId);
    this._connection.ontabdetached = tabId => void this._clearBadge(tabId);
    this._onTabCreatedListener = tab => void this._trackAndAttach(tab);
    this._onTabUpdatedListener = (tabId, changeInfo, tab) => {
      if (changeInfo.url !== undefined)
        void this._trackAndAttach(tab);
      if (this._connection.attachedTabs.has(tabId))
        void this._setBadge(tabId);
    };
    this._onTabRemovedListener = tabId => this._knownTabIds.delete(tabId);
    chrome.tabs.onCreated.addListener(this._onTabCreatedListener);
    chrome.tabs.onUpdated.addListener(this._onTabUpdatedListener);
    chrome.tabs.onRemoved.addListener(this._onTabRemovedListener);
  }

  async initialize(selectedTab: chrome.tabs.Tab): Promise<void> {
    await this._trackAndAttach(selectedTab);
    this._connection.didInitialize();
  }

  connectedTabIds(): number[] {
    return [...this._connection.attachedTabs];
  }

  close(reason: string): void {
    this._connection.close(reason);
  }

  releaseTab(tabId: number): void {
    this._knownTabIds.delete(tabId);
    this._connection.detachTab(tabId);
  }

  private async _trackAndAttach(tab: chrome.tabs.Tab): Promise<void> {
    if (tab.id === undefined || isNonDebuggableUrl(tab.url))
      return;
    this._knownTabIds.add(tab.id);
    this._connection.attachTab(tab);
  }

  private async _onTabAttached(tabId: number): Promise<void> {
    this._knownTabIds.add(tabId);
    await this._setBadge(tabId);
  }

  private async _setBadge(tabId: number): Promise<void> {
    try {
      await Promise.all([
        chrome.action.setBadgeText({ tabId, text: CONNECTED_BADGE.text }),
        chrome.action.setBadgeBackgroundColor({ tabId, color: CONNECTED_BADGE.color }),
        chrome.action.setTitle({ tabId, title: CONNECTED_BADGE.title }),
      ]);
    } catch (error: any) {
      debugLog(`Could not update tab ${tabId} badge:`, error.message);
    }
  }

  private async _clearBadge(tabId: number): Promise<void> {
    try {
      await chrome.action.setBadgeText({ tabId, text: '' });
    } catch {
      // The tab may already be closed.
    }
  }

  private _onConnectionClose(): void {
    chrome.tabs.onCreated.removeListener(this._onTabCreatedListener);
    chrome.tabs.onUpdated.removeListener(this._onTabUpdatedListener);
    chrome.tabs.onRemoved.removeListener(this._onTabRemovedListener);
    for (const tabId of this._knownTabIds)
      void this._clearBadge(tabId);
    this._knownTabIds.clear();
    this.onclose?.();
  }
}
