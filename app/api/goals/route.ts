import { backendApi } from "@/app/lib/backendApi";

export function GET(request: Request) {
  return backendApi(`/api/goals${new URL(request.url).search}`);
}

export function POST(request: Request) {
  return backendApi("/api/goals", { body: request.body, headers: { "Content-Type": "application/json" }, method: "POST", duplex: "half" } as RequestInit);
}
