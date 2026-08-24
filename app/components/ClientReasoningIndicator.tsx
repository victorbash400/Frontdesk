"use client";

import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";

import type { ClientChatMessage } from "./clientChatTypes";
import { ClientChatMarkdown } from "./ClientChatMarkdown";
import styles from "./ClientReasoningIndicator.module.css";

type ReasoningItem = Extract<ClientChatMessage, { kind: "reasoning" }>;

export function ClientReasoningIndicator({ item }: { item: ReasoningItem }) {
  const [open, setOpen] = useState(false);
  const streaming = !item.finishedAt;
  const expanded = streaming || open;
  const seconds = item.finishedAt && item.startedAt ? Math.max(1, Math.round((item.finishedAt - item.startedAt) / 1000)) : 1;
  return (
    <section className={styles.reasoning}>
      <button aria-expanded={expanded} onClick={() => setOpen((value) => !value)} type="button">
        {expanded ? <ChevronDown aria-hidden="true" /> : <ChevronRight aria-hidden="true" />}
        {streaming ? "Thinking" : `Thought for ${seconds}s`}
        {streaming ? <i /> : null}
      </button>
      {expanded ? <ClientChatMarkdown content={item.text} /> : null}
    </section>
  );
}
