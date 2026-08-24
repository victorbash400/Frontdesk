"use client";

import { Search } from "lucide-react";
import { useDeferredValue, useState } from "react";

import { usePluginDirectory } from "../hooks/usePluginDirectory";
import { useGoogleWorkspaceConnection } from "../hooks/useGoogleWorkspaceConnection";
import { pluginDirectory, type PluginCategory, type PluginDefinition } from "../lib/pluginDirectory";
import { PluginConnectionDialog } from "./PluginConnectionDialog";
import { PluginRow } from "./PluginRow";
import styles from "./PluginStore.module.css";

const categories: Array<{ id: PluginCategory; label: string }> = [
  { id: "plugins", label: "Plugins" },
  { id: "apps", label: "Apps" },
  { id: "mcps", label: "MCPs" },
];
const googlePluginIds = new Set(["gmail", "google-drive", "calendar"]);

export function PluginStore({ accountId }: { accountId: string }) {
  const { enabledIds, error, loaded, toggle } = usePluginDirectory(accountId);
  const google = useGoogleWorkspaceConnection();
  const [connectionError, setConnectionError] = useState<string>();
  const [category, setCategory] = useState<PluginCategory>("plugins");
  const [pendingPlugin, setPendingPlugin] = useState<PluginDefinition>();
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query.trim().toLocaleLowerCase());
  const visible = pluginDirectory.filter((plugin) => plugin.category === category && (!deferredQuery || `${plugin.name} ${plugin.description}`.toLocaleLowerCase().includes(deferredQuery)));

  if (!loaded) return null;

  return (
    <section aria-label="Plugin directory" className={styles.store}>
      <header>
        <span><h1>Plugins</h1><p>Connect the tools Front Desk can use</p></span>
        <label><Search aria-hidden="true" /><input aria-label="Search plugins" onChange={(event) => setQuery(event.target.value)} placeholder="Search plugins" type="search" value={query} /></label>
      </header>
      <nav aria-label="Plugin categories">
        {categories.map((item) => {
          const count = pluginDirectory.filter((plugin) => plugin.category === item.id).length;
          return <button aria-current={category === item.id ? "page" : undefined} key={item.id} onClick={() => setCategory(item.id)} type="button">{item.label} <small>{count}</small></button>;
        })}
      </nav>
      {error || google.error || connectionError ? <p className={styles.error} role="alert">{connectionError || google.error || error}</p> : null}
      <section className={styles.list}>
        {visible.map((plugin) => <PluginRow enabled={googlePluginIds.has(plugin.id) ? google.connected : enabledIds.has(plugin.id)} key={plugin.id} onToggle={() => setPendingPlugin(plugin)} plugin={plugin} />)}
      </section>
      <PluginConnectionDialog
        connected={pendingPlugin ? googlePluginIds.has(pendingPlugin.id) ? google.connected : enabledIds.has(pendingPlugin.id) : false}
        onCancel={() => setPendingPlugin(undefined)}
        onConfirm={() => {
          if (!pendingPlugin) return;
          if (googlePluginIds.has(pendingPlugin.id)) {
            const action = google.connected ? google.disconnect() : google.connect();
            void action.catch((reason) => setConnectionError(reason instanceof Error ? reason.message : "Could not update Google Workspace"));
            setPendingPlugin(undefined);
            return;
          }
          toggle(pendingPlugin.id);
          setPendingPlugin(undefined);
        }}
        plugin={pendingPlugin}
      />
    </section>
  );
}
