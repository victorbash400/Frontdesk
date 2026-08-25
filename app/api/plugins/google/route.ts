import { auth } from "@/auth";
import { authenticationRequiredResponse } from "@/app/lib/authResponses";


async function proxy(method: "GET" | "POST" | "DELETE") {
  const session = await auth();
  if (!session?.user?.id) return authenticationRequiredResponse();
  const internalSecret = process.env.FRONT_DESK_INTERNAL_SECRET;
  if (!internalSecret) return Response.json({ error: "Google Workspace is not configured" }, { status: 500 });
  const backendUrl = process.env.FRONT_DESK_BACKEND_URL || "http://127.0.0.1:8000";
  const path = method === "POST" ? "/api/plugins/google/start" : "/api/plugins/google";
  try {
    const response = await fetch(`${backendUrl.replace(/\/$/, "")}${path}`, {
      method,
      headers: {
        "X-Front-Desk-Account": session.user.id,
        "X-Front-Desk-Internal-Secret": internalSecret,
      },
      cache: "no-store",
    });
    const payload = await response.json().catch(() => ({ detail: "Google Workspace request failed" })) as Record<string, unknown>;
    if (!response.ok) {
      const error = typeof payload.detail === "string" ? payload.detail : "Google Workspace request failed";
      return Response.json({ error }, { status: response.status });
    }
    return Response.json(payload);
  } catch {
    return Response.json({ error: "Front Desk could not reach the Google connection service" }, { status: 503 });
  }
}

export function GET() { return proxy("GET"); }
export function POST() { return proxy("POST"); }
export function DELETE() { return proxy("DELETE"); }
