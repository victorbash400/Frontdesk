"use client";

import { useState } from "react";

import { useMailbox } from "../hooks/useMailbox";
import { useMailboxThreads } from "../hooks/useMailboxThreads";
import { EmailInbox } from "./EmailInbox";
import { EmailAttentionButton } from "./EmailAttentionButton";
import { MailboxConnectionCard } from "./MailboxConnectionCard";
import { TitanMailboxForm } from "./TitanMailboxForm";
import styles from "./EmailsWorkspace.module.css";

export function EmailsWorkspace() {
  const { connect, disconnect, error, mailbox } = useMailbox();
  const connected = mailbox?.connected === true;
  const inbox = useMailboxThreads(connected);
  const [selectedId, setSelectedId] = useState<string>();
  const attention = inbox.threads.filter((thread) => thread.attentionRequired);

  return <section className={styles.workspace}><header><span><h1>Email</h1><p>The Email Agent files customer messages and starts work only when needed.</p></span>{connected ? <MailboxConnectionCard mailbox={mailbox} onDisconnect={disconnect} /> : null}</header>{error || inbox.error ? <p className={styles.error} role="alert">{error || inbox.error}</p> : null}{connected && inbox.loaded ? <section className={styles.panel}><header><strong>Customer inbox</strong><span><small>{inbox.threads.length} {inbox.threads.length === 1 ? "conversation" : "conversations"}</small><EmailAttentionButton count={attention.length} onClick={() => attention[0] && setSelectedId(attention[0].id)} /></span></header><EmailInbox onSelect={setSelectedId} selectedId={selectedId} threads={inbox.threads} /></section> : mailbox && !connected ? <TitanMailboxForm onConnect={connect} /> : null}</section>;
}
