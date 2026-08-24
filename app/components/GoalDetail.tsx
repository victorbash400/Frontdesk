"use client";

import { Check, Play, RotateCcw } from "lucide-react";
import { useState } from "react";

import type { PluginDefinition } from "../lib/pluginDirectory";
import type { GoalStatus, OperatorGoal } from "../types/goal";
import type { OperatorSkill } from "../types/skill";
import { GoalCapabilitySelector } from "./GoalCapabilitySelector";
import { GoalProgress } from "./GoalProgress";
import styles from "./GoalDetail.module.css";

type GoalDetailProps = {
  clientName: string;
  goal: OperatorGoal;
  plugins: PluginDefinition[];
  skills: OperatorSkill[];
  onStatusChange: (status: GoalStatus) => void;
  onSave: (update: Pick<OperatorGoal, "text" | "skillIds" | "pluginIds">) => void;
};

export function GoalDetail({ clientName, goal, plugins, skills, onStatusChange, onSave }: GoalDetailProps) {
  const [text, setText] = useState(goal.text);
  const [skillIds, setSkillIds] = useState(goal.skillIds);
  const [pluginIds, setPluginIds] = useState(goal.pluginIds);
  const [error, setError] = useState<string>();
  const changed = text.trim() !== goal.text || !sameIds(skillIds, goal.skillIds) || !sameIds(pluginIds, goal.pluginIds);

  function save() {
    try {
      onSave({ text, skillIds, pluginIds });
      setError(undefined);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save this goal.");
    }
  }

  function changeStatus(status: GoalStatus) {
    try {
      onStatusChange(status);
      setError(undefined);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not update this goal.");
    }
  }

  return (
    <article className={styles.detail}>
      <header><span><strong>{clientName}</strong><small>{statusLabel(goal.status)}</small></span>{goal.status === "ready" ? <button className={styles.primary} onClick={() => changeStatus("active")} type="button"><Play aria-hidden="true" />Start Goal</button> : null}{goal.status === "active" ? <button className={styles.primary} onClick={() => changeStatus("completed")} type="button"><Check aria-hidden="true" />Complete Goal</button> : null}{goal.status === "completed" ? <button onClick={() => changeStatus("active")} type="button"><RotateCcw aria-hidden="true" />Resume Goal</button> : null}</header>
      <textarea aria-label="Goal text" onChange={(event) => { setText(event.target.value); setError(undefined); }} spellCheck="true" value={text} />
      <GoalCapabilitySelector onPluginIdsChange={setPluginIds} onSkillIdsChange={setSkillIds} pluginIds={pluginIds} plugins={plugins} skillIds={skillIds} skills={skills} />
      <GoalProgress status={goal.status} />
      <footer>{error ? <small role="alert">{error}</small> : <small>Created {formatDate(goal.createdAt)}</small>}<button disabled={!changed || !text.trim()} onClick={save} type="button">Save Changes</button></footer>
    </article>
  );
}

function sameIds(left: string[], right: string[]) {
  return left.length === right.length && left.every((id) => right.includes(id));
}

function statusLabel(status: OperatorGoal["status"]) {
  if (status === "active") return "Active";
  if (status === "completed") return "Completed";
  return "Ready";
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
