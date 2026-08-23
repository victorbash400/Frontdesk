"use client";

import { ListFilter, Plus, UserRound } from "lucide-react";
import { useMemo, useState } from "react";

import { useTasks } from "../hooks/useTasks";
import type { FileSystemNode } from "../types/filesystem";
import type { TaskStatus } from "../types/task";
import { CreateTaskDialog } from "./CreateTaskDialog";
import { TaskDetail } from "./TaskDetail";
import { TaskList } from "./TaskList";
import styles from "./TasksWorkspace.module.css";

type StatusFilter = TaskStatus | "all";
type SortMode = "newest" | "oldest" | "client";

type TasksWorkspaceProps = {
  clients: FileSystemNode[];
};

const filters: Array<{ id: StatusFilter; label: string }> = [
  { id: "active", label: "Active" },
  { id: "ready", label: "Ready" },
  { id: "completed", label: "Completed" },
  { id: "all", label: "All" },
];

export function TasksWorkspace({ clients }: TasksWorkspaceProps) {
  const { createTask, error, loaded, setTaskStatus, tasks, updateTaskText } = useTasks();
  const [status, setStatus] = useState<StatusFilter>("active");
  const [selectedClientId, setSelectedClientId] = useState("all");
  const [selectedTaskId, setSelectedTaskId] = useState<string>();
  const [sort, setSort] = useState<SortMode>("newest");
  const [creating, setCreating] = useState(false);
  const effectiveClientId = selectedClientId === "all" ? undefined : selectedClientId;
  const visible = useMemo(() => {
    const clientIds = new Set(clients.map((client) => client.id));
    return tasks.filter((task) => clientIds.has(task.clientId) && (!effectiveClientId || task.clientId === effectiveClientId) && (status === "all" || task.status === status)).sort((left, right) => {
    if (sort === "oldest") return left.createdAt.localeCompare(right.createdAt);
    if (sort === "client") return (clients.find((client) => client.id === left.clientId)?.name ?? "").localeCompare(clients.find((client) => client.id === right.clientId)?.name ?? "");
    return right.createdAt.localeCompare(left.createdAt);
    });
  }, [clients, effectiveClientId, sort, status, tasks]);
  const selectedTask = visible.find((task) => task.id === selectedTaskId) ?? visible[0];
  const selectedClient = clients.find((client) => client.id === selectedTask?.clientId);

  if (!loaded) return null;

  return (
    <section aria-label="Tasks" className={styles.tasks}>
      <header><span><h1>Tasks</h1><p>Tasks across every client</p></span><button disabled={!clients.length} onClick={() => setCreating(true)} type="button"><Plus aria-hidden="true" />New Task</button></header>
      <section className={styles.controls}>
        <nav aria-label="Task status">{filters.map((filter) => <button aria-current={status === filter.id ? "page" : undefined} key={filter.id} onClick={() => setStatus(filter.id)} type="button">{filter.label}</button>)}</nav>
        <span>
          <label><UserRound aria-hidden="true" /><select aria-label="Filter tasks by client" onChange={(event) => setSelectedClientId(event.target.value)} value={selectedClientId}><option value="all">All Clients</option>{clients.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}</select></label>
          <label><ListFilter aria-hidden="true" /><select aria-label="Sort tasks" onChange={(event) => setSort(event.target.value as SortMode)} value={sort}><option value="newest">Newest</option><option value="oldest">Oldest</option><option value="client">Client</option></select></label>
        </span>
      </section>
      {error ? <p className={styles.error} role="alert">{error}</p> : null}
      <section className={styles.workspace}>
        <TaskList clients={clients} onSelect={setSelectedTaskId} selectedId={selectedTask?.id} tasks={visible} />
        {selectedTask && selectedClient ? <TaskDetail clientName={selectedClient.name} key={`${selectedTask.id}-${selectedTask.updatedAt}`} onStatusChange={(next) => { setTaskStatus(selectedTask.id, next); setStatus(next); }} onTextSave={(text) => updateTaskText(selectedTask.id, text)} task={selectedTask} /> : <p className={styles.empty}>{clients.length ? "Create a task or choose another view." : "Create a client before adding tasks."}</p>}
      </section>
      <CreateTaskDialog clients={clients} onCancel={() => setCreating(false)} onSubmit={(taskClientId, text) => { const task = createTask(taskClientId, text); setSelectedTaskId(task.id); setStatus("ready"); setCreating(false); }} open={creating} />
    </section>
  );
}
