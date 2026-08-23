"use client";

import { useState } from "react";

import type { ClientChat } from "./clientChatTypes";
import { ClientChatComposer } from "./ClientChatComposer";
import { ClientChatDrawer } from "./ClientChatDrawer";
import { ClientChatHeader } from "./ClientChatHeader";
import { ClientChatMessageList } from "./ClientChatMessageList";
import styles from "./ClientChatPanel.module.css";

type ClientChatPanelProps = {
  clientId: string;
  open: boolean;
};

function newChat(id = crypto.randomUUID()): ClientChat {
  return { id, title: "New chat", messages: [] };
}

export function ClientChatPanel({ clientId, open }: ClientChatPanelProps) {
  const [chats, setChats] = useState<ClientChat[]>(() => [newChat("initial")]);
  const [activeId, setActiveId] = useState("initial");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [query, setQuery] = useState("");
  const activeChat = chats.find((chat) => chat.id === activeId) ?? chats[0];

  function createChat() {
    const chat = newChat();
    setChats((current) => [chat, ...current]);
    setActiveId(chat.id);
    setDrawerOpen(false);
  }

  function deleteChat(id: string) {
    const remaining = chats.filter((chat) => chat.id !== id);
    if (remaining.length) {
      setChats(remaining);
      if (id === activeId) setActiveId(remaining[0].id);
      return;
    }
    const replacement = newChat();
    setChats([replacement]);
    setActiveId(replacement.id);
  }

  function send(text: string) {
    setChats((current) => current.map((chat) => chat.id === activeChat.id ? {
      ...chat,
      messages: [...chat.messages, { id: crypto.randomUUID(), kind: "message" as const, role: "user" as const, text }],
    } : chat));
  }

  return (
    <aside aria-hidden={!open} aria-label="Client chat" className={styles.panel} data-open={open} data-client={clientId} inert={!open ? true : undefined}>
      <ClientChatHeader onDrawerToggle={() => setDrawerOpen((current) => !current)} />
      <ClientChatMessageList messages={activeChat.messages} />
      <ClientChatComposer onSend={send} />
      <ClientChatDrawer activeId={activeChat.id} chats={chats} onClose={() => setDrawerOpen(false)} onDelete={deleteChat} onNewChat={createChat} onQueryChange={setQuery} onSelect={(id) => { setActiveId(id); setDrawerOpen(false); }} open={drawerOpen} query={query} />
    </aside>
  );
}
