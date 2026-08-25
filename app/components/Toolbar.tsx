import { ChevronLeft, ChevronRight, Ellipsis, LayoutGrid, List, ListFilter, Search, Share, Tag } from "lucide-react";
import type { MouseEvent } from "react";

import type { BreadcrumbItem, Destination, SortMode, ViewMode } from "../types/filesystem";
import { Breadcrumbs } from "./Breadcrumbs";
import { ClientAssistantActions } from "./ClientAssistantActions";
import styles from "./Toolbar.module.css";

const viewModes: Array<{ mode: ViewMode; label: string; icon: typeof LayoutGrid }> = [
  { mode: "grid", label: "Grid view", icon: LayoutGrid },
  { mode: "list", label: "List view", icon: List },
];

type ToolbarProps = {
  destination: Destination;
  breadcrumbs: BreadcrumbItem[];
  canGoBack: boolean;
  canGoForward: boolean;
  hasSelection: boolean;
  chatAvailable: boolean;
  chatOpen: boolean;
  clientId?: string;
  voiceOpen: boolean;
  query: string;
  sort: SortMode;
  viewMode: ViewMode;
  utilityView?: boolean;
  onBack: () => void;
  onBreadcrumbNavigate: (destination: Destination) => void;
  onForward: () => void;
  onCreateClient: () => void;
  onCreateFolder: () => void;
  onChatToggle: () => void;
  onVoiceToggle: () => void;
  onInspectorToggle: () => void;
  onShare: () => void;
  onQueryChange: (query: string) => void;
  onSortChange: (sort: SortMode) => void;
  onViewModeChange: (mode: ViewMode) => void;
};

export function Toolbar({ destination, breadcrumbs, canGoBack, canGoForward, hasSelection, chatAvailable, chatOpen, clientId, query, sort, viewMode, voiceOpen, utilityView = false, onBack, onBreadcrumbNavigate, onForward, onCreateClient, onCreateFolder, onChatToggle, onVoiceToggle, onInspectorToggle, onShare, onQueryChange, onSortChange, onViewModeChange }: ToolbarProps) {
  const canCreateFolder = destination.type === "folder";

  function closeMenu(event: MouseEvent<HTMLButtonElement>) {
    event.currentTarget.closest("details")?.removeAttribute("open");
  }

  return (
    <header className={styles.toolbar}>
      <nav className={styles.history} aria-label="History">
        <button aria-label="Back" disabled={!canGoBack} onClick={onBack} type="button"><ChevronLeft /></button>
        <button aria-label="Forward" disabled={!canGoForward} onClick={onForward} type="button"><ChevronRight /></button>
      </nav>
      <Breadcrumbs className={styles.path} items={breadcrumbs} onNavigate={onBreadcrumbNavigate} />
      {!utilityView ? <label className={styles.search}>
        <Search aria-hidden="true" />
        <input aria-label="Search Front Desk" onChange={(event) => onQueryChange(event.target.value)} placeholder="Search" type="search" value={query} />
      </label> : null}
      {!utilityView ? <nav className={styles.tools} aria-label="View and filesystem actions">
        <span className={styles.viewModes}>
          {viewModes.map(({ mode, label, icon: Icon }) => (
            <button aria-label={label} aria-pressed={viewMode === mode} key={mode} onClick={() => onViewModeChange(mode)} title={label} type="button"><Icon /></button>
          ))}
        </span>
        <label className={styles.sort} title="Sort items">
          <ListFilter aria-hidden="true" />
          <select aria-label="Sort items" onChange={(event) => onSortChange(event.target.value as SortMode)} value={sort}>
            <option value="name-asc">Name</option>
            <option value="name-desc">Name, reverse</option>
            <option value="date-desc">Newest</option>
            <option value="date-asc">Oldest</option>
          </select>
        </label>
        <span className={styles.actions}>
          <button aria-label="Share" disabled={!hasSelection} onClick={onShare} title="Share" type="button"><Share /></button>
          <button aria-label="Tags" disabled={!hasSelection} onClick={onInspectorToggle} title="Tags" type="button"><Tag /></button>
          <details className={styles.more}>
            <summary aria-label="More" title="More"><Ellipsis /></summary>
            <menu>
              {canCreateFolder ? <button onClick={(event) => { closeMenu(event); onCreateFolder(); }} type="button">New Folder</button> : null}
              {!canCreateFolder ? <button onClick={(event) => { closeMenu(event); onCreateClient(); }} type="button">New Client</button> : null}
              {hasSelection ? <button onClick={(event) => { closeMenu(event); onInspectorToggle(); }} type="button">Get Info</button> : null}
            </menu>
          </details>
        </span>
        {chatAvailable && clientId ? <ClientAssistantActions chatOpen={chatOpen} clientId={clientId} onChatToggle={onChatToggle} onVoiceToggle={onVoiceToggle} voiceOpen={voiceOpen} /> : null}
      </nav> : null}
    </header>
  );
}
