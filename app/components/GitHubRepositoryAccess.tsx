"use client";

import { LockKeyhole, Search } from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";

import { useGitHubRepositoryAccess } from "../hooks/useGitHubRepositoryAccess";
import styles from "./GitHubRepositoryAccess.module.css";


export function GitHubRepositoryAccess({ onSaved }: { onSaved: () => void }) {
  const access = useGitHubRepositoryAccess(onSaved);
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query.trim().toLocaleLowerCase());
  const visible = useMemo(() => access.repositories.filter((repository) => (
    !deferredQuery || repository.full_name.toLocaleLowerCase().includes(deferredQuery)
  )), [access.repositories, deferredQuery]);

  if (!access.loaded) return <p className={styles.status}>Loading repositories…</p>;

  return (
    <section className={styles.access}>
      <span className={styles.heading}><h3>Repository access</h3><small>{access.selected.size} selected</small></span>
      <p>Only selected repositories will be available to Front Desk.</p>
      {access.error ? <p className={styles.error} role="alert">{access.error}</p> : null}
      <label className={styles.search}><Search aria-hidden="true" /><input aria-label="Search GitHub repositories" onChange={(event) => setQuery(event.target.value)} placeholder="Search repositories" type="search" value={query} /></label>
      <span className={styles.selection}>
        <button onClick={() => access.setSelected(new Set(access.repositories.map((repository) => repository.full_name)))} type="button">Select all</button>
        <button onClick={() => access.setSelected(new Set())} type="button">Clear</button>
      </span>
      <ul className={styles.repositories}>
        {visible.map((repository) => <li key={repository.full_name}>
          <label>
            <input checked={access.selected.has(repository.full_name)} onChange={() => access.toggle(repository.full_name)} type="checkbox" />
            <span>{repository.full_name}</span>
            {repository.private ? <LockKeyhole aria-label="Private repository" /> : null}
          </label>
        </li>)}
      </ul>
      {!visible.length ? <p className={styles.empty}>No repositories found.</p> : null}
      <button className={styles.save} disabled={access.saving} onClick={() => void access.save()} type="button">{access.saving ? "Saving…" : "Save access"}</button>
    </section>
  );
}
