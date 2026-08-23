"use client";

import { useCallback, useEffect, useState } from "react";

import { loadSkills, saveSkills } from "../lib/skillStorage";
import type { OperatorSkill } from "../types/skill";

export function useSkillsLibrary() {
  const [skills, setSkills] = useState<OperatorSkill[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      try {
        setSkills(loadSkills());
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "Could not load skills.");
      } finally {
        setLoaded(true);
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const createSkill = useCallback((name: string, description: string) => {
    const cleanName = name.trim();
    if (!cleanName) throw new Error("A skill needs a name.");
    if (skills.some((skill) => normalizeName(skill.name) === normalizeName(cleanName))) throw new Error(`“${cleanName}” already exists.`);
    const id = crypto.randomUUID();
    const skill: OperatorSkill = {
      id,
      name: cleanName,
      description: description.trim(),
      instructions: "",
      updatedAt: new Date().toISOString(),
    };
    const next = [skill, ...skills];
    saveSkills(next);
    setSkills(next);
    setError(undefined);
    return id;
  }, [skills]);

  const updateSkill = useCallback((id: string, update: Pick<OperatorSkill, "name" | "description" | "instructions">) => {
    const name = update.name.trim();
    if (!name) throw new Error("A skill needs a name.");
    if (skills.some((skill) => skill.id !== id && normalizeName(skill.name) === normalizeName(name))) throw new Error(`“${name}” already exists.`);
    const next = skills.map((skill) => skill.id === id ? { ...skill, ...update, name, updatedAt: new Date().toISOString() } : skill);
    saveSkills(next);
    setSkills(next);
    setError(undefined);
  }, [skills]);

  return { createSkill, error, loaded, skills, updateSkill };
}

function normalizeName(name: string) {
  return name.trim().normalize("NFKC").toLocaleLowerCase();
}
