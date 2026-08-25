import { backendApi } from "@/app/lib/backendApi";

export async function POST(request: Request, { params }: { params: Promise<{ notificationId: string }> }) {
  const { notificationId } = await params;
  return backendApi(`/api/notifications/${encodeURIComponent(notificationId)}/answer`, { body: request.body, headers: { "Content-Type": "application/json" }, method: "POST", duplex: "half" } as RequestInit);
}
