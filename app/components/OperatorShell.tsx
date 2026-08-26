"use client";

import { useDeferredValue, useMemo, useState, type KeyboardEvent, type MouseEvent } from "react";

import { useFileSystem } from "../hooks/useFileSystem";
import { useNavigationHistory } from "../hooks/useNavigationHistory";
import { breadcrumbsForDestination, folderPath, isContainer, nodesForDestination, sortNodes } from "../lib/fileSystemSelectors";
import { tagColors, type FileSystemNode, type SortMode, type ViewMode } from "../types/filesystem";
import type { OperatorAccount } from "../types/account";
import { CreateItemDialog } from "./CreateItemDialog";
import { ClientChatPanel } from "./ClientChatPanel";
import { ClientVoicePanel } from "./ClientVoicePanel";
import { ClientProfileEditor } from "./ClientProfileEditor";
import { MarkdownDocumentEditor } from "./MarkdownDocumentEditor";
import { ExplorerContent } from "./ExplorerContent";
import { ItemContextMenu, type ContextMenuState } from "./ItemContextMenu";
import { PluginStore } from "./PluginStore";
import { Sidebar } from "./Sidebar";
import { SkillsLibrary } from "./SkillsLibrary";
import { TasksWorkspace } from "./TasksWorkspace";
import { GoalsWorkspace } from "./GoalsWorkspace";
import { Toolbar } from "./Toolbar";
import styles from "./OperatorShell.module.css";

type DialogState = { mode: "create-client" | "create-folder" | "rename"; node?: FileSystemNode };

export function OperatorShell({ account }: { account: OperatorAccount }) {
  const fileSystem = useFileSystem(account.id);
  const navigation = useNavigationHistory();
  const [chatOpen, setChatOpen] = useState(false);
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<string>();
  const [openFileId, setOpenFileId] = useState<string>();
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
  const openFile = fileSystem.data.nodes.find((node) => node.id === openFileId && (node.kind === "profile" || node.kind === "document"));
  const breadcrumbs = useMemo(() => breadcrumbsForDestination(fileSystem.data.nodes, navigation.destination), [fileSystem.data.nodes, navigation.destination]);
  const client = useMemo(() => {
    const destination = navigation.destination;
    if (destination.type !== "folder") return undefined;
    return folderPath(fileSystem.data.nodes, destination.id).find((node) => node.kind === "client");
  }, [fileSystem.data.nodes, navigation.destination]);
  const clients = useMemo(() => fileSystem.data.nodes.filter((node) => node.kind === "client" && !node.trashedAt), [fileSystem.data.nodes]);
  const canCreate = navigation.destination.type === "folder" || navigation.destination.type === "location" && navigation.destination.location === "clients";
  const taskView = navigation.destination.type === "location" && navigation.destination.location === "tasks";
  const goalView = navigation.destination.type === "location" && navigation.destination.location === "goals";
  const utilityView = Boolean(openFile) || taskView || goalView || navigation.destination.type === "location" && (navigation.destination.location === "plugins" || navigation.destination.location === "skills");
  const explorerKey = navigation.destination.type === "folder" ? `folder-${navigation.destination.id}` : `location-${navigation.destination.location}`;

  function navigate(destination: Parameters<typeof navigation.navigate>[0]) {
    navigation.navigate(destination);
    if (destination.type === "location") { setChatOpen(false); setVoiceOpen(false); }
    setSelectedId(undefined);
    setOpenFileId(undefined);
    setContextMenu(undefined);
  }

  function openNode(node: FileSystemNode) {
    if (isContainer(node)) navigate({ type: "folder", id: node.id });
    else if (node.kind === "profile" || node.kind === "document") {
      setSelectedId(node.id);
      setOpenFileId(node.id);
    }
    else setSelectedId(node.id);
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
    } else if ((event.key === "Backspace" || event.key === "Delete") && selectedNode && !selectedNode.protected) {
      event.preventDefault();
      fileSystem.setTrashed(selectedNode.id, true);
      setSelectedId(undefined);
    }
  }

  if (!fileSystem.loaded) return null;

  return (
    <main className={styles.shell} onKeyDown={handleKeyboard} style={tagVariables} tabIndex={-1}>
      <Sidebar account={account} destination={navigation.destination} onCreateClient={() => setDialog({ mode: "create-client" })} onNavigate={navigate} />
      <section className={styles.explorer}>
        <Toolbar breadcrumbs={breadcrumbs} canGoBack={navigation.canGoBack} canGoForward={navigation.canGoForward} chatAvailable={Boolean(client)} chatOpen={chatOpen} clientId={client?.id} destination={navigation.destination} hasSelection={Boolean(selectedNode)} onBack={() => { navigation.back(); setOpenFileId(undefined); }} onBreadcrumbNavigate={navigate} onChatToggle={() => { setVoiceOpen(false); setChatOpen((current) => !current); }} onCreateClient={() => setDialog({ mode: "create-client" })} onCreateFolder={() => setDialog({ mode: "create-folder" })} onForward={() => { navigation.forward(); setOpenFileId(undefined); }} onQueryChange={setQuery} onShare={() => selectedNode && fileSystem.updateNode(selectedNode.id, { shared: true })} onSortChange={setSort} onViewModeChange={setViewMode} onVoiceToggle={() => { setChatOpen(false); setVoiceOpen((current) => !current); }} query={query} sort={sort} utilityView={utilityView} viewMode={viewMode} voiceOpen={voiceOpen} />
        <section className={styles.workspace}>
          <section className={styles.browser} onClick={() => setContextMenu(undefined)}>
            {navigation.destination.type === "location" && navigation.destination.location === "plugins" ? <PluginStore accountId={account.id} /> : null}
            {navigation.destination.type === "location" && navigation.destination.location === "skills" ? <SkillsLibrary accountId={account.id} /> : null}
            {taskView ? <TasksWorkspace accountId={account.id} clients={clients} /> : null}
            {goalView ? <GoalsWorkspace accountId={account.id} clients={clients} /> : null}
            {openFile?.kind === "profile" && client ? <ClientProfileEditor clientName={client.name} key={`${openFile.id}-${openFile.updatedAt}`} onBack={() => setOpenFileId(undefined)} onSave={(content) => fileSystem.updateNode(openFile.id, { content })} profile={openFile} /> : null}
            {openFile?.kind === "document" ? <MarkdownDocumentEditor document={openFile} key={`${openFile.id}-${openFile.updatedAt}`} onBack={() => setOpenFileId(undefined)} onSave={(content) => fileSystem.updateNode(openFile.id, { content })} /> : null}
            {!utilityView ? <ExplorerContent allNodes={fileSystem.data.nodes} destination={navigation.destination} key={explorerKey} nodes={visibleNodes} onContextMenu={showContextMenu} onOpen={openNode} onSelect={(node) => setSelectedId(node.id)} onRename={(node) => setDialog({ mode: "rename", node })} onTrashToggle={(node) => { fileSystem.setTrashed(node.id, !node.trashedAt); setSelectedId(undefined); }} selectedNode={selectedNode} viewMode={viewMode} /> : null}
          </section>
          {client ? <ClientChatPanel accountId={account.id} clientId={client.id} key={client.id} open={chatOpen} /> : null}
          {client ? <ClientVoicePanel accountId={account.id} clientId={client.id} key={`voice-${client.id}`} open={voiceOpen} /> : null}
        </section>
      </section>
      <CreateItemDialog error={dialogError} initialName={dialog?.mode === "rename" ? dialog.node?.name : ""} onCancel={() => { setDialog(undefined); setDialogError(undefined); }} onNameChange={() => setDialogError(undefined)} onSubmit={submitDialog} open={Boolean(dialog)} submitLabel={dialog?.mode === "rename" ? "Rename" : dialog?.mode === "create-client" ? "Create Client" : "Create Folder"} title={dialog?.mode === "rename" ? "Rename Item" : dialog?.mode === "create-client" ? "New Client" : "New Folder"} />
      {contextMenu ? <ItemContextMenu onAttentionToggle={() => { fileSystem.updateNode(contextMenu.node.id, { needsAttention: !contextMenu.node.needsAttention }); setContextMenu(undefined); }} onClose={() => setContextMenu(undefined)} onRename={() => setDialog({ mode: "rename", node: contextMenu.node })} onShareToggle={() => { fileSystem.updateNode(contextMenu.node.id, { shared: !contextMenu.node.shared }); setContextMenu(undefined); }} onTrashToggle={() => { fileSystem.setTrashed(contextMenu.node.id, !contextMenu.node.trashedAt); setSelectedId(undefined); setContextMenu(undefined); }} state={contextMenu} /> : null}
      {fileSystem.error ? <p className={styles.error} role="alert">{fileSystem.error}</p> : null}
    </main>
  );
}

const tagVariables = Object.fromEntries(Object.entries(tagColors).map(([name, color]) => [`--tag-${name}`, color])) as React.CSSProperties;
