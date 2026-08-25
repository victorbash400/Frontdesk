import { pluginGroups, type PluginDefinition, type PluginState } from "../lib/pluginDirectory";
import { PluginCatalogRow } from "./PluginCatalogRow";
import styles from "./AvailablePluginGroups.module.css";


export function AvailablePluginGroups({ entries, onAdd }: { entries: Array<{ plugin: PluginDefinition; state: PluginState }>; onAdd: (plugin: PluginDefinition) => void }) {
  if (!entries.length) return <p className={styles.empty}>No other plugins match this search.</p>;
  return <section aria-label="Plugin directory" className={styles.section}>
    {pluginGroups.map((group) => {
      const groupEntries = entries.filter(({ plugin }) => plugin.group === group.id);
      if (!groupEntries.length) return null;
      return <section className={styles.group} key={group.id}>
        <h2>{group.label}</h2>
        <ul>{groupEntries.map(({ plugin, state }) => <PluginCatalogRow key={plugin.id} onAdd={() => onAdd(plugin)} plugin={plugin} state={state} />)}</ul>
      </section>;
    })}
  </section>;
}
