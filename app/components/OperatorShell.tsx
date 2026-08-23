"use client";

import { useDeferredValue, useMemo, useState, type KeyboardEvent, type MouseEvent } from "react";

import { useFileSystem } from "../hooks/useFileSystem";
import { useNavigationHistory } from "../hooks/useNavigationHistory";
import { destinationTitle, isContainer, nodesForDestination, sortNodes } from "../lib/fileSystemSelectors";
import { tagColors, type FileSystemNode, type SortMode, type ViewMode } from "../types/filesystem";
import { CreateItemDialog } from "./CreateItemDialog";
import { ExplorerContent } from "./ExplorerContent";
import { Inspector } from "./Inspector";
import { ItemContextMenu, type ContextMenuState } from "./ItemContextMenu";
import { Sidebar } from "./Sidebar";
import { Toolbar } from "./Toolbar";
import styles from "./OperatorShell.module.css";

type DialogState = { mode: "create-client" | "create-folder" | "rename"; node?: FileSystemNode };

export function OperatorShell() {
  const fileSystem = useFileSystem();
  const navigation = useNavigationHistory();
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<string>();
  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [sort, setSort] = useState<SortMode>("name-asc");
  const [query, setQuery] = useState("");
  const [dialog, setDialog] = useState<DialogState>();
  const [contextMenu, setContextMenu] = useState<ContextMenuState>();
  const deferredQuery = useDeferredValue(query.trim().toLocaleLowerCase());

  const visibleNodes = useMemo(() => {
    const scoped = nodesForDestination(fileSystem.data.nodes, navigation.destination);
    const filtered = deferredQuery ? scoped.filter((node) => node.name.toLocaleLowerCase().includes(deferredQuery)) : scoped;
    return sortNodes(filtered, sort);
  }, [deferredQuery, fileSystem.data.nodes, navigation.destination, sort]);

  const selectedNode = visibleNodes.find((node) => node.id === selectedId);
  const title = destinationTitle(fileSystem.data.nodes, navigation.destination);
  const canCreate = navigation.destination.type === "folder" || navigation.destination.type === "location" && navigation.destination.location === "clients";

  function navigate(destination: Parameters<typeof navigation.navigate>[0]) {
    navigation.navigate(destination);
    setSelectedId(undefined);
    setContextMenu(undefined);
  }

  function openNode(node: FileSystemNode) {
    if (isContainer(node)) navigate({ type: "folder", id: node.id });
    else {
      setSelectedId(node.id);
      setInspectorOpen(true);
    }
  }

  function createItem(name: string, mode: "create-client" | "create-folder") {
    const parentId = mode === "create-folder" && navigation.destination.type === "folder" ? navigation.destination.id : null;
    const node = fileSystem.createNode(name, mode === "create-client" ? "client" : "folder", parentId);
    setDialog(undefined);
    setSelectedId(node.id);
  }

  function submitDialog(name: string) {
    if (dialog?.mode === "rename" && dialog.node) {
      fileSystem.updateNode(dialog.node.id, { name });
      setDialog(undefined);
      setContextMenu(undefined);
      return;
    }
    if (dialog?.mode === "create-client" || dialog?.mode === "create-folder") createItem(name, dialog.mode);
  }

  function showContextMenu(event: MouseEvent, node: FileSystemNode) {
    event.preventDefault();
    setSelectedId(node.id);
    setContextMenu({ x: event.clientX, y: event.clientY, node });
  }

  function handleKeyboard(event: KeyboardEvent<HTMLElement>) {
    const target = event.target as HTMLElement;
    if (target.matches("input, select, textarea")) return;
    if ((event.metaKey || event.ctrlKey) && event.key.toLocaleLowerCase() === "n" && canCreate) {
      event.preventDefault();
      setDialog({ mode: navigation.destination.type === "folder" ? "create-folder" : "create-client" });
    } else if (event.key === "Enter" && selectedNode) {
      openNode(selectedNode);
    } else if ((event.key === "Backspace" || event.key === "Delete") && selectedNode) {
      event.preventDefault();
      fileSystem.setTrashed(selectedNode.id, true);
      setSelectedId(undefined);
    }
  }

  if (!fileSystem.loaded) return null;

  return (
    <main className={styles.shell} onKeyDown={handleKeyboard} style={tagVariables} tabIndex={-1}>
      <Sidebar destination={navigation.destination} onCreateClient={() => setDialog({ mode: "create-client" })} onNavigate={(location) => navigate({ type: "location", location })} />
      <section className={styles.explorer}>
        <Toolbar canGoBack={navigation.canGoBack} canGoForward={navigation.canGoForward} destination={navigation.destination} hasSelection={Boolean(selectedNode)} onBack={navigation.back} onCreateClient={() => setDialog({ mode: "create-client" })} onCreateFolder={() => setDialog({ mode: "create-folder" })} onForward={navigation.forward} onInspectorToggle={() => setInspectorOpen((current) => !current)} onQueryChange={setQuery} onShare={() => selectedNode && fileSystem.updateNode(selectedNode.id, { shared: true })} onSortChange={setSort} onViewModeChange={setViewMode} query={query} sort={sort} title={title} viewMode={viewMode} />
        <section className={styles.workspace}>
          <section className={styles.browser} onClick={() => setContextMenu(undefined)}>
            <ExplorerContent nodes={visibleNodes} onContextMenu={showContextMenu} onOpen={openNode} onSelect={(node) => setSelectedId(node.id)} selectedNode={selectedNode} viewMode={viewMode} />
          </section>
          {inspectorOpen ? <Inspector node={selectedNode} onToggleTag={(tag) => selectedNode && fileSystem.toggleTag(selectedNode.id, tag)} /> : null}
        </section>
      </section>
      <CreateItemDialog initialName={dialog?.mode === "rename" ? dialog.node?.name : ""} onCancel={() => setDialog(undefined)} onSubmit={submitDialog} open={Boolean(dialog)} submitLabel={dialog?.mode === "rename" ? "Rename" : dialog?.mode === "create-client" ? "Create Client" : "Create Folder"} title={dialog?.mode === "rename" ? "Rename Item" : dialog?.mode === "create-client" ? "New Client" : "New Folder"} />
      {contextMenu ? <ItemContextMenu onAttentionToggle={() => { fileSystem.updateNode(contextMenu.node.id, { needsAttention: !contextMenu.node.needsAttention }); setContextMenu(undefined); }} onClose={() => setContextMenu(undefined)} onRename={() => setDialog({ mode: "rename", node: contextMenu.node })} onShareToggle={() => { fileSystem.updateNode(contextMenu.node.id, { shared: !contextMenu.node.shared }); setContextMenu(undefined); }} onTrashToggle={() => { fileSystem.setTrashed(contextMenu.node.id, !contextMenu.node.trashedAt); setSelectedId(undefined); setContextMenu(undefined); }} state={contextMenu} /> : null}
      {fileSystem.error ? <p className={styles.error} role="alert">{fileSystem.error}</p> : null}
    </main>
  );
}

const tagVariables = Object.fromEntries(Object.entries(tagColors).map(([name, color]) => [`--tag-${name}`, color])) as React.CSSProperties;
