export async function POST(request: Request) {
  const body = await request.json() as { email?: string; password?: string; name?: string };
  const backendUrl = process.env.OPERATOR_BACKEND_URL || "http://127.0.0.1:8000";
  let response: Response;
  try {
    response = await fetch(`${backendUrl.replace(/\/$/, "")}/accounts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: body.email || "", password: body.password || "", name: body.name || "" }),
    });
  } catch {
    return Response.json({ error: "Operator account service is unavailable" }, { status: 503 });
  }
  const result = await response.json().catch(() => ({ detail: "Could not create account" })) as Record<string, unknown>;
  if (!response.ok) {
    const error = typeof result.detail === "string" ? result.detail : "Could not create account";
    return Response.json({ error }, { status: response.status });
  }
  return Response.json(result, { status: 201 });
}
