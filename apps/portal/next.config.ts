import type { NextConfig } from "next";

const atlasApiInternalUrl = (process.env.ATLAS_API_INTERNAL_URL ?? "http://127.0.0.1:8000").replace(
  /\/+$/,
  ""
);

const nextConfig: NextConfig = {
  reactStrictMode: true,

  poweredByHeader: false,

  output: "standalone",

  allowedDevOrigins: ["192.168.30.213"],

  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${atlasApiInternalUrl}/api/:path*`
      }
    ];
  }
};

export default nextConfig;
