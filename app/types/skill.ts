export type SkillSource = "general" | "user" | "plugin";

export type OperatorSkill = {
  id: string;
  name: string;
  description: string;
  instructions: string;
  updatedAt: string;
  source: SkillSource;
  pluginId?: string;
  sourceUrl?: string;
};

export type CatalogSkill = Omit<OperatorSkill, "updatedAt">;
