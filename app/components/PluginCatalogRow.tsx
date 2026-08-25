import type { PluginDefinition, PluginState } from "../lib/pluginDirectory";
import { PluginIcon } from "./PluginIcon";
import styles from "./PluginCatalogRow.module.css";


export function PluginCatalogRow({ onAdd, plugin, state }: { onAdd: () => void; plugin: PluginDefinition; state: PluginState }) {
  const comingLater = state.connection_type === "extension" && !state.connection_supported;
  return (
    <li className={styles.row}>
      <PluginIcon plugin={plugin} />
      <span><strong>{plugin.name}</strong><small>{plugin.description}</small></span>
      <button disabled={state.installed || comingLater} onClick={onAdd} type="button">{state.installed ? "Added" : comingLater ? "Coming later" : "Add"}</button>
      {!comingLater && !state.connection_supported && state.setup_message ? <p>{state.setup_message}</p> : null}
    </li>
  );
}
