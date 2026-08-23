import type { MouseEvent } from "react";

import type { FileSystemNode, ViewMode } from "../types/filesystem";
import { IconView } from "./IconView";
import { ListView } from "./ListView";
import styles from "./ExplorerContent.module.css";

type ItemHandler = (node: FileSystemNode) => void;

type ExplorerContentProps = {
  nodes: FileSystemNode[];
  selectedNode?: FileSystemNode;
  viewMode: ViewMode;
  onOpen: ItemHandler;
  onContextMenu: (event: MouseEvent, node: FileSystemNode) => void;
};

export function ExplorerContent({ nodes, selectedNode, viewMode, onOpen, onContextMenu }: ExplorerContentProps) {
  const shared = { nodes, onOpen, onContextMenu };
  return (
    <section className={styles.content}>
      {viewMode === "grid" ? <IconView {...shared} selectedId={selectedNode?.id} /> : null}
      {viewMode === "list" ? <ListView {...shared} selectedId={selectedNode?.id} /> : null}
    </section>
  );
}
