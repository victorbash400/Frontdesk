import type { MouseEvent } from "react";

import type { FileSystemNode } from "../types/filesystem";
import { FileIcon } from "./FileIcon";
import styles from "./ColumnView.module.css";

type ItemHandler = (node: FileSystemNode) => void;

export function ColumnView({ nodes, selectedNode, onOpen, onSelect, onContextMenu }: { nodes: FileSystemNode[]; selectedNode?: FileSystemNode; onOpen: ItemHandler; onSelect: ItemHandler; onContextMenu: (event: MouseEvent, node: FileSystemNode) => void }) {
  return (
    <section className={styles.columns} aria-label="Column view">
      <nav>
        {nodes.map((node) => (
          <button aria-current={selectedNode?.id === node.id ? "true" : undefined} key={node.id} onClick={() => onSelect(node)} onContextMenu={(event) => onContextMenu(event, node)} onDoubleClick={() => onOpen(node)} type="button">
            <FileIcon kind={node.kind} size="small" />
            <span>{node.name}</span>
            {(node.kind === "folder" || node.kind === "client") ? <b>›</b> : null}
          </button>
        ))}
      </nav>
      <article>
        {selectedNode ? <><FileIcon kind={selectedNode.kind} /><strong>{selectedNode.name}</strong><span>{selectedNode.kind === "client" ? "Client folder" : selectedNode.kind}</span></> : null}
      </article>
    </section>
  );
}
