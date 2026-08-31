import { ChevronDown } from "lucide-react";

import type { PluginDefinition, PluginState } from "../lib/pluginDirectory";
import { BrowserExtensionAccess } from "./BrowserExtensionAccess";
import { GitHubRepositoryAccess } from "./GitHubRepositoryAccess";
import { PluginFeaturePermissions } from "./PluginFeaturePermissions";
import { PluginIcon } from "./PluginIcon";
import styles from "./ExternalPluginSection.module.css";


type ExternalPluginSectionProps = {
  onConnect: () => void;
  onDisconnect: () => void;
  onPermissionChange: (permissionId: string, enabled: boolean) => void;
  onRefresh: () => void;
  onRemove: () => void;
  plugin: PluginDefinition;
  state: PluginState;
};

export function ExternalPluginSection({ onConnect, onDisconnect, onPermissionChange, onRefresh, onRemove, plugin, state }: ExternalPluginSectionProps) {
  const connectionAvailable = state.connected || state.connection_supported;
  const isManaged = state.connection_type === "managed";
  const overview = state.connected
    ? `${state.account_label || "Connected"}${state.tool_count ? ` · ${state.tool_count} tools` : ""}${plugin.id === "github" ? ` · ${state.repository_count || 0} repositories` : ""}`
    : "Not connected";

  return (
    <section className={styles.section}>
      <h2>{plugin.name}</h2>
      <details className={styles.plugin}>
        <summary>
          <PluginIcon plugin={plugin} variant="row" />
          <span className={styles.copy}><strong>{plugin.description}</strong><small>{overview}</small></span>
          <span className={state.connected ? styles.connected : styles.disconnected}>{state.connected ? "Connected" : "Not connected"}</span>
          <ChevronDown aria-hidden="true" className={styles.chevron} />
        </summary>
        <section aria-label={`${plugin.name} connection settings`} className={styles.settings}>
          {state.connection_type === "extension" ? <BrowserExtensionAccess /> : <header>
            <span><strong>Connection</strong><small>{state.connected ? state.account_label || `${plugin.name} is connected` : state.setup_message || `Connect ${plugin.name} to Front Desk`}</small></span>
            {!isManaged ? <button disabled={!connectionAvailable} onClick={state.connected ? onDisconnect : onConnect} type="button">{state.connected ? "Disconnect" : "Connect"}</button> : null}
          </header>}
          {state.connected ? <>
            <PluginFeaturePermissions connected onChange={onPermissionChange} permissions={state.permissions} plugin={plugin} />
            {plugin.id === "github" ? <GitHubRepositoryAccess onSaved={onRefresh} /> : null}
          </> : null}
          <footer><button onClick={onRemove} type="button">Remove plugin</button></footer>
        </section>
      </details>
    </section>
  );
}
