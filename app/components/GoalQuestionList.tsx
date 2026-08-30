"use client";

import { ArrowUp, ChevronDown } from "lucide-react";
import { useState } from "react";

import type { ClientNotification } from "../hooks/useClientNotifications";
import type { FileSystemNode } from "../types/filesystem";
import styles from "./GoalQuestionList.module.css";

type GoalQuestionListProps = {
  clients: FileSystemNode[];
  error?: string;
  onAnswer: (id: string, answer: string) => Promise<void>;
  questions: ClientNotification[];
};

export function GoalQuestionList({ clients, error, onAnswer, questions }: GoalQuestionListProps) {
  const [expandedId, setExpandedId] = useState<string | null>();
  if (error) return <p className={styles.error} role="alert">{error}</p>;
  if (!questions.length) return <p className={styles.empty}>No questions need your attention.</p>;
  const activeExpandedId = expandedId === null ? undefined : questions.some((question) => question.id === expandedId) ? expandedId : questions[0].id;
  return <ol className={styles.list}>{questions.map((question, index) => <GoalQuestion clients={clients} expanded={activeExpandedId === question.id} index={index + 1} item={question} key={question.id} onAnswer={onAnswer} onToggle={() => setExpandedId(activeExpandedId === question.id ? null : question.id)} />)}</ol>;
}

function GoalQuestion({ clients, expanded, index, item, onAnswer, onToggle }: { clients: FileSystemNode[]; expanded: boolean; index: number; item: ClientNotification; onAnswer: GoalQuestionListProps["onAnswer"]; onToggle: () => void }) {
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState<string>();
  const [sending, setSending] = useState(false);
  const clientName = clients.find((client) => client.id === item.clientId)?.name ?? "Client";

  async function submit() {
    setSending(true);
    try {
      await onAnswer(item.id, answer.trim());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not answer question.");
      setSending(false);
    }
  }

  return <li className={styles.question} data-expanded={expanded}>
    <button aria-expanded={expanded} className={styles.toggle} onClick={onToggle} type="button">
      <small>{index}</small><span>{item.message}</span><ChevronDown aria-hidden="true" />
    </button>
    {expanded ? <section className={styles.answer}>
      <header><strong>{clientName}</strong><time dateTime={item.createdAt}>{new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(item.createdAt))}</time></header>
      <form onSubmit={(event) => { event.preventDefault(); void submit(); }}>
        <input aria-label={`Answer question for ${clientName}`} autoComplete="off" onChange={(event) => setAnswer(event.target.value)} placeholder="Write your answer" value={answer} />
        <button aria-label={sending ? "Sending answer" : "Send answer"} disabled={sending || !answer.trim()} type="submit"><ArrowUp aria-hidden="true" /></button>
      </form>
      {error ? <small role="alert">{error}</small> : null}
    </section> : null}
  </li>;
}
