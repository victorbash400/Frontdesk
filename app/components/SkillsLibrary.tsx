"use client";

import { FilePlus2, Search } from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";

import { useSkillsLibrary } from "../hooks/useSkillsLibrary";
import { pluginById } from "../lib/pluginDirectory";
import { CreateSkillDialog } from "./CreateSkillDialog";
import { SkillDirectorySection } from "./SkillDirectorySection";
import { SkillEditor } from "./SkillEditor";
import { SkillPreview } from "./SkillPreview";
import styles from "./SkillsLibrary.module.css";

export function SkillsLibrary({ accountId }: { accountId: string }) {
  const { createSkill, deleteSkill, error, loaded, skills, updateSkill } = useSkillsLibrary(accountId);
  const [openSkillId, setOpenSkillId] = useState<string>();
  const [creating, setCreating] = useState(false);
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query.trim().toLocaleLowerCase());
  const visible = useMemo(() => skills.filter((skill) => !deferredQuery || `${skill.name} ${skill.description} ${skill.instructions} ${skill.batchName}`.toLocaleLowerCase().includes(deferredQuery)), [deferredQuery, skills]);
  const batches = useMemo(() => [...new Set(visible.map((skill) => skill.batchName))], [visible]);
  const openSkill = skills.find((skill) => skill.id === openSkillId);

  if (!loaded) return null;
  if (openSkill?.deletable) return <SkillEditor key={`${openSkill.id}-${openSkill.updatedAt}`} onBack={() => setOpenSkillId(undefined)} onSave={(update) => updateSkill(openSkill.id, { ...update, requiredPluginIds: openSkill.requiredPluginIds })} skill={openSkill} />;
  if (openSkill) return <SkillPreview onBack={() => setOpenSkillId(undefined)} skill={openSkill} />;

  return <section aria-label="Skills library" className={styles.library}>
    <header><span><h1>Skills</h1><p>Organization procedures selected by the planner and used by workers</p></span><button onClick={() => setCreating(true)} type="button"><FilePlus2 aria-hidden="true" />New Skill</button></header>
    <section className={styles.controls}><label className={styles.search}><Search aria-hidden="true" /><input aria-label="Search skills" onChange={(event) => setQuery(event.target.value)} placeholder="Search skills" type="search" value={query} /></label></section>
    {error ? <p className={styles.error} role="alert">{error}</p> : null}
    <section className={styles.directory}>
      {batches.map((batchName) => {
        const batchSkills = visible.filter((skill) => skill.batchName === batchName);
        const plugin = pluginById(batchSkills.find((skill) => skill.pluginId)?.pluginId || "");
        return <SkillDirectorySection key={batchName} onDelete={(id) => void deleteSkill(id)} onOpen={setOpenSkillId} plugin={plugin} skills={batchSkills} title={batchName} />;
      })}
      {!visible.length ? <p className={styles.empty}>No skills match this search.</p> : null}
    </section>
    <CreateSkillDialog onCancel={() => setCreating(false)} onSubmit={(name, description) => { void createSkill(name, description).then((id) => { setCreating(false); setOpenSkillId(id); }); }} open={creating} />
  </section>;
}
