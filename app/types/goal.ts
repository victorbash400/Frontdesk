export type GoalStatus = "active" | "paused" | "completed";

export type GoalActivity = { id: string; kind: string; summary: string; evidence: Array<Record<string, unknown>>; createdAt: string };
export type GoalPreviewTarget = { kind: "workspace" | "browser"; resource_id: string; title?: string; mime_type?: string; revision?: string };
export type GoalTaskUpdate = { id: string; phase: string; progress: number; message: string; nextStep: string; createdAt: string };
export type GoalAssignment = { id: string; title: string; instruction: string; status: string; phase: string; progress: number; currentStep: string; nextStep: string; dependsOn: string[]; requiredInputs: string[]; expectedOutputs: string[]; previewTarget: GoalPreviewTarget | null; updates: GoalTaskUpdate[]; report: string; evidence: Array<Record<string, unknown>>; createdAt: string; startedAt: string | null; finishedAt: string | null };
export type GoalAutomation = { id: string; instruction: string; intervalSeconds: number; timezone: string; nextRunAt: string; enabled: boolean; createdAt: string };
export type GoalRunState = "idle" | "planning" | "queued" | "running" | "blocked" | "paused" | "completed" | "failed" | "cancelled";
export type GoalToolActivity = { id?: string; taskId?: string; message: string; name: string; service: string; status: "running" | "done" | "error" };
export type GoalLiveUpdate = { state: GoalRunState; summary?: string; tool?: GoalToolActivity };

export type OperatorGoal = {
  id: string;
  clientId: string;
  text: string;
  situation: string;
  skillIds: string[];
  pluginIds: string[];
  status: GoalStatus;
  runState: GoalRunState;
  currentStep: string;
  version: number;
  createdAt: string;
  updatedAt: string;
  startedAt: string | null;
  completedAt: string | null;
  activities: GoalActivity[];
  assignments: GoalAssignment[];
  automations: GoalAutomation[];
};
