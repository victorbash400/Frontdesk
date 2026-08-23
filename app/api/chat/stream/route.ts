import { auth } from "@/auth";


export async function POST(request: Request) {
  const session = await auth();
  if (!session?.user?.id) return Response.json({ error: "Authentication is required" }, { status: 401 });

  const internalSecret = process.env.OPERATOR_INTERNAL_SECRET;
  if (!internalSecret) return Response.json({ error: "Operator chat is not configured" }, { status: 500 });

  const backendUrl = process.env.OPERATOR_BACKEND_URL || "http://127.0.0.1:8000";
  let response: Response;
  try {
    response = await fetch(`${backendUrl.replace(/\/$/, "")}/api/chat/stream`, {
      body: await request.text(),
      headers: {
        "Content-Type": "application/json",
        "X-Operator-Account": session.user.id,
        "X-Operator-Internal-Secret": internalSecret,
      },
      method: "POST",
    });
  } catch {
    return Response.json({ error: "Operator chat service is unavailable" }, { status: 503 });
  }

  if (!response.ok || !response.body) {
    const detail = await response.text();
    return Response.json({ error: detail || "Operator chat failed" }, { status: response.status });
  }
  return new Response(response.body, {
    headers: {
      "Cache-Control": "no-cache",
      "Content-Type": "text/event-stream",
    },
  });
}
