import type { MouseEvent } from "react";

import type { FileSystemNode } from "../types/filesystem";
import { FileIcon } from "./FileIcon";
import styles from "./GalleryView.module.css";

type ItemHandler = (node: FileSystemNode) => void;

export function GalleryView({ nodes, selectedNode, onOpen, onSelect, onContextMenu }: { nodes: FileSystemNode[]; selectedNode?: FileSystemNode; onOpen: ItemHandler; onSelect: ItemHandler; onContextMenu: (event: MouseEvent, node: FileSystemNode) => void }) {
  const current = selectedNode ?? nodes[0];
  return (
    <section className={styles.gallery} aria-label="Gallery view">
      <article>{current ? <><FileIcon kind={current.kind} /><strong>{current.name}</strong></> : null}</article>
      <nav aria-label="Gallery items">
        {nodes.map((node) => (
          <button aria-current={current?.id === node.id ? "true" : undefined} key={node.id} onClick={() => onSelect(node)} onContextMenu={(event) => onContextMenu(event, node)} onDoubleClick={() => onOpen(node)} title={node.name} type="button">
            <FileIcon kind={node.kind} size="small" />
          </button>
        ))}
      </nav>
    </section>
  );
}
