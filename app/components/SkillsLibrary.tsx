"use client";

import { FilePlus2, Search } from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";

import { useSkillsLibrary } from "../hooks/useSkillsLibrary";
import { skillCatalog } from "../lib/skillCatalog";
import { pluginById } from "../lib/pluginDirectory";
import type { CatalogSkill } from "../types/skill";
import { CreateSkillDialog } from "./CreateSkillDialog";
import { SkillDirectorySection } from "./SkillDirectorySection";
import { SkillEditor } from "./SkillEditor";
import { SkillPreview } from "./SkillPreview";
import styles from "./SkillsLibrary.module.css";

export function SkillsLibrary({ accountId }: { accountId: string }) {
  const { addCatalogSkill, createSkill, error, loaded, skills, updateSkill } = useSkillsLibrary(accountId);
  const [openSkillId, setOpenSkillId] = useState<string>();
  const [previewSkill, setPreviewSkill] = useState<CatalogSkill>();
  const [creating, setCreating] = useState(false);
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query.trim().toLocaleLowerCase());
  const matches = (skill: Pick<CatalogSkill, "name" | "description" | "instructions">) => !deferredQuery || `${skill.name} ${skill.description} ${skill.instructions}`.toLocaleLowerCase().includes(deferredQuery);
  const catalog = skillCatalog.filter(matches);
  const personal = skills.filter((skill) => skill.source === "user" && matches(skill)).sort((left, right) => left.name.localeCompare(right.name));
  const installedById = useMemo(() => new Map(skills.map((skill) => [skill.id, skill])), [skills]);
  const openSkill = skills.find((skill) => skill.id === openSkillId);

  if (!loaded) return null;
  if (openSkill) return <SkillEditor key={`${openSkill.id}-${openSkill.updatedAt}`} onBack={() => setOpenSkillId(undefined)} onSave={(update) => updateSkill(openSkill.id, update)} skill={openSkill} />;
  if (previewSkill) return <SkillPreview added={installedById.has(previewSkill.id)} onAdd={() => addCatalogSkill(previewSkill)} onBack={() => setPreviewSkill(undefined)} skill={previewSkill} />;

  const general = catalog.filter((skill) => skill.source === "general");
  const pluginIds = [...new Set(catalog.flatMap((skill) => skill.pluginId || []))];

  return (
    <section aria-label="Skills library" className={styles.library}>
      <header><span><h1>Skills</h1><p>Reusable workflows for Front Desk and its plugins</p></span><button onClick={() => setCreating(true)} type="button"><FilePlus2 aria-hidden="true" />New Skill</button></header>
      <section className={styles.controls}>
        <label className={styles.search}><Search aria-hidden="true" /><input aria-label="Search skills" onChange={(event) => setQuery(event.target.value)} placeholder="Search skills" type="search" value={query} /></label>
      </section>
      {error ? <p className={styles.error} role="alert">{error}</p> : null}
      <section className={styles.directory}>
        {general.length ? <SkillDirectorySection addedIds={installedById} onAdd={addCatalogSkill} onOpen={setOpenSkillId} onPreview={setPreviewSkill} skills={general} title="General" /> : null}
        {personal.length ? <SkillDirectorySection addedIds={installedById} onAdd={addCatalogSkill} onOpen={setOpenSkillId} onPreview={setPreviewSkill} skills={personal} title="Created by you" /> : null}
        {pluginIds.map((pluginId) => {
          const plugin = pluginById(pluginId);
          const pluginSkills = catalog.filter((skill) => skill.pluginId === pluginId);
          return <SkillDirectorySection addedIds={installedById} key={pluginId} onAdd={addCatalogSkill} onOpen={setOpenSkillId} onPreview={setPreviewSkill} plugin={plugin} skills={pluginSkills} title={plugin?.name || pluginId} />;
        })}
        {!general.length && !personal.length && !pluginIds.length ? <p className={styles.empty}>No skills match this search.</p> : null}
      </section>
      <CreateSkillDialog onCancel={() => setCreating(false)} onSubmit={(name, description) => { const id = createSkill(name, description); setCreating(false); setOpenSkillId(id); }} open={creating} />
    </section>
  );
}
