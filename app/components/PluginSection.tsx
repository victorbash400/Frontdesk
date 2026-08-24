import type { ReactNode } from "react";

import styles from "./PluginSection.module.css";

export function PluginSection({ children, description, title }: { children: ReactNode; description?: string; title: string }) {
  return (
    <section className={styles.section}>
      <header><h2>{title}</h2>{description ? <p>{description}</p> : null}</header>
      <div className={styles.list}>{children}</div>
    </section>
  );
}
