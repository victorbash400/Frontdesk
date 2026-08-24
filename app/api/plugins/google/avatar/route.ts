import { auth } from "@/auth";


export async function GET() {
  const session = await auth();
  if (!session?.user?.id) return Response.json({ error: "Authentication is required" }, { status: 401 });
  const internalSecret = process.env.FRONT_DESK_INTERNAL_SECRET;
  if (!internalSecret) return Response.json({ error: "Google Workspace is not configured" }, { status: 500 });
  const backendUrl = process.env.FRONT_DESK_BACKEND_URL || "http://127.0.0.1:8000";
  try {
    const response = await fetch(`${backendUrl.replace(/\/$/, "")}/api/plugins/google/avatar`, {
      cache: "no-store",
      headers: {
        "X-Front-Desk-Account": session.user.id,
        "X-Front-Desk-Internal-Secret": internalSecret,
      },
    });
    if (!response.ok) return Response.json({ error: "Google profile photo could not be loaded" }, { status: response.status });
    return new Response(await response.arrayBuffer(), {
      headers: {
        "Cache-Control": "private, max-age=3600",
        "Content-Type": response.headers.get("content-type") || "image/jpeg",
      },
    });
  } catch {
    return Response.json({ error: "Front Desk could not reach the Google connection service" }, { status: 503 });
  }
}
