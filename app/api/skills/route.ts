import { backendApi } from "@/app/lib/backendApi";

export function GET() { return backendApi("/api/skills"); }
export function POST(request: Request) { return backendApi("/api/skills", { body: request.body, headers: { "Content-Type": "application/json" }, method: "POST", duplex: "half" } as RequestInit); }
