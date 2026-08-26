import { ChevronRight } from "lucide-react";
import { useLayoutEffect, useRef, useState, type MouseEvent } from "react";

import { folderPath, isContainer, nodesForDestination } from "../lib/fileSystemSelectors";
import type { Destination, FileSystemNode } from "../types/filesystem";
import { FileIcon } from "./FileIcon";
import { GalleryPreview } from "./GalleryPreview";
import styles from "./ColumnView.module.css";

type ItemHandler = (node: FileSystemNode) => void;

type ColumnViewProps = {
  nodes: FileSystemNode[];
  allNodes: FileSystemNode[];
  destination: Destination;
  onSelect: ItemHandler;
  onOpen: ItemHandler;
  onContextMenu: (event: MouseEvent, node: FileSystemNode) => void;
};

export function ColumnView({ nodes, allNodes, destination, onSelect, onOpen, onContextMenu }: ColumnViewProps) {
  const [path, setPath] = useState<FileSystemNode[]>(() => initialPath(allNodes, destination));
  const browserRef = useRef<HTMLElement>(null);
  const rootNodes = destination.type === "folder" ? nodesForDestination(allNodes, { type: "location", location: "clients" }) : nodes;
  const columns = [sortByName(rootNodes), ...path.filter(isContainer).map((folder) => childrenOf(allNodes, folder))];
  const previewNode = path.at(-1);
  const preview = previewNode && !isContainer(previewNode) ? previewNode : undefined;

  useLayoutEffect(() => {
    const browser = browserRef.current;
    if (browser) browser.scrollTo({ behavior: "smooth", left: browser.scrollWidth });
  }, [path]);

  function select(node: FileSystemNode, columnIndex: number) {
    setPath((current) => [...current.slice(0, columnIndex), node]);
    onSelect(node);
  }

  return (
    <section className={styles.browser} aria-label="Column view" ref={browserRef}>
      {columns.map((items, columnIndex) => (
        <div className={styles.column} key={columnIndex}>
          {items.map((node) => (
            <button
              aria-pressed={path[columnIndex]?.id === node.id}
              className={styles.item}
              key={node.id}
              onClick={() => select(node, columnIndex)}
              onContextMenu={(event) => onContextMenu(event, node)}
              onDoubleClick={() => onOpen(node)}
              type="button"
            >
              <FileIcon kind={node.kind} size="small" />
              <span>{node.name}</span>
              {node.tags[0] ? <i style={{ background: `var(--tag-${node.tags[0]})` }} /> : null}
              {isContainer(node) ? <ChevronRight aria-hidden="true" /> : null}
            </button>
          ))}
        </div>
      ))}
      {preview ? <div className={styles.preview}><GalleryPreview node={preview} /></div> : null}
    </section>
  );
}

function childrenOf(nodes: FileSystemNode[], folder: FileSystemNode) {
  return sortByName(nodes.filter((node) => node.parentId === folder.id && Boolean(node.trashedAt) === Boolean(folder.trashedAt)));
}

function initialPath(nodes: FileSystemNode[], destination: Destination) {
  return destination.type === "folder" ? folderPath(nodes, destination.id) : [];
}

function sortByName(nodes: FileSystemNode[]) {
  return [...nodes].sort((left, right) => left.name.localeCompare(right.name, undefined, { numeric: true }));
}
