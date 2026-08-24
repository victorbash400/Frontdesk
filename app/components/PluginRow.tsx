import type { PluginDefinition } from "../lib/pluginDirectory";
import { Trash2 } from "lucide-react";
import type { ReactNode } from "react";
import styles from "./PluginRow.module.css";

type PluginRowProps = {
  enabled: boolean;
  plugin: PluginDefinition;
  onToggle: () => void;
  enabledLabel?: string;
  disabledLabel?: string;
  detail?: ReactNode;
  disabled?: boolean;
  onRemove?: () => void;
};

export function PluginRow({ disabled = false, disabledLabel = "Connect", detail, enabled, enabledLabel = "Disconnect", onRemove, plugin, onToggle }: PluginRowProps) {
  const Icon = plugin.icon;
  const action = enabled ? enabledLabel : disabledLabel;
  return (
    <article className={styles.row}>
      <span className={styles.icon} style={{ "--plugin-color": plugin.color } as React.CSSProperties}><Icon aria-hidden="true" /></span>
      <span className={styles.copy}>
        <strong>{plugin.name}</strong>
        <small>{detail || plugin.description}</small>
      </span>
      <span className={styles.actions}>
        {onRemove ? <button aria-label={`Remove ${plugin.name}`} className={styles.remove} onClick={onRemove} title={`Remove ${plugin.name}`} type="button"><Trash2 aria-hidden="true" /></button> : null}
        <button aria-label={`${action} ${plugin.name}`} aria-checked={enabled} className={styles.switch} disabled={disabled} onClick={onToggle} role="switch" title={`${action} ${plugin.name}`} type="button"><span /></button>
      </span>
    </article>
  );
}
