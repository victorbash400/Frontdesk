export type SkillSource = "builtin" | "organization";

export type OperatorSkill = {
  id: string;
  name: string;
  description: string;
  instructions: string;
  updatedAt: string;
  source: SkillSource;
  batchName: string;
  pluginId?: string;
  requiredPluginIds: string[];
  sourceUrl?: string;
  deletable: boolean;
  version: number;
};
