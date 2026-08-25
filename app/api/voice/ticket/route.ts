import { auth } from "@/auth";
import { authenticationRequiredResponse } from "@/app/lib/authResponses";

export async function POST(request: Request) {
  const session = await auth();
  if (!session?.user?.id) return authenticationRequiredResponse();
  const internalSecret = process.env.FRONT_DESK_INTERNAL_SECRET;
  if (!internalSecret) return Response.json({ error: "Front Desk voice is not configured" }, { status: 500 });
  const backendUrl = (process.env.FRONT_DESK_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
  try {
    const response = await fetch(`${backendUrl}/api/voice/ticket`, { body: await request.text(), headers: { "Content-Type": "application/json", "X-Front-Desk-Account": session.user.id, "X-Front-Desk-Internal-Secret": internalSecret }, method: "POST" });
    const payload = await response.json() as { ticket?: string; detail?: string };
    if (!response.ok || !payload.ticket) return Response.json({ error: payload.detail || "Voice authentication failed" }, { status: response.status });
    const websocketUrl = backendUrl.replace(/^http/, "ws");
    return Response.json({ ticket: payload.ticket, websocketUrl });
  } catch {
    return Response.json({ error: "Front Desk voice service is unavailable" }, { status: 503 });
  }
}
