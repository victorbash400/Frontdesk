import type { ReactNode } from "react";

import styles from "./PluginSection.module.css";

export function PluginSection({ action, children, description, title }: { action?: ReactNode; children: ReactNode; description?: string; title: string }) {
  return (
    <section className={styles.section}>
      <header><span><h2>{title}</h2>{description ? <p>{description}</p> : null}</span>{action}</header>
      <div className={styles.list}>{children}</div>
    </section>
  );
}
