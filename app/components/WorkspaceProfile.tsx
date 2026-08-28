"use client";

import { CircleUserRound, Eye, EyeOff } from "lucide-react";
import { useState } from "react";

import styles from "./WorkspaceProfile.module.css";


type WorkspaceProfileProps = {
  configured: boolean;
  connected: boolean;
  email?: string | null;
  name?: string | null;
  needsReconnect: boolean;
  picture?: string | null;
  showEmail: boolean;
  onConnect: () => void;
  onDisconnect: () => void;
  onEmailVisibilityChange: (visible: boolean) => void;
};

export function WorkspaceProfile({ configured, connected, email, name, needsReconnect, onConnect, onDisconnect, onEmailVisibilityChange, picture, showEmail }: WorkspaceProfileProps) {
  const [failedPicture, setFailedPicture] = useState<string | null>(null);
  const hasAccount = connected || needsReconnect;
  const showPhoto = hasAccount && picture && picture !== failedPicture;

  return (
    <section aria-label="Google account" className={styles.profile}>
      <span className={styles.avatar}>
        {showPhoto ? <img alt="" onError={() => setFailedPicture(picture)} src={picture} /> : <CircleUserRound aria-hidden="true" />}
      </span>
      <span className={styles.identity}>
        <strong>{hasAccount ? name || "Google account" : "Google Workspace"}</strong>
        {hasAccount ? <span className={styles.email}>
          {showEmail ? email || "Connected account" : "Email hidden"}
          <button aria-label={showEmail ? "Hide email address" : "Show email address"} onClick={() => onEmailVisibilityChange(!showEmail)} type="button">{showEmail ? <Eye aria-hidden="true" /> : <EyeOff aria-hidden="true" />}</button>
          {needsReconnect ? <small>Reconnect required</small> : null}
        </span> : <span>{configured ? "Connect your Google account to Front Desk" : "Google OAuth setup required"}</span>}
      </span>
      <button className={styles.connection} disabled={!configured} onClick={connected ? onDisconnect : onConnect} type="button">{connected ? "Disconnect" : needsReconnect ? "Reconnect" : "Connect"}</button>
    </section>
  );
}
