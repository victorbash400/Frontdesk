import type { FileSystemNode } from "../types/filesystem";
import type { OperatorTask } from "../types/task";
import { TaskRow } from "./TaskRow";
import styles from "./TaskList.module.css";

type TaskListProps = {
  clients: FileSystemNode[];
  selectedId?: string;
  tasks: OperatorTask[];
  onSelect: (id: string) => void;
};

export function TaskList({ clients, selectedId, tasks, onSelect }: TaskListProps) {
  const clientNames = new Map(clients.map((client) => [client.id, client.name]));
  return (
    <section aria-label="Task list" className={styles.list}>
      {tasks.length ? tasks.map((task) => <TaskRow clientName={clientNames.get(task.clientId) ?? "Unknown Client"} key={task.id} onSelect={() => onSelect(task.id)} selected={task.id === selectedId} task={task} />) : <p>No tasks in this view</p>}
    </section>
  );
}
