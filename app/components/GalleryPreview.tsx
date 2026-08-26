import { FileIcon } from "./FileIcon";
import type { FileSystemNode } from "../types/filesystem";
import styles from "./GalleryPreview.module.css";

export function GalleryPreview({ node }: { node?: FileSystemNode }) {
  if (!node) return <section className={styles.empty}>Select an item to preview it.</section>;

  const content = node.content?.trim();
  return (
    <section className={styles.preview} aria-label={`Preview of ${node.name}`}>
      <div className={styles.stage}>
        {content ? <DocumentPreview content={content} /> : <div className={styles.icon}><FileIcon kind={node.kind} /></div>}
      </div>
      <div className={styles.details}>
        <h1>{node.name}</h1>
        <p>{kindLabel(node.kind)}</p>
        <section>
          <h2>Information</h2>
          <dl>
            <dt>Created</dt><dd>{formatDate(node.createdAt)}</dd>
            <dt>Modified</dt><dd>{formatDate(node.updatedAt)}</dd>
            <dt>Shared</dt><dd>{node.shared ? "Yes" : "No"}</dd>
          </dl>
        </section>
        <section>
          <h2>Tags</h2>
          {node.tags.length ? <div className={styles.tags}>{node.tags.map((tag) => <span key={tag} style={{ background: `var(--tag-${tag})` }}>{tag}</span>)}</div> : <p className={styles.muted}>No Tags</p>}
        </section>
      </div>
    </section>
  );
}

function DocumentPreview({ content }: { content: string }) {
  const lines = content.split("\n").filter(Boolean);
  return <article className={styles.document}>{lines.map((line, index) => line.startsWith("# ") ? <h2 key={index}>{line.slice(2)}</h2> : line.startsWith("## ") ? <h3 key={index}>{line.slice(3)}</h3> : <p key={index}>{line.replace(/^[-*]\s/, "")}</p>)}</article>;
}

function kindLabel(kind: FileSystemNode["kind"]) {
  return kind === "client" ? "Client folder" : kind === "folder" ? "Folder" : kind === "profile" ? "Client profile" : `${kind[0].toUpperCase()}${kind.slice(1)}`;
}

function formatDate(value: string) { return dateFormatter.format(new Date(value)); }
const dateFormatter = new Intl.DateTimeFormat(undefined, { dateStyle: "long", timeStyle: "short" });
