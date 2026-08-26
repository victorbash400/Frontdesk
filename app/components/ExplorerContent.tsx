import type { MouseEvent } from "react";

import type { Destination, FileSystemNode, ViewMode } from "../types/filesystem";
import { IconView } from "./IconView";
import { ColumnView } from "./ColumnView";
import { ListView } from "./ListView";
import styles from "./ExplorerContent.module.css";

type ItemHandler = (node: FileSystemNode) => void;

type ExplorerContentProps = {
  nodes: FileSystemNode[];
  allNodes: FileSystemNode[];
  destination: Destination;
  selectedNode?: FileSystemNode;
  viewMode: ViewMode;
  onOpen: ItemHandler;
  onSelect: ItemHandler;
  onRename: ItemHandler;
  onTrashToggle: ItemHandler;
  onContextMenu: (event: MouseEvent, node: FileSystemNode) => void;
};

export function ExplorerContent({ nodes, allNodes, destination, selectedNode, viewMode, onOpen, onSelect, onRename, onTrashToggle, onContextMenu }: ExplorerContentProps) {
  const shared = { nodes, onOpen, onContextMenu };
  return (
    <section className={styles.content}>
      {viewMode === "grid" ? <IconView {...shared} onRename={onRename} onTrashToggle={onTrashToggle} selectedId={selectedNode?.id} /> : null}
      {viewMode === "list" ? <ListView {...shared} selectedId={selectedNode?.id} /> : null}
      {viewMode === "columns" ? <ColumnView allNodes={allNodes} destination={destination} {...shared} onSelect={onSelect} /> : null}
    </section>
  );
}
