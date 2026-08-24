import { pluginBackend } from "@/app/lib/pluginBackend";


type RouteContext = { params: Promise<{ permissionId: string }> };

export async function PUT(request: Request, { params }: RouteContext) {
  const { permissionId } = await params;
  return pluginBackend(`/api/plugins/google/permissions/${encodeURIComponent(permissionId)}`, {
    body: await request.text(),
    headers: { "Content-Type": "application/json" },
    method: "PUT",
  });
}
