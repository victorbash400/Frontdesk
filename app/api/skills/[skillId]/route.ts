import { backendApi } from "@/app/lib/backendApi";

export async function PUT(request: Request, context: { params: Promise<{ skillId: string }> }) {
  const { skillId } = await context.params;
  return backendApi(`/api/skills/${encodeURIComponent(skillId)}`, { body: request.body, headers: { "Content-Type": "application/json" }, method: "PUT", duplex: "half" } as RequestInit);
}

export async function DELETE(_: Request, context: { params: Promise<{ skillId: string }> }) {
  const { skillId } = await context.params;
  return backendApi(`/api/skills/${encodeURIComponent(skillId)}`, { method: "DELETE" });
}
