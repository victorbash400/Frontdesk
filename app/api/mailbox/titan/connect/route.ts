import { backendApi } from "@/app/lib/backendApi";

export async function POST(request: Request) { return backendApi("/api/mailbox/titan/connect", { body: request.body, duplex: "half", headers: { "Content-Type": "application/json" }, method: "POST" } as RequestInit); }
