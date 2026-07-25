import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,

  poweredByHeader: false,

  output: "standalone",

  allowedDevOrigins: [
    "192.168.30.213"
  ]
};

export default nextConfig;
