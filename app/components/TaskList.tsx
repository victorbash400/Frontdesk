import type { FileSystemNode } from "../types/filesystem";
import type { OperatorTask, TaskStatus } from "../types/task";
import { TaskDetail } from "./TaskDetail";
import { TaskRow } from "./TaskRow";
import styles from "./TaskList.module.css";

type TaskListProps = {
  clients: FileSystemNode[];
  selectedId?: string;
  tasks: OperatorTask[];
  onSelect: (id?: string) => void;
  onStatusChange: (id: string, status: TaskStatus) => void;
  onTextSave: (id: string, text: string) => void;
};

export function TaskList({ clients, selectedId, tasks, onSelect, onStatusChange, onTextSave }: TaskListProps) {
  const clientNames = new Map(clients.map((client) => [client.id, client.name]));
  return (
    <section aria-label="Task list" className={styles.list} data-empty={!tasks.length}>
      {tasks.length ? tasks.map((task) => {
        const clientName = clientNames.get(task.clientId) ?? "Unknown Client";
        const expanded = task.id === selectedId;
        return <TaskRow clientName={clientName} detail={<TaskDetail clientName={clientName} onStatusChange={(status) => onStatusChange(task.id, status)} onTextSave={(text) => onTextSave(task.id, text)} task={task} />} expanded={expanded} key={task.id} onSelect={() => onSelect(expanded ? undefined : task.id)} task={task} />;
      }) : <p>{clients.length ? "Tasks in this view will appear here" : "Create a client before adding tasks"}</p>}
    </section>
  );
}
