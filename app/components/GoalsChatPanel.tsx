"use client";

import { useEffect, useRef, useState } from "react";

import { applyClientChatEvent } from "../lib/clientChatMessages";
import { loadClientChats, saveClientChats } from "../lib/clientChatStorage";
import { streamGoalsChat } from "../lib/goalsChatStream";
import type { ClientChat } from "./clientChatTypes";
import { ClientChatComposer } from "./ClientChatComposer";
import { ClientChatDrawer } from "./ClientChatDrawer";
import { ClientChatHeader } from "./ClientChatHeader";
import { ClientChatMessageList } from "./ClientChatMessageList";
import styles from "./GoalsChatPanel.module.css";

const STORAGE_SCOPE = "all-goals";

function newChat(): ClientChat {
  const now = Date.now();
  return { createdAt: now, id: crypto.randomUUID(), title: "Goals chat", messages: [], updatedAt: now };
}

export function GoalsChatPanel({ accountId, open }: { accountId: string; open: boolean }) {
  const [chats, setChats] = useState<ClientChat[]>([]);
  const [activeId, setActiveId] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [streaming, setStreaming] = useState(false);
  const controllerRef = useRef<AbortController | undefined>(undefined);
  const active = chats.find((chat) => chat.id === activeId) ?? chats[0];

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const saved = loadClientChats(accountId, STORAGE_SCOPE);
      const next = saved.length ? saved : [newChat()];
      setChats(next);
      setActiveId(next[0].id);
      setLoaded(true);
    });
    return () => { window.cancelAnimationFrame(frame); controllerRef.current?.abort(); };
  }, [accountId]);
  useEffect(() => { if (loaded) saveClientChats(accountId, STORAGE_SCOPE, chats); }, [accountId, chats, loaded]);

  function createChat() {
    const chat = newChat();
    setChats((current) => [chat, ...current]);
    setActiveId(chat.id);
    setDrawerOpen(false);
  }

  function deleteChat(id: string) {
    const remaining = chats.filter((chat) => chat.id !== id);
    const next = remaining.length ? remaining : [newChat()];
    setChats(next);
    if (id === activeId || !remaining.length) setActiveId(next[0].id);
  }

  async function send(message: string) {
    if (!active || streaming) return;
    const chatId = active.id;
    setChats((current) => current.map((chat) => chat.id === chatId ? { ...chat, messages: [...chat.messages, { id: crypto.randomUUID(), kind: "message", role: "user", text: message }], updatedAt: Date.now() } : chat));
    setStreaming(true);
    const controller = new AbortController();
    controllerRef.current = controller;
    try {
      await streamGoalsChat({ chatId, createTitle: active.title === "Goals chat", message, signal: controller.signal, onEvent: (event) => setChats((current) => current.map((chat) => chat.id === chatId ? { ...chat, title: event.type === "title" ? event.title : chat.title, messages: applyClientChatEvent(chat.messages, event), updatedAt: Date.now() } : chat)) });
    } catch (reason) {
      if (!(reason instanceof DOMException && reason.name === "AbortError")) {
        const error = reason instanceof Error ? reason.message : "Goals chat failed";
        setChats((current) => current.map((chat) => chat.id === chatId ? { ...chat, messages: applyClientChatEvent(chat.messages, { type: "error", error }), updatedAt: Date.now() } : chat));
      }
    } finally {
      setStreaming(false);
      controllerRef.current = undefined;
    }
  }

  if (!loaded || !active) return null;
  const latest = active.messages.at(-1);
  return <aside aria-hidden={!open} aria-label="Goals chat" className={styles.panel} data-open={open} inert={!open ? true : undefined}>
    <ClientChatHeader onDrawerToggle={() => setDrawerOpen((current) => !current)} title={active.title} />
    <ClientChatMessageList messages={active.messages} waiting={streaming && latest?.kind === "message" && latest.role === "user"} />
    <ClientChatComposer disabled={streaming} onSend={(message) => void send(message)} />
    <ClientChatDrawer activeId={active.id} chats={chats} onClose={() => setDrawerOpen(false)} onDelete={deleteChat} onNewChat={createChat} onQueryChange={setQuery} onSelect={(id) => { setActiveId(id); setDrawerOpen(false); }} open={drawerOpen} query={query} />
  </aside>;
}
