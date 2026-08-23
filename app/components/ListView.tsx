import type { MouseEvent } from "react";

import type { FileSystemNode } from "../types/filesystem";
import { FileIcon } from "./FileIcon";
import styles from "./ListView.module.css";

type ItemHandler = (node: FileSystemNode) => void;

export function ListView({ nodes, selectedId, onOpen, onContextMenu }: { nodes: FileSystemNode[]; selectedId?: string; onOpen: ItemHandler; onContextMenu: (event: MouseEvent, node: FileSystemNode) => void }) {
  return (
    <table className={styles.table}>
      <thead><tr><th>Name</th><th>Date Modified</th><th>Kind</th></tr></thead>
      <tbody>
        {nodes.map((node) => (
          <tr aria-selected={selectedId === node.id} key={node.id} onClick={() => onOpen(node)} onContextMenu={(event) => onContextMenu(event, node)}>
            <td><FileIcon kind={node.kind} size="small" /><span>{node.name}</span></td>
            <td>{formatDate(node.updatedAt)}</td>
            <td>{kindLabel(node.kind)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function formatDate(value: string) {
  return dateFormatter.format(new Date(value));
}

function kindLabel(kind: FileSystemNode["kind"]) {
  return kind === "client" ? "Client folder" : kind === "folder" ? "Folder" : kind[0].toUpperCase() + kind.slice(1);
}

const dateFormatter = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
