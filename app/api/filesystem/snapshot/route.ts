import { backendApi } from "../../../lib/backendApi";

export async function GET() { return backendApi("/api/filesystem/snapshot", { cache: "no-store" }); }
