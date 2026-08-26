import { auth } from "@/auth";

import { authenticationRequiredResponse } from "./authResponses";

export async function backendAsset(path: string) {
  const session = await auth();
  if (!session?.user?.id) return authenticationRequiredResponse();
  const internalSecret = process.env.FRONT_DESK_INTERNAL_SECRET;
  if (!internalSecret) return Response.json({ error: "Front Desk backend is not configured" }, { status: 500 });
  const backendUrl = process.env.FRONT_DESK_BACKEND_URL || "http://127.0.0.1:8000";
  try {
    const response = await fetch(`${backendUrl.replace(/\/$/, "")}${path}`, {
      headers: { "X-Front-Desk-Account": session.user.id, "X-Front-Desk-Internal-Secret": internalSecret },
      cache: "no-store",
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({ detail: "Backend asset request failed" })) as { detail?: string };
      return Response.json({ error: payload.detail || "Backend asset request failed" }, { status: response.status });
    }
    return new Response(response.body, {
      status: response.status,
      headers: {
        "Cache-Control": response.headers.get("cache-control") || "private, no-store",
        "Content-Type": response.headers.get("content-type") || "application/octet-stream",
        ...(response.headers.get("etag") ? { ETag: response.headers.get("etag") as string } : {}),
      },
    });
  } catch {
    return Response.json({ error: "Front Desk could not reach the backend" }, { status: 503 });
  }
}
