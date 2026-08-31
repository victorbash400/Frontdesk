import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // The development server is reached at the public hostname so the browser shows that
  // address; without this Next treats its own dev assets as a cross-origin request.
  allowedDevOrigins: ["front-desk-web-222990066722.us-central1.run.app"],
};

export default nextConfig;
