import type { MouseEvent } from "react";

import type { FileSystemNode } from "../types/filesystem";
import { GridItem } from "./GridItem";
import styles from "./IconView.module.css";

type ItemHandler = (node: FileSystemNode) => void;

type IconViewProps = {
  nodes: FileSystemNode[];
  selectedId?: string;
  onOpen: ItemHandler;
  onRename: ItemHandler;
  onTrashToggle: ItemHandler;
  onContextMenu: (event: MouseEvent, node: FileSystemNode) => void;
};

export function IconView({ nodes, selectedId, onOpen, onRename, onTrashToggle, onContextMenu }: IconViewProps) {
  return (
    <section className={styles.grid} aria-label="Items">
      {nodes.map((node) => (
        <GridItem
          key={node.id}
          node={node}
          onContextMenu={onContextMenu}
          onOpen={onOpen}
          onRename={onRename}
          onTrashToggle={onTrashToggle}
          selected={selectedId === node.id}
        />
      ))}
    </section>
  );
}
