/**
 * Derived from Microsoft Playwright's browser extension under Apache-2.0.
 * Front Desk keeps the selected tab and Playwright-created tabs in one visible
 * Chrome group owned by the active browser session.
 */

import { RelayConnection, debugLog } from './relayConnection';

const NON_DEBUGGABLE_SCHEMES = ['chrome:', 'chrome-extension:', 'edge:', 'devtools:'];
const CONNECTED_BADGE = { text: 'FD', color: '#20201e', title: 'Controlled by Front Desk' };
const GROUP_TITLE = 'Front Desk';

export function isNonDebuggableUrl(url: string | undefined): boolean {
  return !url || NON_DEBUGGABLE_SCHEMES.some(scheme => url.startsWith(scheme));
}

export class ConnectedBrowser {
  readonly clientName: string | undefined;
  private _connection: RelayConnection;
  private _knownTabIds = new Set<number>();
  private _onTabUpdatedListener: (tabId: number, changeInfo: chrome.tabs.OnUpdatedInfo, tab: chrome.tabs.Tab) => void;
  private _onTabRemovedListener: (tabId: number) => void;
  private _groupId?: number;
  private _windowId?: number;
  private _returnTabId?: number;

  onclose?: () => void;

  constructor(connection: RelayConnection, clientName: string | undefined, returnTabId: number | undefined) {
    this.clientName = clientName;
    this._connection = connection;
    this._returnTabId = returnTabId;
    this._connection.onclose = () => this._onConnectionClose();
    this._connection.ontabattached = tabId => void this._onTabAttached(tabId);
    this._connection.ontabdetached = tabId => void this._clearBadge(tabId);
    this._onTabUpdatedListener = (tabId, changeInfo, tab) => {
      if (this._connection.attachedTabs.has(tabId))
        void this._setBadge(tabId);
    };
    this._onTabRemovedListener = tabId => this._knownTabIds.delete(tabId);
    chrome.tabs.onUpdated.addListener(this._onTabUpdatedListener);
    chrome.tabs.onRemoved.addListener(this._onTabRemovedListener);
  }

  async initialize(selectedTab: chrome.tabs.Tab): Promise<void> {
    if (selectedTab.windowId === undefined)
      throw new Error('The selected browser tab has no Chrome window.');
    this._windowId = selectedTab.windowId;
    this._connection.setPreferredWindowId(selectedTab.windowId);
    this._connection.setBootstrapTab(selectedTab);
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
    await Promise.all([this._setBadge(tabId), this._addToGroup(tabId), this._injectOverlay(tabId)]);
    await chrome.tabs.sendMessage(tabId, {
      type: 'frontDeskBrowserAction',
      kind: 'navigate',
      label: 'Front Desk is working',
    }).catch(() => {});
  }

  private async _injectOverlay(tabId: number): Promise<void> {
    try {
      await chrome.scripting.executeScript({ target: { tabId }, files: ['lib/content.js'] });
    } catch {
      // Chrome-owned and protected pages cannot host the visual overlay.
    }
  }

  private async _addToGroup(tabId: number): Promise<void> {
    try {
      const tab = await chrome.tabs.get(tabId);
      if (this._windowId !== undefined && tab.windowId !== this._windowId)
        await chrome.tabs.move(tabId, { windowId: this._windowId, index: -1 });
      const groupId = await chrome.tabs.group(this._groupId === undefined ? { tabIds: tabId } : { groupId: this._groupId, tabIds: tabId });
      this._groupId = groupId;
      await chrome.tabGroups.update(groupId, { color: 'green', collapsed: false, title: GROUP_TITLE });
    } catch (error: any) {
      debugLog(`Could not group tab ${tabId}:`, error.message);
    }
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
    chrome.tabs.onUpdated.removeListener(this._onTabUpdatedListener);
    chrome.tabs.onRemoved.removeListener(this._onTabRemovedListener);
    for (const tabId of this._knownTabIds)
      void this._clearBadge(tabId);
    for (const tabId of this._knownTabIds)
      void chrome.tabs.sendMessage(tabId, { type: 'frontDeskBrowserOverlayHide' }).catch(() => {});
    if (this._knownTabIds.size) {
      const [firstTabId, ...remainingTabIds] = this._knownTabIds;
      void chrome.tabs.ungroup([firstTabId, ...remainingTabIds]).catch(() => {});
    }
    this._knownTabIds.clear();
    if (this._returnTabId !== undefined)
      void this._restoreReturnTab(this._returnTabId);
    this.onclose?.();
  }

  private async _restoreReturnTab(tabId: number): Promise<void> {
    try {
      const tab = await chrome.tabs.update(tabId, { active: true });
      if (!tab)
        return;
      await chrome.windows.update(tab.windowId, { focused: true });
    } catch {
      // The Front Desk tab may have been closed while the run was active.
    }
  }
}
