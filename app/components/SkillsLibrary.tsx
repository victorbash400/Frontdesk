"use client";

import { FilePlus2, ListFilter, Search } from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";

import { useSkillsLibrary } from "../hooks/useSkillsLibrary";
import { CreateSkillDialog } from "./CreateSkillDialog";
import { SkillEditor } from "./SkillEditor";
import { SkillList } from "./SkillList";
import styles from "./SkillsLibrary.module.css";

type SortMode = "name" | "newest" | "oldest";

export function SkillsLibrary() {
  const { createSkill, error, loaded, skills, updateSkill } = useSkillsLibrary();
  const [openSkillId, setOpenSkillId] = useState<string>();
  const [creating, setCreating] = useState(false);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortMode>("name");
  const deferredQuery = useDeferredValue(query.trim().toLocaleLowerCase());
  const visible = useMemo(() => skills.filter((skill) => !deferredQuery || `${skill.name} ${skill.description} ${skill.instructions}`.toLocaleLowerCase().includes(deferredQuery)).sort((left, right) => {
    if (sort === "newest") return right.updatedAt.localeCompare(left.updatedAt);
    if (sort === "oldest") return left.updatedAt.localeCompare(right.updatedAt);
    return left.name.localeCompare(right.name);
  }), [deferredQuery, skills, sort]);
  const openSkill = skills.find((skill) => skill.id === openSkillId);

  if (!loaded) return null;
  if (openSkill) return <SkillEditor key={`${openSkill.id}-${openSkill.updatedAt}`} onBack={() => setOpenSkillId(undefined)} onSave={(update) => updateSkill(openSkill.id, update)} skill={openSkill} />;

  return (
    <section aria-label="Skills library" className={styles.library}>
      <header><span><h1>Skills</h1><p>Reusable instructions for client work</p></span><button onClick={() => setCreating(true)} type="button"><FilePlus2 aria-hidden="true" />New Skill</button></header>
      <section className={styles.controls}>
        <label className={styles.search}><Search aria-hidden="true" /><input aria-label="Search skills" onChange={(event) => setQuery(event.target.value)} placeholder="Search skills" type="search" value={query} /></label>
        <label className={styles.sort}><ListFilter aria-hidden="true" /><select aria-label="Sort skills" onChange={(event) => setSort(event.target.value as SortMode)} value={sort}><option value="name">Name</option><option value="newest">Recently Modified</option><option value="oldest">Oldest Modified</option></select></label>
      </section>
      {error ? <p className={styles.error} role="alert">{error}</p> : null}
      <SkillList onOpen={setOpenSkillId} skills={visible} />
      <CreateSkillDialog onCancel={() => setCreating(false)} onSubmit={(name, description) => { const id = createSkill(name, description); setCreating(false); setOpenSkillId(id); }} open={creating} />
    </section>
  );
}
