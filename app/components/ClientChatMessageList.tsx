"use client";

import { useEffect, useRef } from "react";

import type { ClientChatMessage } from "./clientChatTypes";
import { ClientChatMessageBubble } from "./ClientChatMessageBubble";
import { ClientChatThinkingIndicator } from "./ClientChatThinkingIndicator";
import styles from "./ClientChatMessageList.module.css";

type ClientChatMessageListProps = {
  messages: ClientChatMessage[];
  waiting: boolean;
};

export function ClientChatMessageList({ messages, waiting }: ClientChatMessageListProps) {
  const listRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const list = listRef.current;
    if (list) list.scrollTop = list.scrollHeight;
  }, [messages, waiting]);
  return (
    <section aria-live="polite" className={styles.messages} ref={listRef}>
      {messages.map((message) => <ClientChatMessageBubble key={message.id} message={message} />)}
      {waiting && <ClientChatThinkingIndicator />}
    </section>
  );
}
