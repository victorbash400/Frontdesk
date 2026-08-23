"use client";

import { FilePlus2, Search } from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";

import { useSkillsLibrary } from "../hooks/useSkillsLibrary";
import { SkillEditor } from "./SkillEditor";
import { SkillList } from "./SkillList";
import styles from "./SkillsLibrary.module.css";

export function SkillsLibrary() {
  const { createSkill, error, loaded, skills, updateSkill } = useSkillsLibrary();
  const [selectedId, setSelectedId] = useState<string>();
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query.trim().toLocaleLowerCase());
  const visible = useMemo(() => skills.filter((skill) => !deferredQuery || `${skill.name} ${skill.description}`.toLocaleLowerCase().includes(deferredQuery)), [deferredQuery, skills]);
  const selected = skills.find((skill) => skill.id === selectedId) ?? visible[0];

  if (!loaded) return null;

  return (
    <section aria-label="Skills library" className={styles.library}>
      <header>
        <span><h1>Skills</h1><p>Instructions Operator can follow</p></span>
        <button onClick={() => setSelectedId(createSkill())} type="button"><FilePlus2 aria-hidden="true" />New Skill</button>
      </header>
      <label className={styles.search}><Search aria-hidden="true" /><input aria-label="Search skills" onChange={(event) => setQuery(event.target.value)} placeholder="Search skills" type="search" value={query} /></label>
      {error ? <p className={styles.error} role="alert">{error}</p> : null}
      <section className={styles.workspace}>
        <SkillList onSelect={setSelectedId} selectedId={selected?.id} skills={visible} />
        {selected ? <SkillEditor key={selected.id} onSave={(update) => updateSkill(selected.id, update)} skill={selected} /> : null}
      </section>
    </section>
  );
}
