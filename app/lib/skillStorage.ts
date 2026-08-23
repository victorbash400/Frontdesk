import { accountStorageKey } from "./accountStorage";
import type { OperatorSkill } from "../types/skill";

const storageNamespace = "operator-skills-v1";

const starterSkills: OperatorSkill[] = [
  {
    id: "client-brief",
    name: "Client Brief",
    description: "Turn scattered client context into a concise working brief",
    instructions: "Collect the client goal, current priorities, decision makers, deadlines, open questions, and known constraints. Keep the brief factual and concise. Separate confirmed information from assumptions that still need verification.",
    updatedAt: "2026-08-23T00:00:00.000Z",
  },
  {
    id: "email-follow-up",
    name: "Email Follow-up",
    description: "Draft clear follow-ups from client conversations",
    instructions: "Write a direct follow-up that states what was agreed, who owns each next step, and when it is due. Match the client relationship and avoid promotional language. Do not invent commitments or dates.",
    updatedAt: "2026-08-23T00:00:00.000Z",
  },
  {
    id: "meeting-preparation",
    name: "Meeting Preparation",
    description: "Prepare a focused plan for an upcoming client meeting",
    instructions: "Review the available client context and produce the meeting objective, essential background, decisions needed, questions to ask, and a short agenda. Prioritize unresolved issues that can change the outcome.",
    updatedAt: "2026-08-23T00:00:00.000Z",
  },
];

export function loadSkills(accountId: string) {
  const stored = window.localStorage.getItem(accountStorageKey(storageNamespace, accountId));
  if (!stored) return starterSkills;
  const value: unknown = JSON.parse(stored);
  if (!Array.isArray(value) || !value.every(isSkill)) throw new Error("The saved skills library is invalid.");
  return value;
}

export function saveSkills(accountId: string, skills: OperatorSkill[]) {
  window.localStorage.setItem(accountStorageKey(storageNamespace, accountId), JSON.stringify(skills));
}

function isSkill(value: unknown): value is OperatorSkill {
  if (!value || typeof value !== "object") return false;
  const skill = value as Partial<OperatorSkill>;
  return typeof skill.id === "string" && typeof skill.name === "string" && typeof skill.description === "string" && typeof skill.instructions === "string" && typeof skill.updatedAt === "string";
}
