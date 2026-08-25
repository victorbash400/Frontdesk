import { accountStorageKey } from "./accountStorage";
import type { OperatorSkill } from "../types/skill";

const storageNamespace = "front-desk-skills-v1";

export function loadSkills(accountId: string) {
  const stored = window.localStorage.getItem(accountStorageKey(storageNamespace, accountId));
  if (!stored) return [];
  const value: unknown = JSON.parse(stored);
  if (!Array.isArray(value) || !value.every(isStoredSkill)) throw new Error("The saved skills library is invalid.");
  return value.map((skill) => ({ ...skill, source: skill.source || "user" }));
}

export function saveSkills(accountId: string, skills: OperatorSkill[]) {
  window.localStorage.setItem(accountStorageKey(storageNamespace, accountId), JSON.stringify(skills));
}

function isStoredSkill(value: unknown): value is Omit<OperatorSkill, "source"> & Partial<Pick<OperatorSkill, "source">> {
  if (!value || typeof value !== "object") return false;
  const skill = value as Partial<OperatorSkill>;
  return typeof skill.id === "string" && typeof skill.name === "string" && typeof skill.description === "string" && typeof skill.instructions === "string" && typeof skill.updatedAt === "string" && (skill.source === undefined || skill.source === "general" || skill.source === "user" || skill.source === "plugin");
}
