export type GoalStatus = "active" | "paused" | "completed";

export type GoalActivity = { id: string; kind: string; summary: string; evidence: Array<Record<string, unknown>>; createdAt: string };
export type GoalAssignment = { id: string; instruction: string; status: string; report: string; evidence: Array<Record<string, unknown>>; createdAt: string; startedAt: string | null; finishedAt: string | null };
export type GoalAutomation = { id: string; instruction: string; intervalSeconds: number; timezone: string; nextRunAt: string; enabled: boolean; createdAt: string };
export type GoalRunState = "idle" | "queued" | "running" | "blocked" | "paused" | "completed" | "failed" | "cancelled";
export type GoalLiveUpdate = { state: GoalRunState; summary?: string };

export type OperatorGoal = {
  id: string;
  clientId: string;
  text: string;
  situation: string;
  skillIds: string[];
  pluginIds: string[];
  status: GoalStatus;
  runState: GoalRunState;
  version: number;
  createdAt: string;
  updatedAt: string;
  startedAt: string | null;
  completedAt: string | null;
  activities: GoalActivity[];
  assignments: GoalAssignment[];
  automations: GoalAutomation[];
};
