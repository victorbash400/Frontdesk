"use client";

import { Unplug } from "lucide-react";
import { useEffect, useRef } from "react";

import type { PluginDefinition } from "../lib/pluginDirectory";
import styles from "./PluginConnectionDialog.module.css";

type PluginConnectionDialogProps = {
  connected: boolean;
  plugin?: PluginDefinition;
  onCancel: () => void;
  onConfirm: () => void;
};

export function PluginConnectionDialog({ connected, plugin, onCancel, onConfirm }: PluginConnectionDialogProps) {
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
        <header><span className={styles.icon} style={{ "--plugin-color": plugin.color } as React.CSSProperties}><plugin.icon aria-hidden="true" /></span><span><h2>{connected ? `Disconnect ${plugin.name}?` : `Connect ${plugin.name}`}</h2><p>{plugin.description}</p></span></header>
        {!connected ? <><h3>Front Desk will be able to</h3><ul>{plugin.permissions.map((permission) => <li key={permission}>{permission}</li>)}</ul></> : <p className={styles.disconnect}>Front Desk will stop using this connection. Existing client files, tasks, and goals will remain unchanged.</p>}
        <footer><button onClick={onCancel} type="button">Cancel</button><button className={connected ? styles.danger : styles.primary} onClick={onConfirm} type="button">{connected ? <Unplug aria-hidden="true" /> : null}{connected ? "Disconnect" : "Connect"}</button></footer>
      </section> : null}
    </dialog>
  );
}
