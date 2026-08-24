import type { PluginDefinition } from "../lib/pluginDirectory";
import styles from "./PluginIcon.module.css";


export function PluginIcon({ plugin }: { plugin: PluginDefinition }) {
  const Icon = plugin.icon;
  return <span className={styles.icon} style={{ "--plugin-color": plugin.color } as React.CSSProperties}><Icon aria-hidden="true" /></span>;
}
