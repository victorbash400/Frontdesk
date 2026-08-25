import { backendApi } from "@/app/lib/backendApi";

export async function POST(request: Request, { params }: { params: Promise<{ goalId: string }> }) {
  const { goalId } = await params;
  return backendApi(`/api/goals/${encodeURIComponent(goalId)}/automations`, { body: request.body, headers: { "Content-Type": "application/json" }, method: "POST", duplex: "half" } as RequestInit);
}
