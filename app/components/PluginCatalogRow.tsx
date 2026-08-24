import type { PluginDefinition, PluginState } from "../lib/pluginDirectory";
import { PluginIcon } from "./PluginIcon";
import styles from "./PluginCatalogRow.module.css";


export function PluginCatalogRow({ onAdd, plugin, state }: { onAdd: () => void; plugin: PluginDefinition; state: PluginState }) {
  return (
    <article className={styles.row}>
      <PluginIcon plugin={plugin} />
      <span><strong>{plugin.name}</strong><small>{plugin.description}</small></span>
      <button onClick={onAdd} type="button">Add</button>
      {!state.connection_supported && state.setup_message ? <p>{state.setup_message}</p> : null}
    </article>
  );
}
