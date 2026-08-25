import { pluginBackend } from "@/app/lib/pluginBackend";


type RouteContext = { params: Promise<{ permissionId: string; pluginId: string }> };

export async function PUT(request: Request, { params }: RouteContext) {
  const { permissionId, pluginId } = await params;
  return pluginBackend(`/api/plugins/${encodeURIComponent(pluginId)}/permissions/${encodeURIComponent(permissionId)}`, {
    body: await request.text(),
    headers: { "Content-Type": "application/json" },
    method: "PUT",
  });
}
