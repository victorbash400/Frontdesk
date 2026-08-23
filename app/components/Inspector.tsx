import { FileIcon } from "./FileIcon";
import { tagColors, type FileSystemNode, type TagName } from "../types/filesystem";
import styles from "./Inspector.module.css";

export function Inspector({ node, onToggleTag }: { node?: FileSystemNode; onToggleTag: (tag: TagName) => void }) {
  return (
    <aside className={styles.inspector} aria-label="Inspector">
      {node ? (
        <>
          <header><FileIcon kind={node.kind} size="small" /><strong>{node.name}</strong></header>
          <section>
            <h2>Information</h2>
            <dl>
              <dt>Kind</dt><dd>{node.kind}</dd>
              <dt>Created</dt><dd>{formatDate(node.createdAt)}</dd>
              <dt>Modified</dt><dd>{formatDate(node.updatedAt)}</dd>
              <dt>Shared</dt><dd>{node.shared ? "Yes" : "No"}</dd>
            </dl>
          </section>
          <section>
            <h2>Tags</h2>
            <nav aria-label="Item tags">
              {(Object.keys(tagColors) as TagName[]).map((tag) => <button aria-pressed={node.tags.includes(tag)} key={tag} onClick={() => onToggleTag(tag)} title={tag} type="button" style={{ background: tagColors[tag] }} />)}
            </nav>
          </section>
        </>
      ) : <p>Select an item to inspect it.</p>}
    </aside>
  );
}

function formatDate(value: string) {
  return dateFormatter.format(new Date(value));
}

const dateFormatter = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
