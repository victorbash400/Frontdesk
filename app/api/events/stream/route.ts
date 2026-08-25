import { auth } from "@/auth";
import { authenticationRequiredResponse } from "@/app/lib/authResponses";

export async function GET() {
  const session = await auth();
  if (!session?.user?.id) return authenticationRequiredResponse();
  const internalSecret = process.env.FRONT_DESK_INTERNAL_SECRET;
  if (!internalSecret) return Response.json({ error: "Front Desk events are not configured" }, { status: 500 });
  const backendUrl = process.env.FRONT_DESK_BACKEND_URL || "http://127.0.0.1:8000";
  try {
    const response = await fetch(`${backendUrl.replace(/\/$/, "")}/api/events/stream`, {
      headers: { "X-Front-Desk-Account": session.user.id, "X-Front-Desk-Internal-Secret": internalSecret },
      cache: "no-store",
    });
    if (!response.ok || !response.body) return Response.json({ error: "Front Desk event stream failed" }, { status: response.status });
    return new Response(response.body, { headers: { "Cache-Control": "no-cache", "Content-Type": "text/event-stream" } });
  } catch {
    return Response.json({ error: "Front Desk event stream is unavailable" }, { status: 503 });
  }
}
