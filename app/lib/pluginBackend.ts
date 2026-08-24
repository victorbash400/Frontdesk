import { auth } from "@/auth";


export async function pluginBackend(path: string, init: RequestInit = {}) {
  const session = await auth();
  if (!session?.user?.id) return Response.json({ error: "Authentication is required" }, { status: 401 });
  const internalSecret = process.env.FRONT_DESK_INTERNAL_SECRET;
  if (!internalSecret) return Response.json({ error: "Front Desk plugins are not configured" }, { status: 500 });
  const backendUrl = process.env.FRONT_DESK_BACKEND_URL || "http://127.0.0.1:8000";
  try {
    const response = await fetch(`${backendUrl.replace(/\/$/, "")}${path}`, {
      ...init,
      headers: {
        ...init.headers,
        "X-Front-Desk-Account": session.user.id,
        "X-Front-Desk-Internal-Secret": internalSecret,
      },
      cache: "no-store",
    });
    const payload = await response.json().catch(() => ({ detail: "Plugin request failed" })) as Record<string, unknown>;
    if (!response.ok) {
      const error = typeof payload.detail === "string" ? payload.detail : "Plugin request failed";
      return Response.json({ error }, { status: response.status });
    }
    return Response.json(payload, { status: response.status });
  } catch {
    return Response.json({ error: "Front Desk could not reach the plugin service" }, { status: 503 });
  }
}
