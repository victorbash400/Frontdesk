"use client";

import Image from "next/image";
import { Bell, SquarePen } from "lucide-react";
import { useState } from "react";

import { useClientNotifications } from "../hooks/useClientNotifications";
import { ClientNotificationPanel } from "./ClientNotificationPanel";
import styles from "./ClientAssistantActions.module.css";

type ClientAssistantActionsProps = {
  chatOpen: boolean;
  clientId: string;
  onChatToggle: () => void;
  onVoiceToggle: () => void;
  voiceOpen: boolean;
};

export function ClientAssistantActions({ chatOpen, clientId, onChatToggle, onVoiceToggle, voiceOpen }: ClientAssistantActionsProps) {
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const notifications = useClientNotifications(clientId);
  const openCount = notifications.notifications.filter((item) => item.status === "open").length;
  return (
    <nav aria-label="Client assistant" className={styles.wrapper}>
      <span className={styles.actions}><button aria-label="Client chat" aria-pressed={chatOpen} onClick={onChatToggle} title="Client chat" type="button">
        <SquarePen aria-hidden="true" />
      </button>
      <button aria-label="Client voice" aria-pressed={voiceOpen} onClick={onVoiceToggle} title="Client voice" type="button">
        <Image alt="" aria-hidden="true" height={18} src="/voice-recognition-svgrepo-com.svg" width={18} />
      </button>
      <button aria-label="Client notifications" aria-expanded={notificationsOpen} onClick={() => { setNotificationsOpen((value) => !value); void notifications.refresh(); }} title="Client notifications" type="button"><Bell aria-hidden="true" />{openCount ? <small>{openCount}</small> : null}</button></span>
      {notificationsOpen ? <ClientNotificationPanel error={notifications.error} notifications={notifications.notifications} onAnswer={notifications.answer} /> : null}
    </nav>
  );
}
