"use client";

import { ListFilter, Plus, UserRound } from "lucide-react";
import { useMemo, useState } from "react";

import { useGoals } from "../hooks/useGoals";
import { useGoogleWorkspaceConnection } from "../hooks/useGoogleWorkspaceConnection";
import { usePluginDirectory } from "../hooks/usePluginDirectory";
import { useSkillsLibrary } from "../hooks/useSkillsLibrary";
import { googleWorkspacePlugin, pluginDirectory } from "../lib/pluginDirectory";
import type { FileSystemNode } from "../types/filesystem";
import type { GoalStatus } from "../types/goal";
import { CreateGoalDialog } from "./CreateGoalDialog";
import { GoalList } from "./GoalList";
import styles from "./GoalsWorkspace.module.css";

type StatusFilter = GoalStatus | "all";
type SortMode = "newest" | "oldest" | "client";

type GoalsWorkspaceProps = {
  accountId: string;
  clients: FileSystemNode[];
};

const filters: Array<{ id: StatusFilter; label: string }> = [
  { id: "all", label: "All" },
  { id: "active", label: "Active" },
  { id: "ready", label: "Ready" },
  { id: "completed", label: "Completed" },
];

export function GoalsWorkspace({ accountId, clients }: GoalsWorkspaceProps) {
  const { createGoal, error, goals, loaded, setGoalStatus, updateGoal } = useGoals(accountId);
  const googleWorkspace = useGoogleWorkspaceConnection();
  const plugins = usePluginDirectory(accountId);
  const skills = useSkillsLibrary(accountId);
  const [status, setStatus] = useState<StatusFilter>("all");
  const [selectedClientId, setSelectedClientId] = useState("all");
  const [selectedGoalId, setSelectedGoalId] = useState<string>();
  const [sort, setSort] = useState<SortMode>("newest");
  const [creating, setCreating] = useState(false);
  const effectiveClientId = selectedClientId === "all" ? undefined : selectedClientId;
  const availablePlugins = useMemo(() => [
    ...pluginDirectory.filter((plugin) => plugins.enabledIds.has(plugin.id)),
    ...(googleWorkspace.connected ? [googleWorkspacePlugin] : []),
  ], [googleWorkspace.connected, plugins.enabledIds]);
  const workspaceError = error ?? plugins.error ?? googleWorkspace.error ?? skills.error;
  const visible = useMemo(() => {
    const clientIds = new Set(clients.map((client) => client.id));
    return goals.filter((goal) => clientIds.has(goal.clientId) && (!effectiveClientId || goal.clientId === effectiveClientId) && (status === "all" || goal.status === status)).sort((left, right) => {
    if (sort === "oldest") return left.createdAt.localeCompare(right.createdAt);
    if (sort === "client") return (clients.find((client) => client.id === left.clientId)?.name ?? "").localeCompare(clients.find((client) => client.id === right.clientId)?.name ?? "");
    return right.createdAt.localeCompare(left.createdAt);
    });
  }, [clients, effectiveClientId, goals, sort, status]);
  const panelTitle = status === "all" ? "All goals" : `${filters.find((filter) => filter.id === status)?.label ?? "Goals"} goals`;

  if (!loaded || !plugins.loaded || !skills.loaded) return null;

  return (
    <section aria-label="Goals" className={styles.goals}>
      <header><span><h1>Goals</h1><p>Goals across every client</p></span><button disabled={!clients.length} onClick={() => setCreating(true)} type="button"><Plus aria-hidden="true" />New Goal</button></header>
      <section className={styles.controls}>
        <nav aria-label="Goal status">{filters.map((filter) => <button aria-current={status === filter.id ? "page" : undefined} key={filter.id} onClick={() => setStatus(filter.id)} type="button">{filter.label}</button>)}</nav>
        <span>
          <label><UserRound aria-hidden="true" /><select aria-label="Filter goals by client" onChange={(event) => setSelectedClientId(event.target.value)} value={selectedClientId}><option value="all">All Clients</option>{clients.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}</select></label>
          <label><ListFilter aria-hidden="true" /><select aria-label="Sort goals" onChange={(event) => setSort(event.target.value as SortMode)} value={sort}><option value="newest">Newest</option><option value="oldest">Oldest</option><option value="client">Client</option></select></label>
        </span>
      </section>
      {workspaceError ? <p className={styles.error} role="alert">{workspaceError}</p> : null}
      <section className={styles.panel}>
        <header><span>{panelTitle}</span><small>{visible.length}</small></header>
        <section className={styles.sheet}>
          <GoalList clients={clients} goals={visible} onSave={updateGoal} onSelect={setSelectedGoalId} onStatusChange={setGoalStatus} plugins={availablePlugins} selectedId={selectedGoalId} skills={skills.skills} />
        </section>
      </section>
      <CreateGoalDialog clients={clients} onCancel={() => setCreating(false)} onSubmit={(goalClientId, text, skillIds, pluginIds) => { const goal = createGoal(goalClientId, text, skillIds, pluginIds); setSelectedGoalId(goal.id); setStatus("active"); setCreating(false); }} open={creating} plugins={availablePlugins} skills={skills.skills} />
    </section>
  );
}
