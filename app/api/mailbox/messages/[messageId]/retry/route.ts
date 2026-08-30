import { backendApi } from "@/app/lib/backendApi";

export async function POST(_: Request, { params }: { params: Promise<{ messageId: string }> }) {
  const { messageId } = await params;
  return backendApi(`/api/mailbox/messages/${encodeURIComponent(messageId)}/retry`, { method: "POST" });
}
