"use client";

import { Bell, ListFilter, Plus, SquarePen, Trash2, UserRound } from "lucide-react";
import { useMemo, useState } from "react";

import { useGoals } from "../hooks/useGoals";
import { useGoalQuestions } from "../hooks/useGoalQuestions";
import { usePluginDirectory } from "../hooks/usePluginDirectory";
import { useSkillsLibrary } from "../hooks/useSkillsLibrary";
import { pluginDirectory } from "../lib/pluginDirectory";
import type { FileSystemNode } from "../types/filesystem";
import type { GoalStatus } from "../types/goal";
import { CreateGoalDialog } from "./CreateGoalDialog";
import { DeleteGoalsDialog } from "./DeleteGoalsDialog";
import { GoalList } from "./GoalList";
import { GoalQuestionList } from "./GoalQuestionList";
import { GoalsChatPanel } from "./GoalsChatPanel";
import { GoalPreviewPane } from "./GoalPreviewPane";
import styles from "./GoalsWorkspace.module.css";

type StatusFilter = GoalStatus | "all" | "questions";
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
  { id: "questions", label: "Questions" },
];

export function GoalsWorkspace({ accountId, clients }: GoalsWorkspaceProps) {
  const { createGoal, deleteGoal, error, goals, liveUpdates, loaded, runtimeOnline, setGoalStatus } = useGoals();
  const questions = useGoalQuestions();
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
  const [chatOpen, setChatOpen] = useState(false);
  const effectiveClientId = selectedClientId === "all" ? undefined : selectedClientId;
  const availablePlugins = useMemo(() => pluginDirectory.filter((plugin) => plugins.enabledIds.has(plugin.id)), [plugins.enabledIds]);
  const availableSkills = useMemo(() => skills.skills.filter((skill) => skill.requiredPluginIds.every((pluginId) => plugins.enabledIds.has(pluginId))), [plugins.enabledIds, skills.skills]);
  const workspaceError = error ?? plugins.error ?? skills.error;
  const visible = useMemo(() => {
    const clientIds = new Set(clients.map((client) => client.id));
    return goals.filter((goal) => clientIds.has(goal.clientId) && (!effectiveClientId || goal.clientId === effectiveClientId) && (status === "all" || status === "questions" || goal.status === status)).sort((left, right) => {
    if (sort === "oldest") return left.createdAt.localeCompare(right.createdAt);
    if (sort === "client") return (clients.find((client) => client.id === left.clientId)?.name ?? "").localeCompare(clients.find((client) => client.id === right.clientId)?.name ?? "");
    return right.createdAt.localeCompare(left.createdAt);
    });
  }, [clients, effectiveClientId, goals, sort, status]);
  const visibleQuestions = questions.questions.filter((question) => !effectiveClientId || question.clientId === effectiveClientId);
  const panelTitle = status === "questions" ? "Questions" : status === "all" ? "All goals" : `${filters.find((filter) => filter.id === status)?.label ?? "Goals"} goals`;
  const previewGoal = visible.find((goal) => goal.id === selectedGoalId) ?? visible.find((goal) => ["running", "blocked"].includes(liveUpdates[goal.id]?.state ?? goal.runState));

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
        <nav aria-label="Goal status">{filters.map((filter) => <button aria-current={status === filter.id ? "page" : undefined} key={filter.id} onClick={() => setStatus(filter.id)} type="button">{filter.label}{filter.id === "questions" && questions.questions.length ? <Bell aria-label={`${questions.questions.length} open questions`} className={styles.questionAlert} /> : null}</button>)}</nav>
        <span>
          <label><UserRound aria-hidden="true" /><select aria-label="Filter goals by client" onChange={(event) => setSelectedClientId(event.target.value)} value={selectedClientId}><option value="all">All Clients</option>{clients.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}</select></label>
          <label><ListFilter aria-hidden="true" /><select aria-label="Sort goals" onChange={(event) => setSort(event.target.value as SortMode)} value={sort}><option value="newest">Newest</option><option value="oldest">Oldest</option><option value="client">Client</option></select></label>
        </span>
      </section>
      {workspaceError ? <p className={styles.error} role="alert">{workspaceError}</p> : null}
      <section className={styles.panel}>
        <header>
          <span className={styles.panelTitle}>{panelTitle}<button aria-label={chatOpen ? "Close Goals chat" : "Open Goals chat"} aria-pressed={chatOpen} onClick={() => setChatOpen((current) => !current)} title="Goals chat" type="button"><SquarePen aria-hidden="true" /></button></span>
          <span className={styles.panelActions}>
            <small>{selecting ? `${selectedGoalIds.size} selected` : status === "questions" ? visibleQuestions.length : visible.length}</small>
            {status === "questions" ? null : selecting ? <>
              <button className={styles.cancelSelection} onClick={leaveSelectionMode} type="button">Cancel</button>
              <button className={styles.deleteSelection} disabled={!selectedGoalIds.size} onClick={() => setConfirmingDelete(true)} type="button"><Trash2 aria-hidden="true" />Delete</button>
            </> : <button disabled={!visible.length} onClick={() => { setSelectedGoalId(undefined); setSelecting(true); }} type="button">Select</button>}
          </span>
        </header>
        <section className={styles.panelBody}>
          <section className={styles.sheet}>{status === "questions"
            ? <GoalQuestionList clients={clients} error={questions.error} onAnswer={questions.answer} questions={visibleQuestions} />
            : <GoalList clients={clients} goals={visible} liveUpdates={liveUpdates} onDelete={async (id) => { await deleteGoal(id); setSelectedGoalId(undefined); }} onSelect={setSelectedGoalId} onStatusChange={setGoalStatus} onToggleSelection={toggleGoalSelection} plugins={availablePlugins} runtimeOnline={runtimeOnline} selectedId={selectedGoalId} selectedIds={selectedGoalIds} selecting={selecting} />}
          </section>
          {!chatOpen && status !== "questions" ? <GoalPreviewPane goal={previewGoal} /> : null}
          <GoalsChatPanel accountId={accountId} open={chatOpen} />
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
