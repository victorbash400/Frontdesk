import http from "node:http";
import https from "node:https";
import { Readable } from "node:stream";

type BackendStreamOptions = {
  accountId: string;
  body?: string;
  internalSecret: string;
  method?: "GET" | "POST";
};

export function backendStream(path: string, options: BackendStreamOptions): Promise<Response> {
  const backendUrl = process.env.FRONT_DESK_BACKEND_URL || "http://127.0.0.1:8000";
  const url = new URL(path, backendUrl);
  return new Promise((resolve) => {
    const transport = url.protocol === "https:" ? https : http;
    let settled = false;
    const request = transport.request(url, {
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        "X-Front-Desk-Account": options.accountId,
        "X-Front-Desk-Internal-Secret": options.internalSecret,
      },
      method: options.method || "GET",
    }, (response) => {
      settled = true;
      if (response.statusCode !== 200) {
        response.resume();
        resolve(Response.json({ error: "Front Desk stream failed" }, { status: response.statusCode || 502 }));
        return;
      }
      resolve(new Response(Readable.toWeb(response) as ReadableStream, {
        headers: { "Cache-Control": "no-cache", "Content-Type": "text/event-stream", "X-Accel-Buffering": "no" },
      }));
    });
    request.on("error", () => {
      if (!settled) resolve(Response.json({ error: "Front Desk stream is unavailable" }, { status: 503 }));
    });
    if (options.body) request.write(options.body);
    request.end();
  });
}
