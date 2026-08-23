import styles from "./StatusBar.module.css";

export function StatusBar({ count }: { count: number }) {
  return <footer className={styles.status}>{count} {count === 1 ? "item" : "items"}</footer>;
}
