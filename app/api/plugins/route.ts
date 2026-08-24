import { pluginBackend } from "@/app/lib/pluginBackend";


export function GET() {
  return pluginBackend("/api/plugins");
}
