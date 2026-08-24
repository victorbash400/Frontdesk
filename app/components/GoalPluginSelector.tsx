import { Plug } from "lucide-react";

import type { PluginDefinition } from "../lib/pluginDirectory";
import { PluginRow } from "./PluginRow";
import styles from "./GoalPluginSelector.module.css";

type GoalPluginSelectorProps = {
  plugins: PluginDefinition[];
  selectedIds: string[];
  onChange: (ids: string[]) => void;
};

export function GoalPluginSelector({ plugins, selectedIds, onChange }: GoalPluginSelectorProps) {
  return (
    <section aria-label="Goal plugins" className={styles.selector}>
      <header><strong>Plugins</strong><small>Connected tools Front Desk can use</small></header>
      <section className={styles.options}>
        {plugins.map((plugin) => <PluginRow disabledLabel="Attach" enabled={selectedIds.includes(plugin.id)} enabledLabel="Remove" key={plugin.id} onToggle={() => onChange(toggleId(selectedIds, plugin.id))} plugin={plugin} />)}
        {!plugins.length ? <p><Plug aria-hidden="true" />Connect plugins from the Plugins workspace</p> : null}
      </section>
    </section>
  );
}

function toggleId(ids: string[], id: string) {
  return ids.includes(id) ? ids.filter((value) => value !== id) : [...ids, id];
}
