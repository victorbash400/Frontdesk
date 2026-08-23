import { ChevronLeft, ChevronRight, Columns3, Ellipsis, GalleryHorizontal, LayoutGrid, List, ListFilter, Search, Share, Tag } from "lucide-react";
import type { MouseEvent } from "react";

import type { Destination, SortMode, ViewMode } from "../types/filesystem";
import styles from "./Toolbar.module.css";

const viewModes: Array<{ mode: ViewMode; label: string; icon: typeof LayoutGrid }> = [
  { mode: "icons", label: "Icon view", icon: LayoutGrid },
  { mode: "list", label: "List view", icon: List },
  { mode: "columns", label: "Column view", icon: Columns3 },
  { mode: "gallery", label: "Gallery view", icon: GalleryHorizontal },
];

type ToolbarProps = {
  destination: Destination;
  title: string;
  canGoBack: boolean;
  canGoForward: boolean;
  hasSelection: boolean;
  query: string;
  sort: SortMode;
  viewMode: ViewMode;
  onBack: () => void;
  onForward: () => void;
  onCreate: () => void;
  onInspectorToggle: () => void;
  onShare: () => void;
  onQueryChange: (query: string) => void;
  onSortChange: (sort: SortMode) => void;
  onViewModeChange: (mode: ViewMode) => void;
};

export function Toolbar({ destination, title, canGoBack, canGoForward, hasSelection, query, sort, viewMode, onBack, onForward, onCreate, onInspectorToggle, onShare, onQueryChange, onSortChange, onViewModeChange }: ToolbarProps) {
  const createLabel = destination.type === "location" && destination.location === "clients" ? "New Client" : "New Folder";
  const canCreate = destination.type === "folder" || destination.type === "location" && destination.location === "clients";

  function closeMenu(event: MouseEvent<HTMLButtonElement>) {
    event.currentTarget.closest("details")?.removeAttribute("open");
  }

  return (
    <header className={styles.toolbar}>
      <nav className={styles.history} aria-label="History">
        <button aria-label="Back" disabled={!canGoBack} onClick={onBack} type="button"><ChevronLeft /></button>
        <button aria-label="Forward" disabled={!canGoForward} onClick={onForward} type="button"><ChevronRight /></button>
      </nav>
      <h1>{title}</h1>
      <nav className={styles.tools} aria-label="View and filesystem actions">
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
        <button aria-label="Share" disabled={!hasSelection} onClick={onShare} title="Share" type="button"><Share /></button>
        <button aria-label="Tags" disabled={!hasSelection} onClick={onInspectorToggle} title="Tags" type="button"><Tag /></button>
        <details className={styles.more}>
          <summary aria-label="More" title="More"><Ellipsis /></summary>
          <menu>
            {canCreate ? <button onClick={(event) => { closeMenu(event); onCreate(); }} type="button">{createLabel}</button> : null}
            {hasSelection ? <button onClick={(event) => { closeMenu(event); onInspectorToggle(); }} type="button">Get Info</button> : null}
          </menu>
        </details>
        <label className={styles.search}>
          <Search aria-hidden="true" />
          <input aria-label="Search Operator" onChange={(event) => onQueryChange(event.target.value)} placeholder="Search" type="search" value={query} />
        </label>
      </nav>
    </header>
  );
}
