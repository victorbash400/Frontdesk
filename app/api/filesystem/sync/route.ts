import { auth } from "@/auth";
import { authenticationRequiredResponse } from "@/app/lib/authResponses";

export async function PUT(request: Request) {
  const session = await auth();
  if (!session?.user?.id) return authenticationRequiredResponse();
  const internalSecret = process.env.FRONT_DESK_INTERNAL_SECRET;
  if (!internalSecret) return Response.json({ error: "Front Desk filesystem is not configured" }, { status: 500 });
  const backendUrl = (process.env.FRONT_DESK_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
  try {
    const response = await fetch(`${backendUrl}/api/filesystem/sync`, {
      body: await request.text(),
      headers: {
        "Content-Type": "application/json",
        "X-Front-Desk-Account": session.user.id,
        "X-Front-Desk-Internal-Secret": internalSecret,
      },
      method: "PUT",
    });
    return new Response(await response.text(), { headers: { "Content-Type": "application/json" }, status: response.status });
  } catch {
    return Response.json({ error: "Front Desk filesystem is unavailable" }, { status: 503 });
  }
}
