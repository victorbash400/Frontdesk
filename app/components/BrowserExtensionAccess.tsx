import Link from "next/link";

import styles from "./BrowserExtensionAccess.module.css";


export function BrowserExtensionAccess() {
  return (
    <section className={styles.access}>
      <span><strong>Chrome extension</strong><small>Download and load the Front Desk extension in Chrome.</small></span>
      <Link href="/extension">Download</Link>
    </section>
  );
}
