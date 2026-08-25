import { backendApi } from "@/app/lib/backendApi";

export function GET(request: Request) {
  return backendApi(`/api/notifications${new URL(request.url).search}`);
}
