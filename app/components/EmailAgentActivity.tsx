import { CircleAlert, LoaderCircle } from "lucide-react";

import type { MailThread } from "../types/mail";
import styles from "./EmailAgentActivity.module.css";

export function EmailAgentActivity({ thread }: { thread: MailThread }) {
  return <aside aria-label="Email Agent activity" className={styles.activity}>
    <header><strong>Email Agent</strong><Status status={thread.agentStatus} /></header>
    {thread.agentFailure ? <p className={styles.failure}><CircleAlert aria-hidden="true" />{thread.agentFailure}</p> : null}
    <ol>{thread.activities.map((item) => <li key={item.id}><i /><span>{item.summary}</span></li>)}</ol>
  </aside>;
}

function Status({ status }: { status: MailThread["agentStatus"] }) {
  if (status === "processing" || status === "queued") return <small className={styles.running}><LoaderCircle aria-hidden="true" />{status === "queued" ? "Queued" : "Working"}</small>;
  return <small>{status === "failed" ? "Needs attention" : "Done"}</small>;
}
