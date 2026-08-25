import { backendApi } from "@/app/lib/backendApi";

export async function PATCH(request: Request, { params }: { params: Promise<{ goalId: string }> }) {
  const { goalId } = await params;
  return backendApi(`/api/goals/${encodeURIComponent(goalId)}`, { body: request.body, headers: { "Content-Type": "application/json" }, method: "PATCH", duplex: "half" } as RequestInit);
}

export async function DELETE(_: Request, { params }: { params: Promise<{ goalId: string }> }) {
  const { goalId } = await params;
  return backendApi(`/api/goals/${encodeURIComponent(goalId)}`, { method: "DELETE" });
}
