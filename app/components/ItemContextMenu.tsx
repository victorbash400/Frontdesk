import { CircleAlert, Pencil, RotateCcw, Share2, Trash2 } from "lucide-react";

import type { FileSystemNode } from "../types/filesystem";
import styles from "./ItemContextMenu.module.css";

export type ContextMenuState = { x: number; y: number; node: FileSystemNode };

type ItemContextMenuProps = {
  state: ContextMenuState;
  onClose: () => void;
  onRename: () => void;
  onShareToggle: () => void;
  onAttentionToggle: () => void;
  onTrashToggle: () => void;
};

export function ItemContextMenu({ state, onClose, onRename, onShareToggle, onAttentionToggle, onTrashToggle }: ItemContextMenuProps) {
  const trashed = Boolean(state.node.trashedAt);
  const protectedItem = Boolean(state.node.protected);
  return (
    <menu className={styles.menu} onMouseLeave={onClose} style={{ left: Math.min(state.x, window.innerWidth - 190), top: Math.min(state.y, window.innerHeight - 190) }}>
      {!protectedItem ? <button onClick={onRename} type="button"><Pencil />Rename</button> : null}
      <button onClick={onShareToggle} type="button"><Share2 />{state.node.shared ? "Remove from Shared" : "Add to Shared"}</button>
      <button onClick={onAttentionToggle} type="button"><CircleAlert />{state.node.needsAttention ? "Clear Needs You" : "Mark as Needs You"}</button>
      {!protectedItem ? <><hr /><button className={trashed ? undefined : styles.destructive} onClick={onTrashToggle} type="button">{trashed ? <RotateCcw /> : <Trash2 />}{trashed ? "Restore" : "Move to Trash"}</button></> : null}
    </menu>
  );
}
