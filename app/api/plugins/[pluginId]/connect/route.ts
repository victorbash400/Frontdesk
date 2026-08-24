import { pluginBackend } from "@/app/lib/pluginBackend";


type RouteContext = { params: Promise<{ pluginId: string }> };

export async function POST(_: Request, { params }: RouteContext) {
  const { pluginId } = await params;
  return pluginBackend(`/api/plugins/${encodeURIComponent(pluginId)}/connect`, { method: "POST" });
}

export async function DELETE(_: Request, { params }: RouteContext) {
  const { pluginId } = await params;
  return pluginBackend(`/api/plugins/${encodeURIComponent(pluginId)}/connect`, { method: "DELETE" });
}
