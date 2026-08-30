"use client";

import { Check, CircleAlert, LoaderCircle, X } from "lucide-react";
import { useEffect, useRef } from "react";

import type { MailThread } from "../types/mail";
import { EmailAgentRetryButton } from "./EmailAgentRetryButton";
import styles from "./EmailAgentActivity.module.css";

export function EmailAgentActivity({ thread, onRetry }: { thread: MailThread; onRetry: (messageId: string) => Promise<void> }) {
  const running = thread.agentStatus === "processing" || thread.agentStatus === "queued";
  const messageId = [...thread.messages].reverse().find((message) => message.direction === "inbound")?.id;
  const activityRef = useRef<HTMLElement>(null);
  useEffect(() => {
    activityRef.current?.scrollTo({ behavior: "smooth", top: activityRef.current.scrollHeight });
  }, [thread.activities.length, thread.agentStatus]);
  return <aside aria-label="Email Agent activity" className={styles.activity} ref={activityRef}>
    <header><strong>Email Agent</strong><span className={styles.controls}><Status status={thread.agentStatus} /><EmailAgentRetryButton disabled={running} messageId={messageId} onRetry={onRetry} /></span></header>
    {thread.agentFailure ? <p className={styles.failure}><CircleAlert aria-hidden="true" />{thread.agentFailure}</p> : null}
    <ol>{thread.activities.map((item, index) => {
      const current = running && index === thread.activities.length - 1;
      const failed = thread.agentStatus === "failed" && index === thread.activities.length - 1;
      return <li data-state={failed ? "failed" : current ? "running" : "completed"} key={item.id}>
        <span className={styles.marker}>{failed ? <X aria-hidden="true" /> : current ? <LoaderCircle aria-hidden="true" /> : <Check aria-hidden="true" />}</span>
        <span className={styles.step}>{item.summary}</span>
      </li>;
    })}</ol>
  </aside>;
}

function Status({ status }: { status: MailThread["agentStatus"] }) {
  if (status === "processing" || status === "queued") return <small className={styles.running}><LoaderCircle aria-hidden="true" />{status === "queued" ? "Queued" : "Working"}</small>;
  return <small>{status === "failed" ? "Needs attention" : "Done"}</small>;
}
