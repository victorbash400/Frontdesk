import { RotateCcw, Trash2 } from "lucide-react";
import type { MouseEvent } from "react";

import type { FileSystemNode } from "../types/filesystem";
import { FileIcon } from "./FileIcon";
import styles from "./GridItem.module.css";

type ItemHandler = (node: FileSystemNode) => void;

type GridItemProps = {
  node: FileSystemNode;
  selected: boolean;
  onOpen: ItemHandler;
  onRename: ItemHandler;
  onTrashToggle: ItemHandler;
  onContextMenu: (event: MouseEvent, node: FileSystemNode) => void;
};

export function GridItem({ node, selected, onOpen, onRename, onTrashToggle, onContextMenu }: GridItemProps) {
  const protectedItem = Boolean(node.protected);
  const trashed = Boolean(node.trashedAt);

  return (
    <article className={styles.item} data-selected={selected} onContextMenu={(event) => onContextMenu(event, node)}>
      <button className={styles.preview} onClick={() => onOpen(node)} type="button">
        <FileIcon kind={node.kind} />
        <span className={styles.openLabel}>Open {node.name}</span>
        {node.tags.length > 0 ? <i className={styles.tag} style={{ background: `var(--tag-${node.tags[0]})` }} /> : null}
      </button>
      <footer className={styles.footer}>
        {protectedItem ? (
          <span className={styles.name}>{node.name}</span>
        ) : (
          <button className={styles.name} onClick={() => onRename(node)} title={`Rename ${node.name}`} type="button">{node.name}</button>
        )}
        {!protectedItem ? (
          <button className={styles.trash} onClick={() => onTrashToggle(node)} title={trashed ? `Restore ${node.name}` : `Move ${node.name} to Trash`} type="button">
            {trashed ? <RotateCcw /> : <Trash2 />}
            <span>{trashed ? "Restore" : "Move to Trash"}</span>
          </button>
        ) : null}
      </footer>
    </article>
  );
}
