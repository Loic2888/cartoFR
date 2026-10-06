import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Image autonome pour le conteneur Docker (infra/web.Dockerfile, T004).
  output: "standalone",
};

export default nextConfig;
