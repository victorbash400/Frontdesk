"use client";

import { Unplug } from "lucide-react";
import { useEffect, useRef } from "react";

import type { PluginDefinition } from "../lib/pluginDirectory";
import { GitHubRepositoryAccess } from "./GitHubRepositoryAccess";
import { PluginIcon } from "./PluginIcon";
import styles from "./PluginConnectionDialog.module.css";

type PluginConnectionDialogProps = {
  connected: boolean;
  plugin?: PluginDefinition;
  onCancel: () => void;
  onConfirm: () => void;
  onRefresh: () => void;
};

export function PluginConnectionDialog({ connected, plugin, onCancel, onConfirm, onRefresh }: PluginConnectionDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (plugin && !dialog.open) dialog.showModal();
    else if (!plugin && dialog.open) dialog.close();
  }, [plugin]);

  return (
    <dialog className={styles.dialog} onCancel={onCancel} ref={dialogRef}>
      {plugin ? <section>
        <header><PluginIcon plugin={plugin} variant="dialog" /><span><h2>{connected && plugin.id === "github" ? "Manage GitHub" : connected ? `Disconnect ${plugin.name}?` : `Connect ${plugin.name}`}</h2><p>{plugin.description}</p></span></header>
        {!connected ? <><h3>Front Desk will be able to</h3><ul>{plugin.permissions.map((permission) => <li key={permission}>{permission}</li>)}</ul></> : plugin.id !== "github" ? <p className={styles.disconnect}>Front Desk will stop using this connection. Existing client files, tasks, and goals will remain unchanged.</p> : null}
        {connected && plugin.id === "github" ? <GitHubRepositoryAccess onSaved={onRefresh} /> : null}
        <footer><button onClick={onCancel} type="button">{connected && plugin.id === "github" ? "Close" : "Cancel"}</button><button className={connected ? styles.danger : styles.primary} onClick={onConfirm} type="button">{connected ? <Unplug aria-hidden="true" /> : null}{connected ? "Disconnect" : "Connect"}</button></footer>
      </section> : null}
    </dialog>
  );
}
