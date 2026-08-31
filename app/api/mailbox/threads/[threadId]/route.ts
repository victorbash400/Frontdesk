import { backendApi } from "@/app/lib/backendApi";

export async function DELETE(_: Request, { params }: { params: Promise<{ threadId: string }> }) {
  const { threadId } = await params;
  return backendApi(`/api/mailbox/threads/${encodeURIComponent(threadId)}`, { method: "DELETE" });
}
