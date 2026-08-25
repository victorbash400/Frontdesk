import type { PluginDefinition } from "../lib/pluginDirectory";
import { PluginIcon } from "./PluginIcon";
import styles from "./GoalPluginIcons.module.css";

export function GoalPluginIcons({ pluginIds, plugins }: { pluginIds: string[]; plugins: PluginDefinition[] }) {
  const selected = pluginIds.flatMap((id) => { const plugin = plugins.find((item) => item.id === id); return plugin ? [plugin] : []; });
  if (!selected.length) return null;
  return <span aria-label="Goal plugins" className={styles.plugins}>{selected.map((plugin) => <span key={plugin.id} title={plugin.name}><PluginIcon plugin={plugin} variant="row" /></span>)}</span>;
}
