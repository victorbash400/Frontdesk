export const dynamic = "force-dynamic";

export function GET() {
  const configured = Boolean(process.env.AUTH_SECRET?.trim()
    && process.env.FRONT_DESK_INTERNAL_SECRET?.trim()
    && process.env.FRONT_DESK_BACKEND_URL?.startsWith("https://"));
  return Response.json({ status: configured ? "ok" : "misconfigured" }, { status: configured ? 200 : 503 });
}
