"use client";

import { useEffect, useState } from "react";

import { useGoogleWorkspaceConnection } from "../hooks/useGoogleWorkspaceConnection";
import { PluginSection } from "./PluginSection";
import { WorkspacePermissions } from "./WorkspacePermissions";
import { WorkspaceProfile } from "./WorkspaceProfile";
import styles from "./WorkspaceSection.module.css";


export function WorkspaceSection({ accountId }: { accountId: string }) {
  const workspace = useGoogleWorkspaceConnection();
  const [showEmail, setShowEmail] = useState(true);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setShowEmail(window.localStorage.getItem(`front-desk-workspace-show-email:${accountId}`) !== "false"));
    return () => window.cancelAnimationFrame(frame);
  }, [accountId]);

  const changeEmailVisibility = (visible: boolean) => {
    window.localStorage.setItem(`front-desk-workspace-show-email:${accountId}`, String(visible));
    setShowEmail(visible);
  };
  const run = (action: Promise<unknown>) => void action.catch((reason) => workspace.setError(reason instanceof Error ? reason.message : "Could not update Google Workspace"));

  return <>
    {workspace.error ? <p className={styles.error} role="alert">{workspace.error}</p> : null}
    <PluginSection description="Your connected Google account." title="Workspace">
      <WorkspaceProfile
        configured={workspace.configured}
        connected={workspace.connected}
        email={workspace.email}
        needsReconnect={workspace.needs_reconnect}
        onConnect={() => run(workspace.connect())}
        onDisconnect={() => run(workspace.disconnect())}
        onEmailVisibilityChange={changeEmailVisibility}
        showEmail={showEmail}
      />
    </PluginSection>
    <PluginSection description="Services Front Desk may use from that account." title="Permissions">
      <WorkspacePermissions connected={workspace.connected} onChange={(permissionId, enabled) => run(workspace.setPermission(permissionId, enabled))} permissions={workspace.permissions} />
    </PluginSection>
  </>;
}
