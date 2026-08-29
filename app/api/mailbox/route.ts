import { backendApi } from "@/app/lib/backendApi";

export async function GET() { return backendApi("/api/mailbox", { cache: "no-store" }); }
export async function DELETE() { return backendApi("/api/mailbox", { method: "DELETE" }); }
