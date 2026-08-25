import type { PluginDefinition, PluginPermissionState } from "../lib/pluginDirectory";
import { PluginRow } from "./PluginRow";


export function PluginFeaturePermissions({ connected, onChange, permissions, plugin }: { connected: boolean; onChange: (permissionId: string, enabled: boolean) => void; permissions: PluginPermissionState[]; plugin: PluginDefinition }) {
  return <>{(plugin.features || []).map((feature) => {
    const permission = permissions.find((item) => item.id === feature.id);
    const row: PluginDefinition = { id: feature.id, name: feature.name, description: feature.description, group: plugin.group, color: plugin.color, icon: feature.icon, permissions: [] };
    return <PluginRow disabled={!connected} enabled={connected && (permission?.enabled ?? true)} key={feature.id} onToggle={() => onChange(feature.id, !(permission?.enabled ?? true))} plugin={row} />;
  })}</>;
}
