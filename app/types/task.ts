export type TaskStatus = "ready" | "active" | "completed";

export type OperatorTask = {
  id: string;
  clientId: string;
  text: string;
  status: TaskStatus;
  createdAt: string;
  updatedAt: string;
  startedAt: string | null;
  completedAt: string | null;
};
