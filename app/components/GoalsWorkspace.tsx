"use client";

import { ListFilter, Plus, Trash2, UserRound } from "lucide-react";
import { useMemo, useState } from "react";

import { useGoals } from "../hooks/useGoals";
import { usePluginDirectory } from "../hooks/usePluginDirectory";
import { useSkillsLibrary } from "../hooks/useSkillsLibrary";
import { pluginDirectory } from "../lib/pluginDirectory";
import { skillCatalog } from "../lib/skillCatalog";
import type { FileSystemNode } from "../types/filesystem";
import type { GoalStatus } from "../types/goal";
import { CreateGoalDialog } from "./CreateGoalDialog";
import { DeleteGoalsDialog } from "./DeleteGoalsDialog";
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
  { id: "paused", label: "Paused" },
  { id: "completed", label: "Completed" },
];

export function GoalsWorkspace({ accountId, clients }: GoalsWorkspaceProps) {
  const { createGoal, deleteGoal, error, goals, liveUpdates, loaded, setGoalStatus } = useGoals();
  const plugins = usePluginDirectory(accountId);
  const skills = useSkillsLibrary(accountId);
  const [status, setStatus] = useState<StatusFilter>("all");
  const [selectedClientId, setSelectedClientId] = useState("all");
  const [selectedGoalId, setSelectedGoalId] = useState<string>();
  const [sort, setSort] = useState<SortMode>("newest");
  const [creating, setCreating] = useState(false);
  const [selecting, setSelecting] = useState(false);
  const [selectedGoalIds, setSelectedGoalIds] = useState<Set<string>>(new Set());
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const effectiveClientId = selectedClientId === "all" ? undefined : selectedClientId;
  const availablePlugins = useMemo(() => pluginDirectory.filter((plugin) => plugins.enabledIds.has(plugin.id)), [plugins.enabledIds]);
  const availableSkills = useMemo(() => {
    const savedIds = new Set(skills.skills.map((skill) => skill.id));
    const pluginSkills = skillCatalog
      .filter((skill) => skill.pluginId && plugins.enabledIds.has(skill.pluginId) && !savedIds.has(skill.id))
      .map((skill) => ({ ...skill, updatedAt: "" }));
    return [...skills.skills, ...pluginSkills];
  }, [plugins.enabledIds, skills.skills]);
  const workspaceError = error ?? plugins.error ?? skills.error;
  const visible = useMemo(() => {
    const clientIds = new Set(clients.map((client) => client.id));
    return goals.filter((goal) => clientIds.has(goal.clientId) && (!effectiveClientId || goal.clientId === effectiveClientId) && (status === "all" || goal.status === status)).sort((left, right) => {
    if (sort === "oldest") return left.createdAt.localeCompare(right.createdAt);
    if (sort === "client") return (clients.find((client) => client.id === left.clientId)?.name ?? "").localeCompare(clients.find((client) => client.id === right.clientId)?.name ?? "");
    return right.createdAt.localeCompare(left.createdAt);
    });
  }, [clients, effectiveClientId, goals, sort, status]);
  const panelTitle = status === "all" ? "All goals" : `${filters.find((filter) => filter.id === status)?.label ?? "Goals"} goals`;

  function leaveSelectionMode() {
    setSelecting(false);
    setSelectedGoalIds(new Set());
  }

  function toggleGoalSelection(id: string) {
    setSelectedGoalIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

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
        <header>
          <span>{panelTitle}</span>
          <span className={styles.panelActions}>
            <small>{selecting ? `${selectedGoalIds.size} selected` : visible.length}</small>
            {selecting ? <>
              <button className={styles.cancelSelection} onClick={leaveSelectionMode} type="button">Cancel</button>
              <button className={styles.deleteSelection} disabled={!selectedGoalIds.size} onClick={() => setConfirmingDelete(true)} type="button"><Trash2 aria-hidden="true" />Delete</button>
            </> : <button disabled={!visible.length} onClick={() => { setSelectedGoalId(undefined); setSelecting(true); }} type="button">Select</button>}
          </span>
        </header>
        <section className={styles.sheet}>
          <GoalList clients={clients} goals={visible} liveUpdates={liveUpdates} onDelete={async (id) => { await deleteGoal(id); setSelectedGoalId(undefined); }} onSelect={setSelectedGoalId} onStatusChange={setGoalStatus} onToggleSelection={toggleGoalSelection} plugins={availablePlugins} selectedId={selectedGoalId} selectedIds={selectedGoalIds} selecting={selecting} />
        </section>
      </section>
      <CreateGoalDialog clients={clients} onCancel={() => setCreating(false)} onSubmit={async (goalClientId, text, skillIds, pluginIds) => { const goal = await createGoal(goalClientId, text, skillIds, pluginIds); setSelectedGoalId(goal.id); setStatus("active"); setCreating(false); }} open={creating} plugins={availablePlugins} skills={availableSkills} />
      <DeleteGoalsDialog count={selectedGoalIds.size} onCancel={() => setConfirmingDelete(false)} onConfirm={async () => {
        const ids = [...selectedGoalIds];
        const results = await Promise.allSettled(ids.map(deleteGoal));
        const failedIds = ids.filter((_, index) => results[index].status === "rejected");
        if (failedIds.length) {
          setSelectedGoalIds(new Set(failedIds));
          throw new Error(`Deleted ${ids.length - failedIds.length} of ${ids.length} goals. ${failedIds.length} could not be deleted.`);
        }
        setConfirmingDelete(false);
        leaveSelectionMode();
      }} open={confirmingDelete} />
    </section>
  );
}
