import { CalendarDays, ContactRound, FileQuestion, FileText, HardDrive, ListChecks, Mail, Presentation, Sheet, Video } from "lucide-react";

import type { WorkspacePermission } from "../hooks/useGoogleWorkspaceConnection";
import type { PluginDefinition } from "../lib/pluginDirectory";
import { PluginRow } from "./PluginRow";


const icons = {
  "workspace.drive": HardDrive,
  "workspace.docs": FileText,
  "workspace.sheets": Sheet,
  "workspace.slides": Presentation,
  "workspace.gmail": Mail,
  "workspace.calendar": CalendarDays,
  "workspace.people": ContactRound,
  "workspace.tasks": ListChecks,
  "workspace.forms": FileQuestion,
  "workspace.meet": Video,
};

export function WorkspacePermissions({ connected, permissions, onChange }: { connected: boolean; permissions: WorkspacePermission[]; onChange: (permissionId: string, enabled: boolean) => void }) {
  return <>{permissions.map((permission) => {
    const plugin: PluginDefinition = { id: permission.id, name: permission.name, description: permission.description, group: "featured", color: "#6f6f6b", icon: icons[permission.id as keyof typeof icons] || FileText, permissions: [] };
    return <PluginRow disabled={!connected} enabled={connected && permission.enabled} key={permission.id} onToggle={() => onChange(permission.id, !permission.enabled)} plugin={plugin} />;
  })}</>;
}
