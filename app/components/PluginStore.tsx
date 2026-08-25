"use client";

import { Search } from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";

import { usePluginDirectory } from "../hooks/usePluginDirectory";
import { pluginDirectory, type PluginDefinition } from "../lib/pluginDirectory";
import { AvailablePluginGroups } from "./AvailablePluginGroups";
import { ExternalPluginSection } from "./ExternalPluginSection";
import { WorkspaceSection } from "./WorkspaceSection";
import styles from "./PluginStore.module.css";


export function PluginStore({ accountId }: { accountId: string }) {
  const directory = usePluginDirectory(accountId);
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

  const add = async (plugin: PluginDefinition) => {
    try {
      await directory.add(plugin.id);
    } catch (reason) {
      directory.setError(reason instanceof Error ? reason.message : "Could not add plugin");
    }
  };

  if (!directory.loaded) return <p className={styles.loading}>Loading plugins…</p>;

  return (
    <section aria-label="Plugin store" className={`${styles.store} ${view === "directory" ? styles.directory : ""}`}>
      <header className={styles.heading}>
        <span><h1>{view === "plugins" ? "Plugins" : "Plugin directory"}</h1>{view === "plugins" ? <p>Manage your connected services.</p> : null}</span>
        <button className={styles.browse} onClick={() => { setQuery(""); setView(view === "plugins" ? "directory" : "plugins"); }} type="button">{view === "plugins" ? "Browse directory" : "Back to plugins"}</button>
      </header>
      <label className={styles.search}><Search aria-hidden="true" /><input aria-label="Search plugins" onChange={(event) => setQuery(event.target.value)} placeholder="Search plugins" type="search" value={query} /></label>
      {directory.error ? <p className={styles.error} role="alert">{directory.error}</p> : null}
      {view === "plugins" ? <>
        {workspace?.state.installed ? <WorkspaceSection accountId={accountId} onRemove={() => void directory.remove("google-workspace")} /> : null}
        {installed.map(({ plugin, state }) => <ExternalPluginSection
            key={plugin.id}
            onConnect={() => void directory.connect(plugin.id).catch((reason) => directory.setError(reason instanceof Error ? reason.message : `Could not connect ${plugin.name}`))}
            onDisconnect={() => void directory.disconnect(plugin.id).catch((reason) => directory.setError(reason instanceof Error ? reason.message : `Could not disconnect ${plugin.name}`))}
            onPermissionChange={(permissionId, enabled) => void directory.setPermission(plugin.id, permissionId, enabled).catch((reason) => directory.setError(reason instanceof Error ? reason.message : `Could not update ${plugin.name}`))}
            onRefresh={() => void directory.refresh()}
            onRemove={() => void directory.remove(plugin.id).catch((reason) => directory.setError(reason instanceof Error ? reason.message : `Could not remove ${plugin.name}`))}
            plugin={plugin}
            state={state}
          />)}
        {!installed.length && !workspace?.state.installed ? <p className={styles.empty}>No plugins added. Browse the directory to add one.</p> : null}
      </> : <AvailablePluginGroups entries={entries} onAdd={(plugin) => void add(plugin)} />}
    </section>
  );
}
