import type { PluginDefinition } from "../lib/pluginDirectory";
import { PluginIcon } from "./PluginIcon";
import styles from "./PluginConnectionProfile.module.css";


type PluginConnectionProfileProps = {
  accountLabel?: string | null;
  connected: boolean;
  connectionSupported: boolean;
  onConnect: () => void;
  onDisconnect: () => void;
  plugin: PluginDefinition;
  setupMessage?: string | null;
};

export function PluginConnectionProfile({ accountLabel, connected, connectionSupported, onConnect, onDisconnect, plugin, setupMessage }: PluginConnectionProfileProps) {
  return (
    <section aria-label={`${plugin.name} account`} className={styles.profile}>
      <PluginIcon plugin={plugin} variant="profile" />
      <span className={styles.identity}>
        <strong>{plugin.name}</strong>
        <span>{connected ? accountLabel || "Connected account" : setupMessage || `Connect ${plugin.name} to Front Desk`}</span>
      </span>
      <button disabled={!connected && !connectionSupported} onClick={connected ? onDisconnect : onConnect} type="button">{connected ? "Disconnect" : "Connect"}</button>
    </section>
  );
}
