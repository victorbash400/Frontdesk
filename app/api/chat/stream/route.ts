import { auth } from "@/auth";
import { authenticationRequiredResponse } from "@/app/lib/authResponses";


export async function POST(request: Request) {
  const session = await auth();
  if (!session?.user?.id) return authenticationRequiredResponse();

  const internalSecret = process.env.FRONT_DESK_INTERNAL_SECRET;
  if (!internalSecret) return Response.json({ error: "Front Desk chat is not configured" }, { status: 500 });

  const backendUrl = process.env.FRONT_DESK_BACKEND_URL || "http://127.0.0.1:8000";
  let response: Response;
  try {
    response = await fetch(`${backendUrl.replace(/\/$/, "")}/api/chat/stream`, {
      body: await request.text(),
      headers: {
        "Content-Type": "application/json",
        "X-Front-Desk-Account": session.user.id,
        "X-Front-Desk-Internal-Secret": internalSecret,
      },
      method: "POST",
    });
  } catch {
    return Response.json({ error: "Front Desk chat service is unavailable" }, { status: 503 });
  }

  if (!response.ok || !response.body) {
    const detail = await response.text();
    return Response.json({ error: detail || "Front Desk chat failed" }, { status: response.status });
  }
  return new Response(response.body, {
    headers: {
      "Cache-Control": "no-cache",
      "Content-Type": "text/event-stream",
    },
  });
}
