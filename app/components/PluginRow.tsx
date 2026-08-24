import type { PluginDefinition } from "../lib/pluginDirectory";
import styles from "./PluginRow.module.css";

type PluginRowProps = {
  enabled: boolean;
  plugin: PluginDefinition;
  onToggle: () => void;
  enabledLabel?: string;
  disabledLabel?: string;
};

export function PluginRow({ disabledLabel = "Connect", enabled, enabledLabel = "Disconnect", plugin, onToggle }: PluginRowProps) {
  const Icon = plugin.icon;
  const action = enabled ? enabledLabel : disabledLabel;
  return (
    <article className={styles.row}>
      <span className={styles.icon} style={{ "--plugin-color": plugin.color } as React.CSSProperties}><Icon aria-hidden="true" /></span>
      <span className={styles.copy}>
        <strong>{plugin.name}</strong>
        <small>{plugin.description}</small>
      </span>
      <button aria-label={`${action} ${plugin.name}`} aria-checked={enabled} className={styles.switch} onClick={onToggle} role="switch" title={`${action} ${plugin.name}`} type="button"><span /></button>
    </article>
  );
}
