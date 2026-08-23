"use client";

import { useDeferredValue, useMemo, useState, type KeyboardEvent, type MouseEvent } from "react";

import { useFileSystem } from "../hooks/useFileSystem";
import { useNavigationHistory } from "../hooks/useNavigationHistory";
import { breadcrumbsForDestination, folderPath, isContainer, nodesForDestination, sortNodes } from "../lib/fileSystemSelectors";
import { tagColors, type FileSystemNode, type SortMode, type ViewMode } from "../types/filesystem";
import { CreateItemDialog } from "./CreateItemDialog";
import { ClientChatPanel } from "./ClientChatPanel";
import { ExplorerContent } from "./ExplorerContent";
import { Inspector } from "./Inspector";
import { ItemContextMenu, type ContextMenuState } from "./ItemContextMenu";
import { PluginStore } from "./PluginStore";
import { Sidebar } from "./Sidebar";
import { SkillsLibrary } from "./SkillsLibrary";
import { TasksWorkspace } from "./TasksWorkspace";
import { Toolbar } from "./Toolbar";
import styles from "./OperatorShell.module.css";

type DialogState = { mode: "create-client" | "create-folder" | "rename"; node?: FileSystemNode };

export function OperatorShell() {
  const fileSystem = useFileSystem();
  const navigation = useNavigationHistory();
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<string>();
  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [sort, setSort] = useState<SortMode>("name-asc");
  const [query, setQuery] = useState("");
  const [dialog, setDialog] = useState<DialogState>();
  const [dialogError, setDialogError] = useState<string>();
  const [contextMenu, setContextMenu] = useState<ContextMenuState>();
  const deferredQuery = useDeferredValue(query.trim().toLocaleLowerCase());

  const visibleNodes = useMemo(() => {
    const scoped = nodesForDestination(fileSystem.data.nodes, navigation.destination);
    const filtered = deferredQuery ? scoped.filter((node) => node.name.toLocaleLowerCase().includes(deferredQuery)) : scoped;
    return sortNodes(filtered, sort);
  }, [deferredQuery, fileSystem.data.nodes, navigation.destination, sort]);

  const selectedNode = visibleNodes.find((node) => node.id === selectedId);
  const breadcrumbs = useMemo(() => breadcrumbsForDestination(fileSystem.data.nodes, navigation.destination), [fileSystem.data.nodes, navigation.destination]);
  const client = useMemo(() => {
    const destination = navigation.destination;
    if (destination.type === "client-location") return fileSystem.data.nodes.find((node) => node.id === destination.clientId && node.kind === "client");
    if (destination.type !== "folder") return undefined;
    return folderPath(fileSystem.data.nodes, destination.id).find((node) => node.kind === "client");
  }, [fileSystem.data.nodes, navigation.destination]);
  const clients = useMemo(() => fileSystem.data.nodes.filter((node) => node.kind === "client" && !node.trashedAt), [fileSystem.data.nodes]);
  const canCreate = navigation.destination.type === "folder" || navigation.destination.type === "location" && navigation.destination.location === "clients";
  const taskView = navigation.destination.type === "location" && navigation.destination.location === "tasks" || navigation.destination.type === "client-location" && navigation.destination.location === "tasks";
  const utilityView = taskView || navigation.destination.type === "location" && (navigation.destination.location === "plugins" || navigation.destination.location === "skills");

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
    try {
      const node = fileSystem.createNode(name, mode === "create-client" ? "client" : "folder", parentId);
      setDialog(undefined);
      setDialogError(undefined);
      setSelectedId(node.id);
    } catch (reason) {
      setDialogError(reason instanceof Error ? reason.message : "That name is already in use.");
    }
  }

  function submitDialog(name: string) {
    if (dialog?.mode === "rename" && dialog.node) {
      try {
        fileSystem.updateNode(dialog.node.id, { name });
        setDialog(undefined);
        setDialogError(undefined);
        setContextMenu(undefined);
      } catch (reason) {
        setDialogError(reason instanceof Error ? reason.message : "That name is already in use.");
      }
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
      <Sidebar client={client ? { id: client.id, name: client.name } : undefined} destination={navigation.destination} onCreateClient={() => setDialog({ mode: "create-client" })} onNavigate={navigate} />
      <section className={styles.explorer}>
        <Toolbar breadcrumbs={breadcrumbs} canGoBack={navigation.canGoBack} canGoForward={navigation.canGoForward} chatAvailable={Boolean(client)} chatOpen={chatOpen} destination={navigation.destination} hasSelection={Boolean(selectedNode)} onBack={navigation.back} onBreadcrumbNavigate={navigate} onChatToggle={() => setChatOpen((current) => !current)} onCreateClient={() => setDialog({ mode: "create-client" })} onCreateFolder={() => setDialog({ mode: "create-folder" })} onForward={navigation.forward} onInspectorToggle={() => setInspectorOpen((current) => !current)} onQueryChange={setQuery} onShare={() => selectedNode && fileSystem.updateNode(selectedNode.id, { shared: true })} onSortChange={setSort} onViewModeChange={setViewMode} query={query} sort={sort} utilityView={utilityView} viewMode={viewMode} />
        <section className={styles.workspace}>
          <section className={styles.browser} onClick={() => setContextMenu(undefined)}>
            {navigation.destination.type === "location" && navigation.destination.location === "plugins" ? <PluginStore /> : null}
            {navigation.destination.type === "location" && navigation.destination.location === "skills" ? <SkillsLibrary /> : null}
            {taskView ? <TasksWorkspace clientId={navigation.destination.type === "client-location" ? navigation.destination.clientId : undefined} clients={clients} /> : null}
            {!utilityView ? <ExplorerContent nodes={visibleNodes} onContextMenu={showContextMenu} onOpen={openNode} selectedNode={selectedNode} viewMode={viewMode} /> : null}
          </section>
          {inspectorOpen && !utilityView ? <Inspector node={selectedNode} onToggleTag={(tag) => selectedNode && fileSystem.toggleTag(selectedNode.id, tag)} /> : null}
          {client ? <ClientChatPanel clientId={client.id} key={client.id} open={chatOpen} /> : null}
        </section>
      </section>
      <CreateItemDialog error={dialogError} initialName={dialog?.mode === "rename" ? dialog.node?.name : ""} onCancel={() => { setDialog(undefined); setDialogError(undefined); }} onNameChange={() => setDialogError(undefined)} onSubmit={submitDialog} open={Boolean(dialog)} submitLabel={dialog?.mode === "rename" ? "Rename" : dialog?.mode === "create-client" ? "Create Client" : "Create Folder"} title={dialog?.mode === "rename" ? "Rename Item" : dialog?.mode === "create-client" ? "New Client" : "New Folder"} />
      {contextMenu ? <ItemContextMenu onAttentionToggle={() => { fileSystem.updateNode(contextMenu.node.id, { needsAttention: !contextMenu.node.needsAttention }); setContextMenu(undefined); }} onClose={() => setContextMenu(undefined)} onRename={() => setDialog({ mode: "rename", node: contextMenu.node })} onShareToggle={() => { fileSystem.updateNode(contextMenu.node.id, { shared: !contextMenu.node.shared }); setContextMenu(undefined); }} onTrashToggle={() => { fileSystem.setTrashed(contextMenu.node.id, !contextMenu.node.trashedAt); setSelectedId(undefined); setContextMenu(undefined); }} state={contextMenu} /> : null}
      {fileSystem.error ? <p className={styles.error} role="alert">{fileSystem.error}</p> : null}
    </main>
  );
}

const tagVariables = Object.fromEntries(Object.entries(tagColors).map(([name, color]) => [`--tag-${name}`, color])) as React.CSSProperties;
