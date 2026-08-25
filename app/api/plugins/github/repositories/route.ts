import { pluginBackend } from "@/app/lib/pluginBackend";


export const dynamic = "force-dynamic";

export async function GET() {
  return pluginBackend("/api/plugins/github/repositories");
}

export async function PUT(request: Request) {
  return pluginBackend("/api/plugins/github/repositories", {
    method: "PUT",
    body: await request.text(),
    headers: { "Content-Type": "application/json" },
  });
}
