import { backendAsset } from "@/app/lib/backendAsset";

export async function GET(_: Request, { params }: { params: Promise<{ fileId: string }> }) {
  const { fileId } = await params;
  return backendAsset(`/api/workspace/previews/${encodeURIComponent(fileId)}`);
}
