"use client";

import { useEffect, useRef, useState } from "react";

import { applyClientChatEvent } from "../lib/clientChatMessages";
import { loadClientChats, saveClientChats } from "../lib/clientChatStorage";
import { streamClientChat } from "../lib/clientChatStream";
import type { ClientChat } from "./clientChatTypes";
import { ClientChatComposer } from "./ClientChatComposer";
import { ClientChatDrawer } from "./ClientChatDrawer";
import { ClientChatHeader } from "./ClientChatHeader";
import { ClientChatMessageList } from "./ClientChatMessageList";
import styles from "./ClientChatPanel.module.css";

type ClientChatPanelProps = {
  accountId: string;
  clientId: string;
  open: boolean;
};

function newChat(): ClientChat {
  const now = Date.now();
  return { createdAt: now, id: crypto.randomUUID(), title: "New chat", messages: [], updatedAt: now };
}

export function ClientChatPanel({ accountId, clientId, open }: ClientChatPanelProps) {
  const [chats, setChats] = useState<ClientChat[]>([]);
  const [activeId, setActiveId] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [streaming, setStreaming] = useState(false);
  const controllerRef = useRef<AbortController | undefined>(undefined);
  const activeChat = chats.find((chat) => chat.id === activeId) ?? chats[0];
  const latestMessage = activeChat?.messages.at(-1);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const saved = loadClientChats(accountId, clientId);
      const next = saved.length ? saved : [newChat()];
      setChats(next);
      setActiveId(next[0].id);
      setLoaded(true);
    });
    return () => {
      window.cancelAnimationFrame(frame);
      controllerRef.current?.abort();
    };
  }, [accountId, clientId]);

  useEffect(() => {
    if (loaded) saveClientChats(accountId, clientId, chats);
  }, [accountId, chats, clientId, loaded]);

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

  async function send(text: string) {
    if (streaming) return;
    const chatId = activeChat.id;
    setChats((current) => current.map((chat) => chat.id === activeChat.id ? {
      ...chat,
      messages: [...chat.messages, { id: crypto.randomUUID(), kind: "message" as const, role: "user" as const, text }],
      updatedAt: Date.now(),
    } : chat));
    setStreaming(true);
    const controller = new AbortController();
    controllerRef.current = controller;
    try {
      await streamClientChat({
        chatId,
        clientId,
        createTitle: activeChat.title === "New chat",
        message: text,
        signal: controller.signal,
        onEvent: (event) => {
          setChats((current) => current.map((chat) => chat.id === chatId ? {
            ...chat,
            title: event.type === "title" ? event.title : chat.title,
            messages: applyClientChatEvent(chat.messages, event),
            updatedAt: Date.now(),
          } : chat));
        },
      });
    } catch (reason) {
      if (!(reason instanceof DOMException && reason.name === "AbortError")) {
        const error = reason instanceof Error ? reason.message : "Front Desk chat failed";
        setChats((current) => current.map((chat) => chat.id === chatId ? { ...chat, messages: applyClientChatEvent(chat.messages, { type: "error", error }), updatedAt: Date.now() } : chat));
      }
    } finally {
      setStreaming(false);
      controllerRef.current = undefined;
    }
  }

  if (!loaded || !activeChat) return null;

  return (
    <aside aria-hidden={!open} aria-label="Client chat" className={styles.panel} data-open={open} data-client={clientId} inert={!open ? true : undefined}>
      <ClientChatHeader onDrawerToggle={() => setDrawerOpen((current) => !current)} title={activeChat.title} />
      <ClientChatMessageList messages={activeChat.messages} waiting={streaming && latestMessage?.kind === "message" && latestMessage.role === "user"} />
      <ClientChatComposer disabled={streaming} onSend={(text) => void send(text)} />
      <ClientChatDrawer activeId={activeChat.id} chats={chats} onClose={() => setDrawerOpen(false)} onDelete={deleteChat} onNewChat={createChat} onQueryChange={setQuery} onSelect={(id) => { setActiveId(id); setDrawerOpen(false); }} open={drawerOpen} query={query} />
    </aside>
  );
}
