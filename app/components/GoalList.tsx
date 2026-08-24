import type { FileSystemNode } from "../types/filesystem";
import type { GoalStatus, OperatorGoal } from "../types/goal";
import type { PluginDefinition } from "../lib/pluginDirectory";
import type { OperatorSkill } from "../types/skill";
import { GoalDetail } from "./GoalDetail";
import { GoalRow } from "./GoalRow";
import styles from "./GoalList.module.css";

type GoalListProps = {
  clients: FileSystemNode[];
  selectedId?: string;
  goals: OperatorGoal[];
  plugins: PluginDefinition[];
  skills: OperatorSkill[];
  onSelect: (id?: string) => void;
  onStatusChange: (id: string, status: GoalStatus) => void;
  onSave: (id: string, update: Pick<OperatorGoal, "text" | "skillIds" | "pluginIds">) => void;
};

export function GoalList({ clients, goals, plugins, selectedId, skills, onSelect, onSave, onStatusChange }: GoalListProps) {
  const clientNames = new Map(clients.map((client) => [client.id, client.name]));
  return (
    <section aria-label="Goal list" className={styles.list} data-empty={!goals.length}>
      {goals.length ? goals.map((goal) => {
        const clientName = clientNames.get(goal.clientId) ?? "Unknown Client";
        const expanded = goal.id === selectedId;
        return <GoalRow clientName={clientName} detail={<GoalDetail clientName={clientName} goal={goal} onSave={(update) => onSave(goal.id, update)} onStatusChange={(status) => onStatusChange(goal.id, status)} plugins={plugins} skills={skills} />} expanded={expanded} goal={goal} key={goal.id} onSelect={() => onSelect(expanded ? undefined : goal.id)} />;
      }) : <p>{clients.length ? "Goals in this view will appear here" : "Create a client before adding goals"}</p>}
    </section>
  );
}
