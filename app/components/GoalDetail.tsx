"use client";

import { Pause, Play, Trash2 } from "lucide-react";
import { useState } from "react";

import type { PluginDefinition } from "../lib/pluginDirectory";
import type { GoalLiveUpdate, GoalStatus, OperatorGoal } from "../types/goal";
import { DeleteGoalDialog } from "./DeleteGoalDialog";
import { GoalPluginIcons } from "./GoalPluginIcons";
import { GoalPlanningStatus } from "./GoalPlanningStatus";
import { GoalTaskBoard } from "./GoalTaskBoard";
import styles from "./GoalDetail.module.css";

type GoalDetailProps = { goal: OperatorGoal; liveUpdate?: GoalLiveUpdate; plugins: PluginDefinition[]; runtimeOnline: boolean; onDelete: () => Promise<void>; onStatusChange: (status: GoalStatus) => void };

export function GoalDetail({ goal, liveUpdate, plugins, runtimeOnline, onDelete, onStatusChange }: GoalDetailProps) {
  const [deleting, setDeleting] = useState(false);
  const currentLiveUpdate = goal.status === "completed" ? undefined : liveUpdate;
  const runState = !runtimeOnline && ["planning", "queued", "running"].includes(goal.runState) ? "paused" : currentLiveUpdate?.state ?? goal.runState;
  const canPause = goal.status === "active" && (runState === "planning" || runState === "queued" || runState === "running");
  return <><article className={styles.detail}>
    {runState === "planning" && goal.currentStep ? <GoalPlanningStatus currentStep={goal.currentStep} /> : null}
    <GoalTaskBoard runtimeOnline={runtimeOnline} tasks={goal.assignments} />
    <footer>
      <GoalPluginIcons pluginIds={goal.pluginIds} plugins={plugins} />
      <span className={styles.actions}>
        {goal.status !== "completed" && (canPause ? <button aria-label="Pause goal" onClick={() => onStatusChange("paused")} title="Pause" type="button"><Pause aria-hidden="true" /></button> : <button aria-label="Resume goal" onClick={() => onStatusChange("active")} title="Resume" type="button"><Play aria-hidden="true" /></button>)}
        <button aria-label="Delete goal" className={styles.delete} onClick={() => setDeleting(true)} title="Delete" type="button"><Trash2 aria-hidden="true" /></button>
      </span>
    </footer>
  </article><DeleteGoalDialog goal={goal.text} onCancel={() => setDeleting(false)} onConfirm={onDelete} open={deleting} /></>;
}
