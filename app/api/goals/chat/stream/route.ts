import { auth } from "@/auth";
import { authenticationRequiredResponse } from "@/app/lib/authResponses";
import { backendStream } from "@/app/lib/backendStream";

export async function POST(request: Request) {
  const session = await auth();
  if (!session?.user?.id) return authenticationRequiredResponse();
  const internalSecret = process.env.FRONT_DESK_INTERNAL_SECRET;
  if (!internalSecret) return Response.json({ error: "Front Desk Goals chat is not configured" }, { status: 500 });
  return backendStream("/api/goals/chat/stream", { accountId: session.user.id, body: await request.text(), internalSecret, method: "POST" });
}
