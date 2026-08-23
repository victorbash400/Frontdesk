import type { MouseEvent } from "react";

import type { FileSystemNode } from "../types/filesystem";
import { FileIcon } from "./FileIcon";
import styles from "./IconView.module.css";

type ItemHandler = (node: FileSystemNode) => void;

export function IconView({ nodes, selectedId, onOpen, onSelect, onContextMenu }: { nodes: FileSystemNode[]; selectedId?: string; onOpen: ItemHandler; onSelect: ItemHandler; onContextMenu: (event: MouseEvent, node: FileSystemNode) => void }) {
  return (
    <section className={styles.grid} aria-label="Items">
      {nodes.map((node) => (
        <button aria-pressed={selectedId === node.id} key={node.id} onClick={() => onSelect(node)} onContextMenu={(event) => onContextMenu(event, node)} onDoubleClick={() => onOpen(node)} type="button">
          <FileIcon kind={node.kind} />
          <span>{node.name}</span>
          {node.tags.length > 0 ? <i style={{ background: `var(--tag-${node.tags[0]})` }} /> : null}
        </button>
      ))}
    </section>
  );
}
