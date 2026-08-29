import { backendApi } from "@/app/lib/backendApi";

export async function GET() {
  return backendApi("/api/mailbox/threads");
}
