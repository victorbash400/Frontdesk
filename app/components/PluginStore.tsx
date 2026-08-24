"use client";

import { Search } from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";

import { usePluginDirectory } from "../hooks/usePluginDirectory";
import { pluginDirectory, type PluginDefinition, type PluginState } from "../lib/pluginDirectory";
import { AvailablePluginGroups } from "./AvailablePluginGroups";
import { PluginConnectionDialog } from "./PluginConnectionDialog";
import { PluginRow } from "./PluginRow";
import { PluginSection } from "./PluginSection";
import { WorkspaceSection } from "./WorkspaceSection";
import styles from "./PluginStore.module.css";


export function PluginStore({ accountId }: { accountId: string }) {
  const directory = usePluginDirectory(accountId);
  const [pendingPlugin, setPendingPlugin] = useState<PluginDefinition>();
  const [view, setView] = useState<"plugins" | "directory">("plugins");
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query.trim().toLocaleLowerCase());
  const stateById = useMemo(() => new Map(directory.plugins.map((state) => [state.id, state])), [directory.plugins]);
  const entries = pluginDirectory
    .filter((plugin) => !deferredQuery || `${plugin.name} ${plugin.description}`.toLocaleLowerCase().includes(deferredQuery))
    .flatMap((plugin) => {
      const state = stateById.get(plugin.id);
      return state ? [{ plugin, state }] : [];
    });
  const workspace = entries.find(({ plugin }) => plugin.id === "google-workspace");
  const installed = entries.filter(({ plugin, state }) => plugin.id !== "google-workspace" && state.installed);
  const pendingState = pendingPlugin ? stateById.get(pendingPlugin.id) : undefined;

  const add = async (plugin: PluginDefinition, state: PluginState) => {
    try {
      await directory.add(plugin.id);
      if (state.connection_type === "mcp" && state.connection_supported) setPendingPlugin(plugin);
    } catch (reason) {
      directory.setError(reason instanceof Error ? reason.message : "Could not add plugin");
    }
  };

  if (!directory.loaded) return <p className={styles.loading}>Loading plugins…</p>;

  return (
    <section aria-label="Plugin store" className={styles.store}>
      <header className={styles.heading}>
        <span><h1>{view === "plugins" ? "Plugins" : "Plugin directory"}</h1><p>{view === "plugins" ? "Manage the tools Front Desk can use." : "Add tools to Front Desk, then connect the account they should use."}</p></span>
        <button className={styles.browse} onClick={() => { setQuery(""); setView(view === "plugins" ? "directory" : "plugins"); }} type="button">{view === "plugins" ? "Browse directory" : "Back to plugins"}</button>
      </header>
      <label className={styles.search}><Search aria-hidden="true" /><input aria-label="Search plugins" onChange={(event) => setQuery(event.target.value)} placeholder="Search plugins" type="search" value={query} /></label>
      {directory.error ? <p className={styles.error} role="alert">{directory.error}</p> : null}
      {view === "plugins" ? <>
        {workspace?.state.installed ? <WorkspaceSection accountId={accountId} onRemove={() => void directory.remove("google-workspace")} /> : null}
        {installed.length ? <PluginSection title="Plugins">
          {installed.map(({ plugin, state }) => <PluginRow
            detail={state.connected ? `${state.account_label || plugin.description}${state.tool_count ? ` · ${state.tool_count} tools` : ""}` : state.setup_message || "Added, not connected"}
            enabled={state.connected}
            key={plugin.id}
            onRemove={() => void directory.remove(plugin.id)}
            onToggle={() => setPendingPlugin(plugin)}
            plugin={plugin}
          />)}
        </PluginSection> : !workspace?.state.installed ? <p className={styles.empty}>No plugins added. Browse the directory to add one.</p> : null}
      </> : <AvailablePluginGroups entries={entries} onAdd={(plugin, state) => void add(plugin, state)} />}
      <PluginConnectionDialog
        connected={pendingState?.connected || false}
        onCancel={() => setPendingPlugin(undefined)}
        onConfirm={() => {
          if (!pendingPlugin || !pendingState) return;
          const action = pendingState.connected ? directory.disconnect(pendingPlugin.id) : directory.connect(pendingPlugin.id);
          void action.catch((reason) => directory.setError(reason instanceof Error ? reason.message : "Could not update plugins"));
          setPendingPlugin(undefined);
        }}
        plugin={pendingPlugin}
      />
    </section>
  );
}
