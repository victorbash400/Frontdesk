import type { FileSystemNode } from "../types/filesystem";
import type { GoalLiveUpdate, GoalStatus, OperatorGoal } from "../types/goal";
import type { PluginDefinition } from "../lib/pluginDirectory";
import { GoalDetail } from "./GoalDetail";
import { GoalRow } from "./GoalRow";
import styles from "./GoalList.module.css";

type GoalListProps = {
  clients: FileSystemNode[];
  selectedId?: string;
  goals: OperatorGoal[];
  plugins: PluginDefinition[];
  liveUpdates: Record<string, GoalLiveUpdate>;
  onSelect: (id?: string) => void;
  onDelete: (id: string) => Promise<void>;
  onStatusChange: (id: string, status: GoalStatus) => void;
  onToggleSelection: (id: string) => void;
  selectedIds: Set<string>;
  selecting: boolean;
};

export function GoalList({ clients, goals, liveUpdates, plugins, selectedId, selectedIds, selecting, onDelete, onSelect, onStatusChange, onToggleSelection }: GoalListProps) {
  return (
    <section aria-label="Goal list" className={styles.list} data-empty={!goals.length}>
      {goals.length ? goals.map((goal) => {
        const expanded = goal.id === selectedId;
        return <GoalRow detail={<GoalDetail goal={goal} liveUpdate={liveUpdates[goal.id]} onDelete={() => onDelete(goal.id)} onStatusChange={(status) => onStatusChange(goal.id, status)} plugins={plugins} />} expanded={expanded} goal={goal} key={goal.id} liveUpdate={liveUpdates[goal.id]} onSelect={() => selecting ? onToggleSelection(goal.id) : onSelect(expanded ? undefined : goal.id)} selected={selectedIds.has(goal.id)} selecting={selecting} />;
      }) : <p>{clients.length ? "Goals in this view will appear here" : "Create a client before adding goals"}</p>}
    </section>
  );
}
