export type GoalStatus = "ready" | "active" | "completed";

export type OperatorGoal = {
  id: string;
  clientId: string;
  text: string;
  skillIds: string[];
  pluginIds: string[];
  status: GoalStatus;
  createdAt: string;
  updatedAt: string;
  startedAt: string | null;
  completedAt: string | null;
};
