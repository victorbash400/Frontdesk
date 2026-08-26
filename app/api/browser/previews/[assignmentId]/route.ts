import { backendAsset } from "@/app/lib/backendAsset";

export async function GET(_: Request, { params }: { params: Promise<{ assignmentId: string }> }) {
  const { assignmentId } = await params;
  return backendAsset(`/api/browser/previews/${encodeURIComponent(assignmentId)}`);
}
